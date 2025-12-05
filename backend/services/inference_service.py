"""Inference service for handling model predictions."""

import json
import queue
import threading
import base64
from typing import Dict, Any, List, Generator
from datetime import datetime

from core.models import model_registry
from utils import get_logger


logger = get_logger(__name__)


class InferenceService:
    """Service for handling model inference requests."""

    def __init__(self):
        """Initialize inference service."""
        self.registry = model_registry
        # Import ModelService to check deployment status for custom models
        from .model_service import ModelService
        self.model_service = ModelService()

    def _detect_image_format(self, base64_data: str) -> str:
        """Detect image format from base64 data.

        Args:
            base64_data: Base64 encoded image data

        Returns:
            MIME type (e.g., 'image/jpeg', 'image/png')
        """
        try:
            # Decode first few bytes to check magic numbers
            decoded_bytes = base64.b64decode(base64_data[:100])  # First ~75 bytes should be enough

            # Check for common image format signatures
            if decoded_bytes.startswith(b'\xff\xd8\xff'):
                return 'image/jpeg'
            elif decoded_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                return 'image/png'
            elif decoded_bytes.startswith(b'GIF87a') or decoded_bytes.startswith(b'GIF89a'):
                return 'image/gif'
            elif decoded_bytes.startswith(b'RIFF') and b'WEBP' in decoded_bytes[:12]:
                return 'image/webp'
            elif decoded_bytes.startswith(b'BM'):
                return 'image/bmp'
            else:
                # Default to JPEG if we can't detect
                return 'image/jpeg'

        except Exception:
            # If anything goes wrong, default to JPEG
            return 'image/jpeg'

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
        completed = 0
        total_models = len(threads)
        
        while completed < total_models:
            try:
                result = result_queue.get(timeout=1)
                completed += 1
                
                # Stream result back to client (SSE format)
                response_data = f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                yield response_data
                
            except queue.Empty:
                # Send heartbeat to keep connection alive (SSE format)
                yield f"data: {json.dumps({'type': 'heartbeat', 'completed': completed, 'total': total_models})}\n\n"
        
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
            
            # Prepare request body based on model type
            text_prompt = data.get('text') or data.get('prompt') or ''
            frames = data.get('frames') or data.get('images') or []
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)
            messages = data.get('messages')

            # Build message content
            message_content = []

            # If messages are provided directly, use the first user message's content
            if messages:
                for msg in messages:
                    if msg.get('role') == 'user':
                        content = msg.get('content', '')
                        if isinstance(content, str):
                            text_prompt = content
                        elif isinstance(content, list):
                            # Already structured content
                            for item in content:
                                if isinstance(item, dict):
                                    message_content.append(item)
                                elif isinstance(item, str):
                                    message_content.append({"type": "text", "text": item})
                        break

            # Add text content if we have a text prompt and haven't added content yet
            if text_prompt and not message_content:
                message_content.append({
                    "type": "text",
                    "text": text_prompt
                })

            # Ensure we have at least some content
            if not message_content:
                message_content.append({
                    "type": "text",
                    "text": "Hello"
                })
            
            # Add image content for multimodal models
            if frames and model_info.get('supports_multimodal', False):
                for frame_base64 in frames:
                    message_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",  # Assume JPEG for now
                            "data": frame_base64
                        }
                    })
            
            # Prepare request body for Anthropic models
            if 'claude' in model.lower() or 'anthropic' in model_id.lower():
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": message_content
                        }
                    ]
                }
            elif 'nova' in model.lower() or 'amazon' in model_id.lower():
                # Amazon Nova format - uses different content structure
                # Nova expects content as list of {"text": "..."} without "type" field
                nova_content = []
                for item in message_content:
                    if item.get('type') == 'text':
                        nova_content.append({"text": item.get('text', '')})
                    elif item.get('type') == 'image':
                        # Nova image format
                        source = item.get('source', {})
                        nova_content.append({
                            "image": {
                                "format": source.get('media_type', 'image/jpeg').split('/')[-1],
                                "source": {
                                    "bytes": source.get('data', '')
                                }
                            }
                        })

                # Ensure we have at least some text content
                if not nova_content:
                    nova_content.append({"text": "Hello"})

                request_body = {
                    "messages": [
                        {
                            "role": "user",
                            "content": nova_content
                        }
                    ],
                    "inferenceConfig": {
                        "maxTokens": max_tokens,
                        "temperature": temperature
                    }
                }
            else:
                # Generic format
                request_body = {
                    "messages": [
                        {
                            "role": "user", 
                            "content": message_content
                        }
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            
            logger.info(f"Calling Bedrock model {model_id} with request: {request_body}")
            
            # Call Bedrock API
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            logger.info(f"Bedrock response for {model}: {response_body}")
            
            # Extract content and usage from response
            content = ""
            usage = {}
            
            if 'claude' in model.lower() or 'anthropic' in model_id.lower():
                # Claude response format
                if 'content' in response_body and response_body['content']:
                    content = response_body['content'][0].get('text', '')
                if 'usage' in response_body:
                    usage = {
                        'input_tokens': response_body['usage'].get('input_tokens', 0),
                        'output_tokens': response_body['usage'].get('output_tokens', 0),
                        'total_tokens': response_body['usage'].get('input_tokens', 0) + response_body['usage'].get('output_tokens', 0)
                    }
            elif 'nova' in model.lower():
                # Nova response format
                if 'output' in response_body and 'message' in response_body['output']:
                    message_content = response_body['output']['message'].get('content', [])
                    if message_content and message_content[0].get('text'):
                        content = message_content[0]['text']
                if 'usage' in response_body:
                    usage = {
                        'input_tokens': response_body['usage'].get('inputTokens', 0),
                        'output_tokens': response_body['usage'].get('outputTokens', 0), 
                        'total_tokens': response_body['usage'].get('totalTokens', 0)
                    }
            
            result = {
                'model': model,
                'status': 'success',
                'result': {
                    'content': content,
                    'usage': usage,
                    'raw_response': response_body  # Include raw response for debugging
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
                    image_format = self._detect_image_format(frame_base64)

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

            # Prepare vLLM request payload
            vllm_payload = {
                "model": huggingface_repo,  # Use the actual HuggingFace repo name
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }

            logger.info(f"Calling EC2 vLLM model {model} ({huggingface_repo}) at {endpoint}")
            logger.info(f"Multimodal support: {model_info.get('supports_multimodal', False)}, Frames count: {len(frames)}")

            # Log detailed payload structure for debugging
            logger.info(f"🔍 Payload structure:")
            logger.info(f"  Model: {vllm_payload['model']}")
            logger.info(f"  Messages count: {len(vllm_payload['messages'])}")
            logger.info(f"  Content type: {type(vllm_payload['messages'][0]['content'])}")

            if isinstance(vllm_payload['messages'][0]['content'], list):
                logger.info(f"  Content parts: {len(vllm_payload['messages'][0]['content'])}")
                for i, part in enumerate(vllm_payload['messages'][0]['content']):
                    if part.get('type') == 'text':
                        logger.info(f"    Part {i}: text = '{part.get('text', '')[:50]}...'")
                    elif part.get('type') == 'image_url':
                        image_url = part.get('image_url', {}).get('url', '')
                        if image_url.startswith('data:'):
                            # Extract just the format info, not the full base64
                            prefix = image_url.split(',')[0] if ',' in image_url else image_url
                            base64_length = len(image_url.split(',')[1]) if ',' in image_url else 0
                            logger.info(f"    Part {i}: image_url = '{prefix}...' (base64 length: {base64_length})")
                        else:
                            logger.info(f"    Part {i}: image_url = '{image_url[:50]}...'")
            else:
                logger.info(f"  Content: '{str(vllm_payload['messages'][0]['content'])[:100]}...'")

            # Only log full payload in debug mode to avoid huge logs
            logger.debug(f"Full vLLM payload: {json.dumps(vllm_payload, indent=2)}")
            
            # Make HTTP request to local vLLM server
            vllm_url = f"{endpoint}/v1/chat/completions"

            try:
                logger.info(f"🔥 Making POST request to: {vllm_url}")

                response = requests.post(
                    vllm_url,
                    json=vllm_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=60  # 60 second timeout
                )

                logger.info(f"📥 Response status: {response.status_code}")
                logger.info(f"📥 Response headers: {dict(response.headers)}")

                if not response.ok:
                    logger.error(f"❌ HTTP error {response.status_code}: {response.text}")
                    logger.error(f"❌ Response content type: {response.headers.get('content-type', 'unknown')}")

                    # Try to parse error response if it's JSON
                    try:
                        error_json = response.json()
                        logger.error(f"❌ Error JSON: {json.dumps(error_json, indent=2)}")
                    except:
                        logger.error(f"❌ Raw error response: {response.text}")

                    logger.error(f"❌ Our request payload was:")
                    logger.error(f"❌   Model: {vllm_payload['model']}")
                    logger.error(f"❌   Messages: {json.dumps(vllm_payload['messages'], indent=4)}")
                    logger.error(f"❌   Other params: max_tokens={vllm_payload['max_tokens']}, temp={vllm_payload['temperature']}")

                response.raise_for_status()  # Raise exception for HTTP errors
                response_body = response.json()

                logger.info(f"vLLM response for {model}: {response_body}")

                # Extract content and usage from vLLM response (OpenAI-compatible format)
                content = ""
                usage = {}

                if 'choices' in response_body and response_body['choices']:
                    choice = response_body['choices'][0]
                    if 'message' in choice and 'content' in choice['message']:
                        content = choice['message']['content']
                    else:
                        content = f"Unexpected vLLM response format: {choice}"

                    # Extract usage information
                    if 'usage' in response_body:
                        usage = response_body['usage']
                else:
                    content = f"Unexpected vLLM response format: {response_body}"

                # Calculate response time
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds()

                result = {
                    'model': model,
                    'status': 'success',
                    'result': {
                        'content': content,
                        'usage': usage,
                        'raw_response': response_body
                    },
                    'duration_ms': response_time * 1000
                }

                result_queue.put(result)
                return

            except requests.exceptions.RequestException as req_error:
                logger.error(f"HTTP request failed for {model}: {req_error}")
                raise ValueError(f"vLLM request failed: {req_error}")
            except Exception as parse_error:
                logger.error(f"Response parsing failed for {model}: {parse_error}")
                raise ValueError(f"Response parsing failed: {parse_error}")
            
        except Exception as e:
            logger.error(f"Error processing EC2 model {model}: {e}")
            result_queue.put({
                'model': model,
                'status': 'error',
                'message': str(e)
            })
    
    def _process_manual_api(self, manual_config: Dict[str, Any], data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for a manually configured API endpoint.
        
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
            
            if not api_url or not model_name:
                raise ValueError("Both api_url and model_name are required in manual_config")
            
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
                    image_format = self._detect_image_format(frame_base64)
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
            
            # Prepare request payload
            request_payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            logger.info(f"Calling manual API {api_url} with model {model_name}")
            logger.debug(f"Request payload: {request_payload}")
            
            # Make API call
            response = requests.post(
                api_url,
                json=request_payload,
                headers={
                    "Content-Type": "application/json"
                },
                timeout=120  # 2 minute timeout
            )
            
            if not response.ok:
                raise ValueError(f"API call failed with status {response.status_code}: {response.text}")
            
            response_data = response.json()
            logger.info(f"Manual API response for {model_name}: {response_data}")
            
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
                            # If only reasoning is available, present it as the response
                            # This happens when the model hits token limits during generation
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
            
            result = {
                'model': f"{model_name} (Manual API)",
                'status': 'success',
                'result': {
                    'content': content,
                    'usage': usage,
                    'raw_response': response_data
                },
                'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                'api_url': api_url
            }
            
            result_queue.put(result)
            
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
                    image_format = self._detect_image_format(frame_base64)
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

            # Invoke endpoint using boto3 directly
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