"""Async inference service for handling model predictions with true streaming."""

import asyncio
import json
import base64
from typing import Dict, Any, AsyncGenerator
from datetime import datetime

import aioboto3
import aiohttp

from core.models import model_registry
from utils import get_logger
from .streaming_helpers import (
    build_bedrock_request,
    classify_bedrock_model,
    parse_bedrock_chunk,
    parse_openai_chunk,
    finalize_usage,
    SSEBuffer,
    detect_image_format,
    extract_context_limits_from_error,
)


logger = get_logger(__name__)


class AsyncInferenceService:
    """Async service for handling model inference requests with true streaming.

    Uses aioboto3 for native async Bedrock/SageMaker streaming and aiohttp
    for async HTTP requests. This allows each chunk to be yielded with proper
    async control flow, enabling incremental frontend display.
    """

    def __init__(self):
        """Initialize async inference service."""
        self.registry = model_registry
        self._http_session: aiohttp.ClientSession = None
        self._aioboto3_session = aioboto3.Session()

    async def get_http_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._http_session

    async def close(self):
        """Cleanup resources."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    def _resize_image_for_sagemaker(self, base64_data: str, max_width: int = 720, max_height: int = 480) -> str:
        """Resize image for SageMaker endpoint."""
        import io
        from PIL import Image

        try:
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes))

            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')

            original_width, original_height = image.size
            ratio = min(max_width / original_width, max_height / original_height)

            if ratio < 1:
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"🖼️ Resized image from {original_width}x{original_height} to {new_width}x{new_height}")

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return base64_data

    async def multi_inference(self, data: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Run inference on multiple models with true async streaming.

        Uses asyncio.Queue to merge streams from multiple concurrent model tasks.
        Each model task puts chunks to queue as they arrive from the API.
        Main generator yields from queue, providing natural timing for incremental display.
        """
        models = data.get('models', [])
        manual_config = data.get('manual_config')
        sagemaker_config = data.get('sagemaker_config')

        if not models and not manual_config and not sagemaker_config:
            yield f"data: {json.dumps({'error': 'No models specified', 'status': 'error'})}\n\n"
            return

        result_queue: asyncio.Queue = asyncio.Queue()
        tasks = []

        # Create async tasks for each endpoint type
        if manual_config:
            tasks.append(asyncio.create_task(
                self._process_manual_api_async(manual_config, data, result_queue)
            ))

        if sagemaker_config:
            tasks.append(asyncio.create_task(
                self._process_sagemaker_endpoint_async(sagemaker_config, data, result_queue)
            ))

        for model in models:
            if self.registry.is_bedrock_model(model):
                tasks.append(asyncio.create_task(
                    self._process_bedrock_model_async(model, data, result_queue)
                ))
            elif self.registry.is_ec2_model(model):
                tasks.append(asyncio.create_task(
                    self._process_ec2_model_async(model, data, result_queue)
                ))
            else:
                # Check for custom deployed model
                from .model_service import ModelService
                model_service = ModelService()
                custom_status = model_service.get_ec2_deployment_status(model)
                if custom_status.get('status') in ['deployed', 'inprogress']:
                    tasks.append(asyncio.create_task(
                        self._process_ec2_model_async(model, data, result_queue)
                    ))
                else:
                    yield f"data: {json.dumps({'model': model, 'status': 'error', 'message': f'Unknown model: {model}'})}\n\n"

        if not tasks:
            yield f"data: {json.dumps({'error': 'No valid models', 'status': 'error'})}\n\n"
            return

        # Track completion
        completed_models = set()
        total_tasks = len(tasks)
        heartbeat_interval = 1.0

        # Consumer loop - yields results as they arrive
        while len(completed_models) < total_tasks:
            try:
                result = await asyncio.wait_for(
                    result_queue.get(),
                    timeout=heartbeat_interval
                )

                # Track completion
                result_type = result.get('type', '')
                if result_type == 'complete' or result.get('status') in ['success', 'error', 'not_deployed']:
                    completed_models.add(result.get('model'))

                # Yield SSE formatted result
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

            except asyncio.TimeoutError:
                # Send heartbeat
                yield f"data: {json.dumps({'type': 'heartbeat', 'completed': len(completed_models), 'total': total_tasks})}\n\n"

        # Ensure all tasks complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Send final completion
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        # Cleanup
        await self.close()

    async def _process_bedrock_model_async(
        self,
        model: str,
        data: Dict[str, Any],
        result_queue: asyncio.Queue
    ) -> None:
        """Process Bedrock model with native async streaming.

        Uses aioboto3 for true async streaming - each chunk yields control
        to event loop, allowing timely delivery to client.
        """
        try:
            start_time = datetime.now()

            model_info = self.registry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Model {model} not found in registry")

            model_id = model_info.get('model_id')
            if not model_id:
                raise ValueError(f"No model_id found for model {model}")

            # Use shared helper for request building
            request_body = build_bedrock_request(model, model_info, data)

            logger.info(f"🚀 Async Bedrock call to {model_id}")

            # Use aioboto3 for async streaming
            async with self._aioboto3_session.client(
                'bedrock-runtime',
                region_name='us-west-2'
            ) as bedrock_client:

                response = await bedrock_client.invoke_model_with_response_stream(
                    modelId=model_id,
                    body=json.dumps(request_body),
                    contentType='application/json'
                )

                content = ""
                usage = {}
                is_claude, is_nova = classify_bedrock_model(model, model_id)

                # TRUE ASYNC iteration over stream
                async for event in response['body']:
                    chunk = event.get('chunk')
                    if chunk:
                        chunk_data = json.loads(chunk.get('bytes', b'{}').decode('utf-8'))

                        # Use shared helper for chunk parsing
                        text_chunk, is_final, chunk_usage = parse_bedrock_chunk(
                            chunk_data, is_claude, is_nova
                        )

                        if text_chunk:
                            content += text_chunk
                            # Put to queue immediately - yields control to event loop
                            await result_queue.put({
                                'model': model,
                                'type': 'partial',
                                'content': text_chunk,
                                'accumulated_content': content
                            })
                            # Small delay ensures chunk is sent before processing next
                            await asyncio.sleep(0.01)

                        if chunk_usage:
                            usage.update(chunk_usage)

                # Send completion with finalized usage
                await result_queue.put({
                    'model': model,
                    'type': 'complete',
                    'status': 'success',
                    'result': {'content': content, 'usage': finalize_usage(usage)},
                    'duration_ms': (datetime.now() - start_time).total_seconds() * 1000
                })

        except Exception as e:
            logger.error(f"Error processing Bedrock model {model}: {e}")
            await result_queue.put({
                'model': model,
                'status': 'error',
                'message': str(e)
            })

    async def _process_ec2_model_async(
        self,
        model: str,
        data: Dict[str, Any],
        result_queue: asyncio.Queue
    ) -> None:
        """Process EC2 vLLM model with aiohttp."""
        try:
            from .model_service import ModelService
            model_service = ModelService()

            deployment_status = model_service.get_ec2_deployment_status(model)
            if deployment_status.get('status') != 'deployed':
                await result_queue.put({
                    'model': model,
                    'status': 'not_deployed',
                    'message': f'Model {model} is not deployed: {deployment_status.get("message", "Unknown")}'
                })
                return

            start_time = datetime.now()

            model_info = self.registry.get_model_info(model)
            if not model_info:
                model_info = {
                    "name": model,
                    "supports_multimodal": True,
                    "supports_streaming": True,
                    "model_path": model
                }

            huggingface_repo = model_info.get('huggingface_repo', model)
            endpoint = deployment_status.get('endpoint', 'http://localhost:8000')

            # Build vLLM payload
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)

            messages = []
            content_parts = []

            if text_prompt:
                content_parts.append({"type": "text", "text": text_prompt})

            if frames and model_info.get('supports_multimodal', False):
                for frame_base64 in frames:
                    image_format = detect_image_format(frame_base64)
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{image_format};base64,{frame_base64}"}
                    })

            if frames and model_info.get('supports_multimodal', False):
                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append({"role": "user", "content": text_prompt})

            vllm_payload = {
                "model": huggingface_repo,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                "stream_options": {"include_usage": True}
            }

            logger.info(f"🚀 Async EC2 streaming call to {model} at {endpoint}")

            session = await self.get_http_session()
            vllm_url = f"{endpoint}/v1/chat/completions"

            for attempt in range(2):
                async with session.post(
                    vllm_url,
                    json=vllm_payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if not response.ok:
                        error_text = await response.text()

                        if response.status == 400 and attempt == 0:
                            limits = extract_context_limits_from_error(error_text)
                            if limits:
                                max_ctx, input_tokens = limits
                                allowed = max(1, max_ctx - input_tokens - 1)
                                if allowed < vllm_payload.get("max_tokens", allowed + 1):
                                    logger.warning(
                                        f"vLLM max_tokens too large; retrying with max_tokens={allowed} "
                                        f"(max_ctx={max_ctx}, input_tokens={input_tokens})"
                                    )
                                    vllm_payload["max_tokens"] = allowed
                                    continue

                        raise ValueError(f"vLLM request failed: {response.status} - {error_text}")

                    # Check content-type for streaming support
                    content_type = response.headers.get('content-type', '')
                    if 'text/event-stream' not in content_type:
                        # Non-streaming response - parse as JSON
                        response_data = await response.json()
                        content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        usage = response_data.get('usage', {})
                        await result_queue.put({
                            'model': model,
                            'type': 'complete',
                            'status': 'success',
                            'result': {
                                'content': content,
                                'usage': finalize_usage(usage)
                            },
                            'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                            'streaming': False
                        })
                        return

                    content = ""
                    usage = {}
                    buffer = SSEBuffer()

                    # Stream and parse SSE chunks
                    async for chunk_bytes in response.content:
                        for data_str in buffer.add(chunk_bytes.decode('utf-8')):
                            try:
                                chunk_data = json.loads(data_str)
                                text_chunk, is_final, chunk_usage = parse_openai_chunk(chunk_data)

                                if text_chunk:
                                    content += text_chunk
                                    await result_queue.put({
                                        'model': model,
                                        'type': 'partial',
                                        'content': text_chunk,
                                        'accumulated_content': content
                                    })
                                    await asyncio.sleep(0.01)

                                if chunk_usage:
                                    usage.update(chunk_usage)

                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE chunk: {data_str[:50]}")
                                continue

                    # Flush any remaining data in buffer
                    for data_str in buffer.flush():
                        try:
                            chunk_data = json.loads(data_str)
                            text_chunk, _, chunk_usage = parse_openai_chunk(chunk_data)
                            if text_chunk:
                                content += text_chunk
                            if chunk_usage:
                                usage.update(chunk_usage)
                        except json.JSONDecodeError:
                            pass

                    await result_queue.put({
                        'model': model,
                        'type': 'complete',
                        'status': 'success',
                        'result': {
                            'content': content,
                            'usage': finalize_usage(usage)
                        },
                        'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                        'streaming': True
                    })
                    return

        except Exception as e:
            logger.error(f"Error processing EC2 model {model}: {e}")
            await result_queue.put({
                'model': model,
                'status': 'error',
                'message': str(e)
            })

    async def _process_manual_api_async(
        self,
        manual_config: Dict[str, Any],
        data: Dict[str, Any],
        result_queue: asyncio.Queue
    ) -> None:
        """Process manually configured API endpoint with streaming auto-detect."""
        model_name = manual_config.get('model_name', 'Unknown')
        try:
            start_time = datetime.now()

            api_url = manual_config.get('api_url')
            if not api_url or not model_name:
                raise ValueError("Both api_url and model_name are required")

            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)

            content_parts = []
            if text_prompt:
                content_parts.append({"type": "text", "text": text_prompt})

            if frames:
                for frame_base64 in frames:
                    image_format = detect_image_format(frame_base64)
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{image_format};base64,{frame_base64}"}
                    })

            request_payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            session = await self.get_http_session()
            stream_enabled = manual_config.get('stream', True)
            streaming_success = False

            # Try streaming first if enabled
            if stream_enabled:
                try:
                    streaming_payload = {
                        **request_payload,
                        "stream": True,
                        "stream_options": {"include_usage": True}
                    }

                    logger.info(f"🚀 Async Manual API streaming call to {api_url}")

                    async with session.post(
                        api_url,
                        json=streaming_payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.ok:
                            content_type = response.headers.get('content-type', '')

                            if 'text/event-stream' in content_type:
                                streaming_success = True
                                logger.info(f"✅ Manual API supports streaming: {api_url}")

                                content = ""
                                usage = {}
                                buffer = SSEBuffer()

                                async for chunk_bytes in response.content:
                                    for data_str in buffer.add(chunk_bytes.decode('utf-8')):
                                        try:
                                            chunk_data = json.loads(data_str)
                                            text_chunk, is_final, chunk_usage = parse_openai_chunk(chunk_data)

                                            if text_chunk:
                                                content += text_chunk
                                                await result_queue.put({
                                                    'model': f"{model_name} (Manual API)",
                                                    'type': 'partial',
                                                    'content': text_chunk,
                                                    'accumulated_content': content
                                                })
                                                await asyncio.sleep(0.01)

                                            if chunk_usage:
                                                usage.update(chunk_usage)

                                        except json.JSONDecodeError:
                                            continue

                                # Flush any remaining data in buffer
                                for data_str in buffer.flush():
                                    try:
                                        chunk_data = json.loads(data_str)
                                        text_chunk, _, chunk_usage = parse_openai_chunk(chunk_data)
                                        if text_chunk:
                                            content += text_chunk
                                        if chunk_usage:
                                            usage.update(chunk_usage)
                                    except json.JSONDecodeError:
                                        pass

                                await result_queue.put({
                                    'model': f"{model_name} (Manual API)",
                                    'type': 'complete',
                                    'status': 'success',
                                    'result': {
                                        'content': content,
                                        'usage': finalize_usage(usage)
                                    },
                                    'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                                    'api_url': api_url,
                                    'streaming': True
                                })
                                return

                except Exception as stream_error:
                    logger.warning(f"Streaming attempt failed, falling back: {stream_error}")

            # Fallback to non-streaming
            if not streaming_success:
                logger.info(f"🚀 Async Manual API non-streaming call to {api_url}")
                for attempt in range(2):
                    async with session.post(
                        api_url,
                        json=request_payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if not response.ok:
                            error_text = await response.text()

                            if response.status == 400 and attempt == 0:
                                limits = extract_context_limits_from_error(error_text)
                                if limits:
                                    max_ctx, input_tokens = limits
                                    allowed = max(1, max_ctx - input_tokens - 1)
                                    if allowed < request_payload.get("max_tokens", allowed + 1):
                                        logger.warning(
                                            f"Manual API max_tokens too large; retrying with max_tokens={allowed} "
                                            f"(max_ctx={max_ctx}, input_tokens={input_tokens})"
                                        )
                                        request_payload["max_tokens"] = allowed
                                        continue

                            raise ValueError(f"API call failed: {response.status} - {error_text}")

                        response_data = await response.json()
                        break

                    content = ""
                    usage = {}

                    if 'choices' in response_data and response_data['choices']:
                        choice = response_data['choices'][0]
                        if 'message' in choice:
                            message = choice['message']
                            if 'reasoning_content' in message and message['reasoning_content']:
                                reasoning = message['reasoning_content'].strip()
                                main_content = message.get('content', '').strip() if message.get('content') else ''
                                if reasoning and main_content:
                                    content = f"**Reasoning:**\n{reasoning}\n\n**Response:**\n{main_content}"
                                elif reasoning:
                                    content = f"**Reasoning:**\n{reasoning}"
                                else:
                                    content = main_content
                            elif 'content' in message:
                                content = message['content']

                    if 'usage' in response_data:
                        usage = {
                            'input_tokens': response_data['usage'].get('prompt_tokens', 0),
                            'output_tokens': response_data['usage'].get('completion_tokens', 0),
                            'total_tokens': response_data['usage'].get('total_tokens', 0)
                        }

                    await result_queue.put({
                        'model': f"{model_name} (Manual API)",
                        'type': 'complete',
                        'status': 'success',
                        'result': {
                            'content': content,
                            'usage': usage,
                            'raw_response': response_data
                        },
                        'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                        'api_url': api_url,
                        'streaming': False
                    })

        except Exception as e:
            logger.error(f"Error processing manual API: {e}")
            await result_queue.put({
                'model': f"{model_name} (Manual API)",
                'status': 'error',
                'message': str(e),
                'api_url': manual_config.get('api_url', 'Unknown')
            })

    async def _process_sagemaker_endpoint_async(
        self,
        sagemaker_config: Dict[str, Any],
        data: Dict[str, Any],
        result_queue: asyncio.Queue
    ) -> None:
        """Process SageMaker endpoint with aioboto3.

        Supports streaming via invoke_endpoint_with_response_stream with automatic
        fallback to non-streaming invoke_endpoint if streaming is not supported.
        """
        endpoint_name = sagemaker_config.get('endpoint_name', 'Unknown')
        model_name = sagemaker_config.get('model_name', endpoint_name)
        stream_enabled = sagemaker_config.get('stream', True)  # Default to trying streaming

        try:
            start_time = datetime.now()

            if not endpoint_name:
                raise ValueError("endpoint_name is required")

            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 4096)
            temperature = data.get('temperature', 0.6)
            resize_width = data.get('resize_width')
            resize_height = data.get('resize_height')

            # Build messages
            if frames:
                user_content = [{"type": "text", "text": text_prompt or "Please describe this image."}]
                frame_base64 = frames[0]

                if resize_width or resize_height:
                    max_w = resize_width or 720
                    max_h = resize_height or 480
                    resized_base64 = self._resize_image_for_sagemaker(frame_base64, max_w, max_h)
                    image_url_base64 = f"data:image/png;base64,{resized_base64}"
                else:
                    image_format = detect_image_format(frame_base64)
                    image_url_base64 = f"data:{image_format};base64,{frame_base64}"

                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url_base64}
                })

                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_content}
                ]
            else:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": text_prompt}
                ]

            request_payload = {
                "messages": messages,
                "temperature": temperature,
                "top_p": 0.8,
                "top_k": 20,
                "image_max_pixels": 1080 ** 2,
            }
            if max_tokens:
                request_payload["max_tokens"] = max_tokens

            logger.info(f"🚀 Async SageMaker call to {endpoint_name}")

            streaming_success = False

            async with self._aioboto3_session.client('sagemaker-runtime') as smr_client:
                # Try streaming first if enabled
                if stream_enabled:
                    try:
                        streaming_payload = {
                            **request_payload,
                            "stream": True,
                            "stream_options": {"include_usage": True}
                        }

                        response = await smr_client.invoke_endpoint_with_response_stream(
                            EndpointName=endpoint_name,
                            ContentType="application/json",
                            Body=json.dumps(streaming_payload)
                        )

                        streaming_success = True
                        logger.info(f"📡 Async SageMaker streaming enabled for {endpoint_name}")

                        content = ""
                        usage = {}
                        buffer = SSEBuffer()

                        async for event in response['Body']:
                            chunk_bytes = event.get('PayloadPart', {}).get('Bytes', b'')
                            if not chunk_bytes:
                                continue

                            for data_str in buffer.add(chunk_bytes.decode('utf-8')):
                                try:
                                    chunk_data = json.loads(data_str)
                                    text_chunk, is_final, chunk_usage = parse_openai_chunk(chunk_data)

                                    if text_chunk:
                                        content += text_chunk
                                        await result_queue.put({
                                            'model': model_name,
                                            'type': 'partial',
                                            'content': text_chunk,
                                            'accumulated_content': content
                                        })
                                        await asyncio.sleep(0.01)

                                    if chunk_usage:
                                        usage.update(chunk_usage)
                                except json.JSONDecodeError:
                                    continue

                        # Flush any remaining buffer
                        for data_str in buffer.flush():
                            try:
                                chunk_data = json.loads(data_str)
                                text_chunk, _, chunk_usage = parse_openai_chunk(chunk_data)
                                if text_chunk:
                                    content += text_chunk
                                if chunk_usage:
                                    usage.update(chunk_usage)
                            except json.JSONDecodeError:
                                pass

                        await result_queue.put({
                            'model': model_name,
                            'type': 'complete',
                            'status': 'success',
                            'result': {
                                'content': content,
                                'usage': finalize_usage(usage)
                            },
                            'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                            'metadata': {'endpoint_name': endpoint_name, 'streaming': True}
                        })

                        logger.info(f"✅ Async SageMaker {endpoint_name} (streaming) completed")
                        return

                    except Exception as e:
                        logger.warning(f"SageMaker streaming not supported for {endpoint_name}, falling back: {e}")
                        streaming_success = False

                # Non-streaming fallback
                if not streaming_success:
                    response = await smr_client.invoke_endpoint(
                        EndpointName=endpoint_name,
                        ContentType="application/json",
                        Body=json.dumps(request_payload)
                    )

                    response_body = await response['Body'].read()
                    response_json = json.loads(response_body.decode('utf-8'))

                    content = ""
                    if 'choices' in response_json and response_json['choices']:
                        choice = response_json['choices'][0]
                        if 'message' in choice:
                            content = choice['message'].get('content', '')

                    usage = {}
                    if 'usage' in response_json:
                        usage = {
                            'input_tokens': response_json['usage'].get('prompt_tokens', 0),
                            'output_tokens': response_json['usage'].get('completion_tokens', 0),
                            'total_tokens': response_json['usage'].get('total_tokens', 0)
                        }

                    await result_queue.put({
                        'model': model_name,
                        'status': 'success',
                        'result': {
                            'content': content,
                            'usage': usage,
                            'raw_response': response_json
                        },
                        'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                        'metadata': {'endpoint_name': endpoint_name}
                    })

        except Exception as e:
            logger.error(f"Error processing SageMaker endpoint {endpoint_name}: {e}")
            await result_queue.put({
                'model': f"{model_name} (SageMaker)",
                'status': 'error',
                'message': str(e),
                'endpoint_name': endpoint_name
            })
