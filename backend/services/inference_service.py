"""Inference service for handling model predictions."""

import json
import queue
import threading
import base64
from typing import Dict, Any, List, Generator
from datetime import datetime

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


class InferenceService:
    """Service for handling model inference requests."""

    def __init__(self):
        """Initialize inference service."""
        self.registry = model_registry
        # Import ModelService to check deployment status for custom models
        from .model_service import ModelService
        self.model_service = ModelService()

    def _resize_image_for_sagemaker(self, base64_data: str, max_width: int = 720, max_height: int = 480) -> str:
        """Resize image for SageMaker endpoint to avoid size errors.

        Args:
            base64_data: Base64 encoded image data
            max_width: Maximum width (default 720)
            max_height: Maximum height (default 480)

        Returns:
            Base64 encoded resized PNG image
        """
        import io
        from PIL import Image

        try:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_data)

            # Open image
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary (for PNG with alpha channel)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')

            # Resize while maintaining aspect ratio
            original_width, original_height = image.size
            ratio = min(max_width / original_width, max_height / original_height)

            if ratio < 1:  # Only resize if image is larger than max dimensions
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"🖼️ Resized image from {original_width}x{original_height} to {new_width}x{new_height}")

            # Save to PNG format
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            resized_bytes = buffer.getvalue()

            # Encode back to base64
            return base64.b64encode(resized_bytes).decode('utf-8')

        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            # Return original if resize fails
            return base64_data

    def multi_inference(self, data: Dict[str, Any]) -> Generator[str, None, None]:
        """Run inference on multiple models simultaneously.
        
        Args:
            data: Request data containing models and inference parameters
            
        Yields:
            JSON strings with inference results
        """
        models = data.get('models', [])
        manual_config = data.get('manual_config')
        sagemaker_config = data.get('sagemaker_config')

        if not models and not manual_config and not sagemaker_config:
            yield f"data: {json.dumps({'error': 'No models, manual configuration, or SageMaker configuration specified', 'status': 'error'})}\n\n"
            return
        
        result_queue = queue.Queue()
        threads = []
        
        # Handle manual configuration
        if manual_config:
            thread = threading.Thread(
                target=self._process_manual_api,
                args=(manual_config, data, result_queue)
            )
            threads.append(thread)
            thread.start()

        # Handle SageMaker endpoint configuration
        if sagemaker_config:
            thread = threading.Thread(
                target=self._process_sagemaker_endpoint,
                args=(sagemaker_config, data, result_queue)
            )
            threads.append(thread)
            thread.start()
        
        # Create threads for each model
        for model in models:
            if self.registry.is_bedrock_model(model):
                thread = threading.Thread(
                    target=self._process_bedrock_model,
                    args=(model, data, result_queue)
                )
            elif self.registry.is_ec2_model(model):
                thread = threading.Thread(
                    target=self._process_ec2_model,
                    args=(model, data, result_queue)
                )
            else:
                # Check if this is a deployed custom model (not in registry but deployed via model service)
                custom_model_status = self.model_service.get_ec2_deployment_status(model)
                if custom_model_status.get('status') in ['deployed', 'inprogress']:
                    # Treat deployed custom model as EC2 model
                    logger.info(f"🤖 Processing custom deployed model as EC2: {model}")
                    thread = threading.Thread(
                        target=self._process_ec2_model,
                        args=(model, data, result_queue)
                    )
                else:
                    # Truly unknown model
                    logger.warning(f"❌ Unknown model type: {model}")
                    result_queue.put({
                        'model': model,
                        'status': 'error',
                        'message': f'未知模型类型: {model}'
                    })
                    continue
            
            threads.append(thread)
            thread.start()
        
        # Wait for results and stream them back
        # Track completed models (those that sent 'type': 'complete')
        completed_models = set()
        total_models = len(threads)
        heartbeat_counter = 0

        while len(completed_models) < total_models:
            try:
                # Use short timeout for responsive streaming
                result = result_queue.get(timeout=0.05)

                # Check if this is a completion message
                result_type = result.get('type', '')
                if result_type == 'complete' or result.get('status') in ['success', 'error']:
                    completed_models.add(result.get('model'))

                # Stream result back to client (SSE format)
                response_data = f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                yield response_data

            except queue.Empty:
                heartbeat_counter += 1
                # Send heartbeat every ~1 second (20 * 0.05s = 1s)
                if heartbeat_counter >= 20:
                    heartbeat_counter = 0
                    yield f"data: {json.dumps({'type': 'heartbeat', 'completed': len(completed_models), 'total': total_models})}\n\n"

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)

        # Send completion signal
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    def _process_bedrock_model(self, model: str, data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for a Bedrock model.

        Args:
            model: Model identifier
            data: Request data
            result_queue: Queue to put results
        """
        try:
            start_time = datetime.now()

            # Import boto3 for Bedrock
            try:
                import boto3
                from botocore.exceptions import ClientError, NoCredentialsError
            except ImportError:
                raise ImportError("boto3 is required for Bedrock models. Please install: pip install boto3")

            # Get model configuration
            model_info = self.registry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Model {model} not found in registry")

            model_id = model_info.get('model_id')
            if not model_id:
                raise ValueError(f"No model_id found for model {model}")

            # Create Bedrock Runtime client
            try:
                bedrock_client = boto3.client('bedrock-runtime', region_name='us-west-2')
            except NoCredentialsError:
                raise ValueError("AWS credentials not configured. Please configure AWS credentials.")

            # Use shared helper for request building
            request_body = build_bedrock_request(model, model_info, data)

            logger.info(f"Calling Bedrock model {model_id} with streaming request")

            # Use streaming API for real-time token output
            response = bedrock_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json'
            )

            # Process streaming response
            content = ""
            usage = {}
            is_claude, is_nova = classify_bedrock_model(model, model_id)

            for event in response.get('body', []):
                chunk = event.get('chunk')
                if chunk:
                    chunk_data = json.loads(chunk.get('bytes', b'{}').decode('utf-8'))

                    # Use shared helper for chunk parsing
                    text_chunk, is_final, chunk_usage = parse_bedrock_chunk(
                        chunk_data, is_claude, is_nova
                    )

                    if text_chunk:
                        content += text_chunk
                        # Send partial result for streaming display
                        result_queue.put({
                            'model': model,
                            'type': 'partial',
                            'content': text_chunk,
                            'accumulated_content': content
                        })

                    if chunk_usage:
                        usage.update(chunk_usage)

            # Send final complete result with finalized usage
            result = {
                'model': model,
                'type': 'complete',
                'status': 'success',
                'result': {
                    'content': content,
                    'usage': finalize_usage(usage)
                },
                'duration_ms': (datetime.now() - start_time).total_seconds() * 1000
            }

            result_queue.put(result)
            
        except Exception as e:
            logger.error(f"Error processing Bedrock model {model}: {e}")
            result_queue.put({
                'model': model,
                'status': 'error',
                'message': str(e)
            })
    
    def _process_ec2_model(self, model: str, data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for an EC2 Docker-deployed model.

        Args:
            model: Model identifier (platform key like 'qwen3-8b')
            data: Request data
            result_queue: Queue to put results
        """
        try:
            import requests
            import json
            from api.routes.model_routes import model_service

            # Check if model is deployed
            deployment_status = model_service.get_ec2_deployment_status(model)

            if deployment_status.get('status') != 'deployed':
                result_queue.put({
                    'model': model,
                    'status': 'not_deployed',
                    'message': f'Model {model} is not deployed: {deployment_status.get("message", "Unknown status")}'
                })
                return

            start_time = datetime.now()

            # Get model information from registry if available, otherwise use defaults for custom models
            model_info = self.registry.get_model_info(model)
            if not model_info:
                # This is likely a custom model not in registry
                logger.info(f"🤖 Model {model} not in registry, treating as custom model")
                model_info = {
                    "name": model,
                    "supports_multimodal": True,  # Assume custom models support multimodal
                    "supports_streaming": True,
                    "model_path": model  # Use model name as path for custom models
                }

            # Get the actual HuggingFace repo name for vLLM API call
            huggingface_repo = model_info.get('huggingface_repo', model)

            # Get the deployment endpoint
            endpoint = deployment_status.get('endpoint', 'http://localhost:8000')
            
            # Prepare request data for vLLM API
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)

            # Build messages array for vLLM Chat Completions API
            messages = []
            content_parts = []

            # Add text content
            if text_prompt:
                content_parts.append({
                    "type": "text",
                    "text": text_prompt
                })

            # Add image content for multimodal models
            if frames and model_info.get('supports_multimodal', False):
                for frame_base64 in frames:
                    # Detect the actual image format
                    image_format = detect_image_format(frame_base64)

                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_format};base64,{frame_base64}"
                        }
                    })

            # For multimodal models with images, always use content_parts array format
            # For text-only, use simple string format
            if frames and model_info.get('supports_multimodal', False):
                messages.append({
                    "role": "user",
                    "content": content_parts
                })
            else:
                messages.append({
                    "role": "user",
                    "content": text_prompt
                })

            # Prepare vLLM request payload with streaming enabled
            vllm_payload = {
                "model": huggingface_repo,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                "stream_options": {"include_usage": True}
            }

            logger.info(f"🚀 Streaming EC2 vLLM model {model} ({huggingface_repo}) at {endpoint}")

            # Make HTTP request to local vLLM server with streaming
            vllm_url = f"{endpoint}/v1/chat/completions"

            try:
                logger.info(f"🔥 Making streaming POST request to: {vllm_url}")

                for attempt in range(2):
                    response = requests.post(
                        vllm_url,
                        json=vllm_payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=120,
                        stream=True
                    )

                    if not response.ok:
                        error_text = response.text
                        logger.error(f"❌ HTTP error {response.status_code}: {error_text}")

                        if response.status_code == 400 and attempt == 0:
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

                        raise ValueError(f"vLLM request failed: {response.status_code} - {error_text}")

                    # Check content-type for streaming support
                    content_type = response.headers.get('content-type', '')
                    if 'text/event-stream' not in content_type:
                        # Non-streaming response - parse as JSON
                        response_data = response.json()
                        content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        usage = response_data.get('usage', {})
                        result_queue.put({
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
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue

                        for data_str in buffer.add(line + '\n'):
                            try:
                                chunk_data = json.loads(data_str)
                                text_chunk, is_final, chunk_usage = parse_openai_chunk(chunk_data)

                                if text_chunk:
                                    content += text_chunk
                                    result_queue.put({
                                        'model': model,
                                        'type': 'partial',
                                        'content': text_chunk,
                                        'accumulated_content': content
                                    })

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

                    # Send final complete result
                    result = {
                        'model': model,
                        'type': 'complete',
                        'status': 'success',
                        'result': {
                            'content': content,
                            'usage': finalize_usage(usage)
                        },
                        'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                        'streaming': True
                    }

                    result_queue.put(result)
                    return

            except requests.exceptions.RequestException as req_error:
                logger.error(f"HTTP request failed for {model}: {req_error}")
                raise ValueError(f"vLLM request failed: {req_error}")
            
        except Exception as e:
            logger.error(f"Error processing EC2 model {model}: {e}")
            result_queue.put({
                'model': model,
                'status': 'error',
                'message': str(e)
            })
    
    def _process_manual_api(self, manual_config: Dict[str, Any], data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for a manually configured API endpoint.

        Supports streaming with auto-detect: tries streaming first, falls back to
        non-streaming if the endpoint doesn't support it.

        Args:
            manual_config: Manual configuration containing api_url and model_name
            data: Request data
            result_queue: Queue to put results
        """
        try:
            import requests

            start_time = datetime.now()

            api_url = manual_config.get('api_url')
            model_name = manual_config.get('model_name')
            stream_enabled = manual_config.get('stream', True)  # Default to trying streaming

            if not api_url or not model_name:
                raise ValueError("Both api_url and model_name are required in manual_config")

            display_model = f"{model_name} (Manual API)"

            # Prepare request data
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)

            # Build messages array
            messages = []
            content_parts = []

            # Add text content
            if text_prompt:
                content_parts.append({
                    "type": "text",
                    "text": text_prompt
                })

            # Add image content if frames are provided
            if frames:
                for frame_base64 in frames:
                    # Detect actual image format
                    image_format = detect_image_format(frame_base64)
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_format};base64,{frame_base64}"
                        }
                    })
                logger.info(f"🖼️ Manual API request with {len(frames)} images")

            messages.append({
                "role": "user",
                "content": content_parts
            })

            # Prepare base request payload
            request_payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            logger.info(f"Calling manual API {api_url} with model {model_name}")
            logger.debug(f"Request payload: {request_payload}")

            # Try streaming first if enabled
            streaming_success = False

            if stream_enabled:
                try:
                    streaming_payload = {
                        **request_payload,
                        "stream": True,
                        "stream_options": {"include_usage": True}
                    }

                    response = requests.post(
                        api_url,
                        json=streaming_payload,
                        headers={"Content-Type": "application/json"},
                        stream=True,
                        timeout=120
                    )

                    content_type = response.headers.get('content-type', '')

                    if response.ok and 'text/event-stream' in content_type:
                        streaming_success = True
                        logger.info(f"📡 Manual API streaming enabled for {model_name}")

                        content = ""
                        usage = {}
                        buffer = SSEBuffer()

                        for line in response.iter_lines(decode_unicode=True):
                            if not line:
                                continue

                            for data_str in buffer.add(line + '\n'):
                                try:
                                    chunk_data = json.loads(data_str)
                                    text_chunk, is_final, chunk_usage = parse_openai_chunk(chunk_data)

                                    if text_chunk:
                                        content += text_chunk
                                        result_queue.put({
                                            'model': display_model,
                                            'type': 'partial',
                                            'content': text_chunk,
                                            'accumulated_content': content
                                        })

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

                        result_queue.put({
                            'model': display_model,
                            'type': 'complete',
                            'status': 'success',
                            'result': {
                                'content': content,
                                'usage': finalize_usage(usage)
                            },
                            'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                            'api_url': api_url
                        })
                        return
                    else:
                        logger.info(f"Manual API {model_name} doesn't support streaming (content-type: {content_type}), falling back")

                except Exception as e:
                    logger.warning(f"Streaming failed for manual API {model_name}, falling back: {e}")

            # Non-streaming fallback
            if not streaming_success:
                response_data = None
                for attempt in range(2):
                    response = requests.post(
                        api_url,
                        json=request_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=120
                    )

                    if not response.ok:
                        if response.status_code == 400 and attempt == 0:
                            limits = extract_context_limits_from_error(response.text)
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

                        raise ValueError(f"API call failed with status {response.status_code}: {response.text}")

                    response_data = response.json()
                    logger.info(f"Manual API response for {model_name}: {response_data}")
                    break

                # Extract content and usage from response
                content = ""
                usage = {}

                # Handle OpenAI-compatible response format
                if 'choices' in response_data and response_data['choices']:
                    choice = response_data['choices'][0]
                    if 'message' in choice:
                        message = choice['message']
                        # Check for reasoning_content first (manual API Qwen models)
                        if 'reasoning_content' in message and message['reasoning_content']:
                            reasoning = message['reasoning_content'].strip()
                            main_content = message.get('content', '').strip() if message.get('content') else ''

                            # Combine reasoning and main content
                            if reasoning and main_content:
                                content = f"**Reasoning:**\n{reasoning}\n\n**Response:**\n{main_content}"
                            elif reasoning:
                                content = f"**Reasoning:**\n{reasoning}\n\n**Note:** The model's response was cut off due to token limits. The reasoning shows the model's thought process before generating the final answer."
                            elif main_content:
                                content = main_content
                            else:
                                content = "No content available"
                        elif 'content' in message and message['content']:
                            content = message['content']
                        else:
                            content = str(message)
                    elif 'text' in choice:
                        content = choice['text']
                    else:
                        content = str(choice)
                else:
                    # Fallback: try to extract any text content
                    content = str(response_data)

                # Extract usage information if available
                if 'usage' in response_data:
                    usage = {
                        'input_tokens': response_data['usage'].get('prompt_tokens', 0),
                        'output_tokens': response_data['usage'].get('completion_tokens', 0),
                        'total_tokens': response_data['usage'].get('total_tokens', 0)
                    }

                result_queue.put({
                    'model': display_model,
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
            logger.error(f"Error processing manual API {manual_config}: {e}")
            result_queue.put({
                'model': f"{manual_config.get('model_name', 'Unknown')} (Manual API)",
                'status': 'error',
                'message': str(e),
                'api_url': manual_config.get('api_url', 'Unknown')
            })

    def _process_sagemaker_endpoint(self, sagemaker_config: Dict[str, Any], data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for a SageMaker endpoint.

        Supports streaming via invoke_endpoint_with_response_stream with automatic
        fallback to non-streaming invoke_endpoint if streaming is not supported.

        Args:
            sagemaker_config: SageMaker endpoint configuration
            data: Request data
            result_queue: Queue to put results
        """
        try:
            import boto3

            start_time = datetime.now()
            endpoint_name = sagemaker_config.get('endpoint_name')
            model_name = sagemaker_config.get('model_name', endpoint_name)
            stream_enabled = sagemaker_config.get('stream', True)  # Default to trying streaming

            if not endpoint_name:
                raise ValueError("endpoint_name is required for SageMaker endpoint")

            # Create SageMaker runtime client
            smr_client = boto3.client("sagemaker-runtime")

            # Prepare request
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 4096)
            temperature = data.get('temperature', 0.6)
            resize_width = data.get('resize_width')
            resize_height = data.get('resize_height')

            logger.info(f"🔍 SageMaker request - text: '{text_prompt[:50] if text_prompt else ''}...', frames: {len(frames)}, max_tokens: {max_tokens}, temperature: {temperature}, resize: {resize_width}x{resize_height}")

            # Build user content - exactly matching reference code format
            if frames:
                # VLM request with images
                # Reference format: text first, then image_url
                user_content = [
                    {"type": "text", "text": text_prompt if text_prompt else "Please describe this image."}
                ]

                # Add images (only first image for now to match reference)
                frame_base64 = frames[0]

                # Only resize if resize parameters are specified
                if resize_width or resize_height:
                    max_w = resize_width or 720
                    max_h = resize_height or 480
                    resized_base64 = self._resize_image_for_sagemaker(frame_base64, max_w, max_h)
                    image_url_base64 = f"data:image/png;base64,{resized_base64}"
                    logger.info(f"🖼️ Added resized image ({max_w}x{max_h}), base64 length: {len(resized_base64)}")
                else:
                    # No resize - use original image with detected format
                    image_format = detect_image_format(frame_base64)
                    image_url_base64 = f"data:{image_format};base64,{frame_base64}"
                    logger.info(f"🖼️ Added original image ({image_format}), base64 length: {len(frame_base64)}")

                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url_base64}
                })

                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_content}
                ]
            else:
                # Text-only request
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": text_prompt}
                ]

            # Build request payload - exactly matching reference format
            request_payload = {
                "messages": messages,
                "temperature": temperature,
                "top_p": 0.8,
                "top_k": 20,
                "image_max_pixels": 1080 ** 2,
            }

            # Only add max_tokens if specified (some models don't accept it)
            if max_tokens:
                request_payload["max_tokens"] = max_tokens

            logger.info(f"🚀 Calling SageMaker endpoint {endpoint_name}")
            logger.info(f"📦 Payload: messages count={len(messages)}, has_images={bool(frames)}")

            streaming_success = False

            # Try streaming first if enabled
            if stream_enabled:
                try:
                    # Add streaming option to payload
                    streaming_payload = {
                        **request_payload,
                        "stream": True,
                        "stream_options": {"include_usage": True}
                    }

                    response = smr_client.invoke_endpoint_with_response_stream(
                        EndpointName=endpoint_name,
                        ContentType="application/json",
                        Body=json.dumps(streaming_payload)
                    )

                    streaming_success = True
                    logger.info(f"📡 SageMaker streaming enabled for {endpoint_name}")

                    content = ""
                    usage = {}
                    buffer = SSEBuffer()

                    for event in response['Body']:
                        chunk_bytes = event.get('PayloadPart', {}).get('Bytes', b'')
                        if not chunk_bytes:
                            continue

                        for data_str in buffer.add(chunk_bytes.decode('utf-8')):
                            try:
                                chunk_data = json.loads(data_str)
                                text_chunk, is_final, chunk_usage = parse_openai_chunk(chunk_data)

                                if text_chunk:
                                    content += text_chunk
                                    result_queue.put({
                                        'model': model_name,
                                        'type': 'partial',
                                        'content': text_chunk,
                                        'accumulated_content': content
                                    })

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

                    end_time = datetime.now()
                    processing_time = (end_time - start_time).total_seconds()

                    result_queue.put({
                        'model': model_name,
                        'type': 'complete',
                        'status': 'success',
                        'result': {
                            'content': content,
                            'usage': finalize_usage(usage)
                        },
                        'metadata': {
                            'processingTime': f"{processing_time:.2f}s",
                            'endpoint_name': endpoint_name,
                            'streaming': True
                        }
                    })

                    logger.info(f"✅ SageMaker endpoint {endpoint_name} (streaming) completed in {processing_time:.2f}s")
                    return

                except Exception as e:
                    # If streaming fails (e.g., endpoint doesn't support it), fall back
                    logger.warning(f"SageMaker streaming not supported for {endpoint_name}, falling back: {e}")
                    streaming_success = False

            # Non-streaming fallback
            if not streaming_success:
                response = smr_client.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType="application/json",
                    Body=json.dumps(request_payload)
                )

                # Parse response
                response_text = response["Body"].read().decode("utf-8")
                response_json = json.loads(response_text)

                # Extract content from OpenAI-compatible response format
                content = ""
                output_tokens = 0

                if 'choices' in response_json and response_json['choices']:
                    choice = response_json['choices'][0]
                    if 'message' in choice:
                        content = choice['message'].get('content', '')

                # Get usage info if available
                if 'usage' in response_json:
                    output_tokens = response_json['usage'].get('completion_tokens', 0)
                    input_tokens = response_json['usage'].get('prompt_tokens', 0)
                else:
                    input_tokens = 0
                    output_tokens = len(content.split()) if content else 0

                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()

                total_tokens = input_tokens + output_tokens

                result = {
                    'model': model_name,
                    'status': 'success',
                    'result': {
                        'content': content,
                        'usage': {
                            'input_tokens': input_tokens,
                            'output_tokens': output_tokens,
                            'total_tokens': total_tokens
                        },
                        'raw_response': response_json
                    },
                    'metadata': {
                        'processingTime': f"{processing_time:.2f}s",
                        'endpoint_name': endpoint_name
                    }
                }

                logger.info(f"✅ SageMaker endpoint {endpoint_name} completed in {processing_time:.2f}s")
                result_queue.put(result)

        except Exception as e:
            logger.error(f"Error processing SageMaker endpoint {sagemaker_config}: {e}")
            result_queue.put({
                'model': f"{sagemaker_config.get('model_name', sagemaker_config.get('endpoint_name', 'Unknown'))} (SageMaker)",
                'status': 'error',
                'message': str(e),
                'endpoint_name': sagemaker_config.get('endpoint_name', 'Unknown')
            })
