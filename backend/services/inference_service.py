"""Inference service for handling model predictions."""

import json
import queue
import threading
from typing import Dict, Any, List, Generator
from datetime import datetime

from ..core.models import model_registry
from ..utils import get_logger


logger = get_logger(__name__)


class InferenceService:
    """Service for handling model inference requests."""
    
    def __init__(self):
        """Initialize inference service."""
        self.registry = model_registry
    
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
            elif self.registry.is_emd_model(model):
                thread = threading.Thread(
                    target=self._process_emd_model,
                    args=(model, data, result_queue)
                )
            else:
                # Unknown model
                result_queue.put({
                    'model': model,
                    'status': 'error',
                    'message': f'Unknown model: {model}'
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
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)
            
            # Build message content
            message_content = []
            
            # Add text content
            if text_prompt:
                message_content.append({
                    "type": "text",
                    "text": text_prompt
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
                # Amazon Nova format
                request_body = {
                    "messages": [
                        {
                            "role": "user",
                            "content": message_content
                        }
                    ],
                    "inferenceConfig": {
                        "max_new_tokens": max_tokens,
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
    
    def _process_emd_model(self, model: str, data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for an EMD model.
        
        Args:
            model: Model identifier
            data: Request data
            result_queue: Queue to put results
        """
        try:
            import requests
            from .model_service import ModelService
            model_service = ModelService()
            
            # Check if model is deployed
            deployment_status = model_service.get_emd_deployment_status(model)
            
            if deployment_status.get('status') != 'deployed':
                result_queue.put({
                    'model': model,
                    'status': 'not_deployed',
                    'message': f'Model {model} is not deployed: {deployment_status.get("message", "Unknown status")}'
                })
                return
            
            start_time = datetime.now()
            
            # Get model information
            model_info = self.registry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Model {model} not found in registry")
            
            # Get model path for EMD lookup
            model_path = model_info.get('model_path', model)
            
            # Prepare request data for EMD
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)
            
            # Build messages array for EMD inference
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
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_base64}"
                        }
                    })
            
            messages.append({
                "role": "user",
                "content": content_parts
            })
            
            # Prepare EMD request payload
            emd_payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False  # Use non-streaming for now
            }
            
            logger.info(f"Calling EMD model {model} with payload: {emd_payload}")
            
            # Try to get EMD endpoint URL and make inference call
            actual_endpoint_name = None
            try:
                import boto3
                from botocore.exceptions import ClientError, NoCredentialsError

                # Get the deployment tag for this model
                deployment_tag = deployment_status.get('tag')
                if not deployment_tag:
                    raise ValueError(f"No deployment tag found for model {model}")

                # Get endpoint name from EMD deployment info
                # Based on the emd status output, the actual endpoint name uses model_path:
                # EMD-Model-{model_path_converted}-{tag}-endpoint
                # Convert model_path to lowercase and replace special chars with hyphens
                model_name_for_endpoint = model_path.lower().replace('_', '-').replace('.', '-')
                actual_endpoint_name = f"EMD-Model-{model_name_for_endpoint}-{deployment_tag}-endpoint"

                logger.info(f"Using EMD endpoint: {actual_endpoint_name}")

                # Use boto3 SageMaker Runtime client directly
                runtime_client = boto3.client('sagemaker-runtime', region_name='us-west-2')

                # Call EMD endpoint via SageMaker Runtime
                response = runtime_client.invoke_endpoint(
                    EndpointName=actual_endpoint_name,
                    ContentType='application/json',
                    Body=json.dumps(emd_payload)
                )

                # Parse response
                response_body = json.loads(response['Body'].read().decode('utf-8'))
                logger.info(f"EMD response for {model}: {response_body}")
                
            except Exception as emd_error:
                logger.warning(f"EMD direct call failed for {model}: {emd_error}")
                
                # Try to use the actual deployed endpoint from EMD status
                try:
                    from emd.sdk.status import get_model_status
                    
                    # Get the current EMD status to find the actual endpoint name
                    status = get_model_status()
                    actual_endpoint_name = None
                    
                    # Look for the deployed model in the EMD status
                    for model_entry in status.get("completed", []):
                        model_id = model_entry.get("model_id")
                        model_tag = model_entry.get("model_tag")
                        stack_status = model_entry.get("stack_status", "")
                        
                        if model_id and model_path in model_id and "CREATE_COMPLETE" in stack_status:
                            # Construct the endpoint name from EMD conventions using actual model_id
                            # Convert model_id to lowercase and replace special chars with hyphens
                            model_name_for_endpoint = model_id.lower().replace('_', '-').replace('.', '-')
                            actual_endpoint_name = f"EMD-Model-{model_name_for_endpoint}-{model_tag}-endpoint"
                            logger.info(f"Constructed endpoint name: {actual_endpoint_name} from model_id: {model_id}")
                            break
                    
                    if not actual_endpoint_name:
                        raise ValueError(f"Could not determine endpoint name for {model}")
                    
                    logger.info(f"Trying actual EMD endpoint: {actual_endpoint_name}")
                    print(f"🔍 DEBUG: Attempting to invoke endpoint: {actual_endpoint_name}")
                    
                    # Use boto3 SageMaker Runtime client with actual endpoint name
                    runtime_client = boto3.client('sagemaker-runtime', region_name='us-west-2')
                    
                    response = runtime_client.invoke_endpoint(
                        EndpointName=actual_endpoint_name,
                        ContentType='application/json',
                        Body=json.dumps(emd_payload)
                    )
                    
                    # Parse response
                    response_body = json.loads(response['Body'].read().decode('utf-8'))
                    logger.info(f"EMD response for {model}: {response_body}")
                    
                except Exception as final_error:
                    logger.error(f"All EMD methods failed for {model}: {final_error}")
                    raise ValueError(f"EMD inference failed: {final_error}")
            
            # Extract content and usage from EMD response
            content = ""
            usage = {}
            
            # Handle different EMD response formats
            if isinstance(response_body, dict):
                if 'choices' in response_body and response_body['choices']:
                    # OpenAI-compatible format
                    choice = response_body['choices'][0]
                    if 'message' in choice:
                        message = choice['message']
                        # Check for reasoning_content first (EMD Qwen models)
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
                elif 'generated_text' in response_body:
                    # Hugging Face format
                    content = response_body['generated_text']
                elif 'outputs' in response_body:
                    # Alternative format
                    content = response_body['outputs'][0] if response_body['outputs'] else ""
                else:
                    # Fallback: convert entire response to string
                    content = str(response_body)
                
                # Extract usage information
                if 'usage' in response_body:
                    usage = {
                        'input_tokens': response_body['usage'].get('prompt_tokens', 0),
                        'output_tokens': response_body['usage'].get('completion_tokens', 0),
                        'total_tokens': response_body['usage'].get('total_tokens', 0)
                    }
            else:
                # Handle string response
                content = str(response_body)
            
            result = {
                'model': model,
                'status': 'success',
                'result': {
                    'content': content,
                    'usage': usage,
                    'raw_response': response_body  # Include raw response for debugging
                },
                'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                'deployment_tag': deployment_status.get('tag')
            }
            
            result_queue.put(result)
            
        except Exception as e:
            logger.error(f"Error processing EMD model {model}: {e}")
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
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_base64}"
                        }
                    })
            
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
            start_time = datetime.now()
            endpoint_name = sagemaker_config.get('endpoint_name')
            model_name = sagemaker_config.get('model_name', endpoint_name)

            if not endpoint_name:
                raise ValueError("endpoint_name is required for SageMaker endpoint")

            # Import SageMaker SDK
            try:
                import boto3
                import sagemaker
                from sagemaker import serializers, deserializers
            except ImportError:
                raise ImportError("SageMaker SDK is required. Please install: pip install sagemaker boto3")

            # Get SageMaker session and role
            try:
                role = sagemaker.get_execution_role()
                sess = sagemaker.session.Session()
            except Exception:
                # Fallback for environments without SageMaker execution role
                sess = sagemaker.session.Session()
                role = None

            # Create predictor
            predictor = sagemaker.Predictor(
                endpoint_name=endpoint_name,
                sagemaker_session=sess,
                serializer=serializers.JSONSerializer()
            )

            # Prepare request
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 4096)
            temperature = data.get('temperature', 0.6)

            # For text-only models, we can apply chat template formatting on our side
            # This matches the format from your working example
            # if 'qwen' in endpoint_name.lower() or 'coder' in endpoint_name.lower():
            #     # Build messages for chat template
            #     messages = [
            #         {"role": "system", "content": "You are a helpful assistant."},
            #         {"role": "user", "content": text_prompt}
            #     ]

            #     # Apply a simple chat template formatting (Qwen style)
            #     formatted_prompt = ""
            #     for msg in messages:
            #         if msg["role"] == "system":
            #             formatted_prompt += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
            #         elif msg["role"] == "user":
            #             formatted_prompt += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
            #     formatted_prompt += "<|im_start|>assistant\n"

            #     request_payload = {
            #         "inputs": formatted_prompt,
            #         "parameters": {
            #             "max_new_tokens": max_tokens,
            #             "temperature": temperature,
            #             "top_p": 0.9,
            #             "include_stop_str_in_output": False,
            #             "ignore_eos": False,
            #             "repetition_penalty": 1.0,
            #             "details": True
            #         }
            #     }
            # else:
            # Generic format for other models
            request_payload = {
                "inputs": text_prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "include_stop_str_in_output": False,
                    "ignore_eos": False,
                    "repetition_penalty": 1.0,
                    "details": True
                }
            }

            # Add image frames if provided - for multimodal models
            if frames:
                # Some endpoints expect 'images' instead of 'frames'
                request_payload["images"] = frames
                request_payload["mediaType"] = data.get("mediaType", "image")

            logger.info(f"🚀 Calling SageMaker endpoint {endpoint_name} with {len(frames)} frames")
            logger.debug(f"Request payload: {json.dumps(request_payload, indent=2)}")

            # Make prediction
            response = predictor.predict(request_payload)

            # Parse response
            if isinstance(response, bytes):
                response_text = response.decode('utf-8')
            else:
                response_text = str(response)

            try:
                response_json = json.loads(response_text)
                if 'generated_text' in response_json:
                    content = response_json['generated_text']
                else:
                    content = response_text

                if 'generated_tokens' in response_json:
                    output_tokens = response_json['generated_tokens']
                else:
                    # Fallback: estimate tokens based on text length
                    output_tokens = len(content.split()) if content else 0

            except json.JSONDecodeError:
                content = response_text
                # Estimate tokens for raw text response
                output_tokens = len(response_text.split()) if response_text else 0

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Estimate input tokens from prompt length
            prompt_text = data.get('text', '')
            input_tokens = len(prompt_text.split()) if prompt_text else 0
            total_tokens = input_tokens + output_tokens

            result = {
                'model': model_name,
                'status': 'success',
                'result': {
                    'content': content,
                    'usage': {
                        'input_tokens': input_tokens,
                        'prompt_tokens': input_tokens,  # Alternative field name
                        'output_tokens': output_tokens,
                        'completion_tokens': output_tokens,  # Alternative field name
                        'total_tokens': total_tokens
                    },
                    'raw_response': response_json if 'response_json' in locals() else None
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