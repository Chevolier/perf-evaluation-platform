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

    def _detect_image_format(self, base64_data: str) -> str:
        """Detect image format from base64 data."""
        try:
            decoded_bytes = base64.b64decode(base64_data[:100])
            if decoded_bytes.startswith(b'\xff\xd8\xff'):
                return 'image/jpeg'
            elif decoded_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                return 'image/png'
            elif decoded_bytes.startswith(b'GIF87a') or decoded_bytes.startswith(b'GIF89a'):
                return 'image/gif'
            elif decoded_bytes.startswith(b'RIFF') and b'WEBP' in decoded_bytes[:12]:
                return 'image/webp'
            else:
                return 'image/jpeg'
        except Exception:
            return 'image/jpeg'

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

    def _build_bedrock_request(self, model: str, model_info: Dict, data: Dict) -> Dict:
        """Build request body for Bedrock models."""
        model_id = model_info.get('model_id', '')
        text_prompt = data.get('text') or data.get('prompt') or ''
        frames = data.get('frames') or data.get('images') or []
        max_tokens = data.get('max_tokens', 1000)
        temperature = data.get('temperature', 0.7)
        messages = data.get('messages')

        # Build message content
        message_content = []

        if messages:
            for msg in messages:
                if msg.get('role') == 'user':
                    content = msg.get('content', '')
                    if isinstance(content, str):
                        text_prompt = content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                message_content.append(item)
                            elif isinstance(item, str):
                                message_content.append({"type": "text", "text": item})
                    break

        if text_prompt and not message_content:
            message_content.append({"type": "text", "text": text_prompt})

        if not message_content:
            message_content.append({"type": "text", "text": "Hello"})

        # Add images for multimodal models
        if frames and model_info.get('supports_multimodal', False):
            for frame_base64 in frames:
                message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": frame_base64
                    }
                })

        # Build request based on model type
        if 'claude' in model.lower() or 'anthropic' in model_id.lower():
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": message_content}]
            }
        elif 'nova' in model.lower() or 'amazon' in model_id.lower():
            nova_content = []
            for item in message_content:
                if item.get('type') == 'text':
                    nova_content.append({"text": item.get('text', '')})
                elif item.get('type') == 'image':
                    source = item.get('source', {})
                    nova_content.append({
                        "image": {
                            "format": source.get('media_type', 'image/jpeg').split('/')[-1],
                            "source": {"bytes": source.get('data', '')}
                        }
                    })
            if not nova_content:
                nova_content.append({"text": "Hello"})
            return {
                "messages": [{"role": "user", "content": nova_content}],
                "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}
            }
        else:
            return {
                "messages": [{"role": "user", "content": message_content}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

    def _parse_stream_chunk(self, chunk_data: dict, is_claude: bool, is_nova: bool) -> tuple:
        """Parse streaming chunk based on model type.

        Returns: (text_chunk, is_final, usage_dict)
        """
        text_chunk = ""
        is_final = False
        usage = {}

        if is_claude:
            event_type = chunk_data.get('type', '')
            if event_type == 'content_block_delta':
                delta = chunk_data.get('delta', {})
                if delta.get('type') == 'text_delta':
                    text_chunk = delta.get('text', '')
            elif event_type == 'message_delta':
                if 'usage' in chunk_data:
                    usage = {'output_tokens': chunk_data['usage'].get('output_tokens', 0)}
                    is_final = True
            elif event_type == 'message_start':
                msg = chunk_data.get('message', {})
                if 'usage' in msg:
                    usage = {'input_tokens': msg['usage'].get('input_tokens', 0)}

        elif is_nova:
            if 'contentBlockDelta' in chunk_data:
                delta = chunk_data['contentBlockDelta'].get('delta', {})
                text_chunk = delta.get('text', '')
            elif 'metadata' in chunk_data:
                meta_usage = chunk_data['metadata'].get('usage', {})
                usage = {
                    'input_tokens': meta_usage.get('inputTokens', 0),
                    'output_tokens': meta_usage.get('outputTokens', 0),
                    'total_tokens': meta_usage.get('totalTokens', 0)
                }
                is_final = True

        return text_chunk, is_final, usage

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

            request_body = self._build_bedrock_request(model, model_info, data)

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
                is_claude = 'claude' in model.lower() or 'anthropic' in model_id.lower()
                is_nova = 'nova' in model.lower() or 'amazon' in model_id.lower()

                # TRUE ASYNC iteration over stream
                async for event in response['body']:
                    chunk = event.get('chunk')
                    if chunk:
                        chunk_data = json.loads(chunk.get('bytes', b'{}').decode('utf-8'))

                        text_chunk, is_final, chunk_usage = self._parse_stream_chunk(
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

                # Calculate total tokens
                if 'total_tokens' not in usage and 'input_tokens' in usage and 'output_tokens' in usage:
                    usage['total_tokens'] = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)

                # Send completion
                await result_queue.put({
                    'model': model,
                    'type': 'complete',
                    'status': 'success',
                    'result': {'content': content, 'usage': usage},
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
                    image_format = self._detect_image_format(frame_base64)
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
                "stream": False
            }

            logger.info(f"🚀 Async EC2 call to {model} at {endpoint}")

            session = await self.get_http_session()
            vllm_url = f"{endpoint}/v1/chat/completions"

            async with session.post(
                vllm_url,
                json=vllm_payload,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"vLLM request failed: {response.status} - {error_text}")

                response_body = await response.json()

                content = ""
                usage = {}
                if 'choices' in response_body and response_body['choices']:
                    choice = response_body['choices'][0]
                    if 'message' in choice:
                        content = choice['message'].get('content', '')
                    if 'usage' in response_body:
                        usage = response_body['usage']

                await result_queue.put({
                    'model': model,
                    'status': 'success',
                    'result': {
                        'content': content,
                        'usage': usage,
                        'raw_response': response_body
                    },
                    'duration_ms': (datetime.now() - start_time).total_seconds() * 1000
                })

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
        """Process manually configured API endpoint with aiohttp."""
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
                    image_format = self._detect_image_format(frame_base64)
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

            logger.info(f"🚀 Async Manual API call to {api_url}")

            session = await self.get_http_session()

            async with session.post(
                api_url,
                json=request_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"API call failed: {response.status} - {error_text}")

                response_data = await response.json()

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
                    'status': 'success',
                    'result': {
                        'content': content,
                        'usage': usage,
                        'raw_response': response_data
                    },
                    'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                    'api_url': api_url
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
        """Process SageMaker endpoint with aioboto3."""
        endpoint_name = sagemaker_config.get('endpoint_name', 'Unknown')
        model_name = sagemaker_config.get('model_name', endpoint_name)
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
                    image_format = self._detect_image_format(frame_base64)
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

            async with self._aioboto3_session.client('sagemaker-runtime') as smr_client:
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
