"""Inference service for handling model predictions."""

import json
import os
import queue
import threading
import time
from typing import Dict, Any, List, Generator, Optional
from datetime import datetime

from ..core.models import model_registry
from ..utils import get_logger, get_account_id
from ..utils.emd import resolve_deployment_api_url
from ..config import get_config

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError as exc:  # pragma: no cover - defensive guard
    raise ImportError("botocore is required for Bedrock interactions. Please install boto3/botocore.") from exc


logger = get_logger(__name__)


class InferenceService:
    """Service for handling model inference requests."""
    
    def __init__(self):
        """Initialize inference service."""
        self.registry = model_registry
        self._aws_account_id: Optional[str] = None
        delay_ms = os.environ.get('STREAMING_CHUNK_DELAY_MS')
        try:
            self._chunk_delay_seconds = max(float(delay_ms) / 1000.0, 0.0) if delay_ms is not None else 0.05
        except (TypeError, ValueError):
            self._chunk_delay_seconds = 0.05

    
    def multi_inference(self, data: Dict[str, Any]) -> Generator[str, None, None]:
        """Run inference on multiple models simultaneously.
        
        Args:
            data: Request data containing models and inference parameters
            
        Yields:
            JSON strings with inference results
        """
        models = data.get('models', [])
        manual_config = data.get('manual_config')
        
        if not models and not manual_config:
            yield f"data: {json.dumps({'error': 'No models or manual configuration specified', 'status': 'error'})}\n\n"
            return

        result_queue = queue.Queue()
        threads = []

        total_workers = len(models) + (1 if manual_config else 0)
        yield f"data: {json.dumps({'type': 'status', 'status': 'initializing', 'total': total_workers}, ensure_ascii=False)}\n\n"
        
        # Handle manual configuration
        if manual_config:
            thread = threading.Thread(
                target=self._process_manual_api,
                args=(manual_config, data, result_queue)
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
            elif self.registry.is_external_model(model):
                thread = threading.Thread(
                    target=self._process_external_model,
                    args=(model, data, result_queue)
                )
            else:
                # Unknown model
                result_queue.put({
                    'type': 'error',
                    'model': model,
                    'label': model,
                    'status': 'error',
                    'message': f'Unknown model: {model}'
                })
                continue
            
            threads.append(thread)
            thread.start()
        
        # Wait for results and stream them back
        completed = 0
        total_models = len(threads)

        logger.info(f"Starting to wait for {total_models} models: {models}")

        while completed < total_models:
            try:
                result = result_queue.get(timeout=1)
            except queue.Empty:
                # Send heartbeat to keep connection alive (SSE format)
                yield f"data: {json.dumps({'type': 'heartbeat', 'completed': completed, 'total': total_models})}\n\n"
                continue

            event_type = result.get('type') if isinstance(result, dict) else None

            if event_type == 'chunk':
                # Forward streaming token update without marking model complete
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                continue

            completed += 1
            if isinstance(result, dict) and not event_type:
                result = {**result, 'type': 'result'}

            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)
        
        # Send completion signal
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    def _get_aws_account_id(self) -> Optional[str]:
        """Fetch and cache the AWS account ID for Bedrock inference profiles."""
        if self._aws_account_id:
            return self._aws_account_id

        config = None
        try:
            config = get_config()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Failed to access config manager when fetching account ID: %s", exc)

        account_id: Optional[str] = None
        if config:
            account_id = config.get('aws.account_id')

        if not account_id:
            session = None
            try:
                session = self._get_boto_session()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("Unable to create boto session for account lookup: %s", exc)

            if session:
                try:
                    sts_client = session.client('sts')
                    response = sts_client.get_caller_identity()
                    account_id = response.get('Account')
                except Exception as exc:  # pragma: no cover - fallback
                    logger.debug("Failed to fetch AWS account via session: %s", exc)

            if not account_id:
                account_id = get_account_id()

            if account_id and config:
                try:
                    config.set('aws.account_id', account_id)
                except Exception as exc:  # pragma: no cover - best effort cache
                    logger.debug("Unable to persist AWS account ID in config: %s", exc)

        self._aws_account_id = account_id
        return account_id

    def _get_boto_session(self, region: Optional[str] = None):
        """Create or reuse a boto3 session with configured credentials."""
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - defensive guard
            raise ImportError(
                "boto3 is required for Bedrock operations. Please install: pip install boto3"
            ) from exc

        config = None
        try:
            config = get_config()
        except Exception as conf_error:  # pragma: no cover
            logger.debug("Failed to access configuration while building boto session: %s", conf_error)

        profile_name = os.environ.get('AWS_PROFILE')
        access_key = None
        secret_key = None
        session_token = None
        default_region = None

        if config:
            profile_name = config.get('aws.profile') or profile_name
            access_key = config.get('aws.access_key_id')
            secret_key = config.get('aws.secret_access_key')
            session_token = config.get('aws.session_token')
            default_region = config.get('aws.region')

        target_region = region or default_region or 'us-east-1'

        session_kwargs: Dict[str, Any] = {'region_name': target_region}

        if access_key and secret_key:
            session_kwargs.update({
                'aws_access_key_id': access_key,
                'aws_secret_access_key': secret_key
            })
            if session_token:
                session_kwargs['aws_session_token'] = session_token
        elif profile_name:
            session_kwargs['profile_name'] = profile_name

        session = boto3.session.Session(**session_kwargs)

        # Ensure credentials are actually resolved; otherwise downstream calls raise cryptic errors.
        if session.get_credentials() is None:
            raise NoCredentialsError()

        return session

    @staticmethod
    def _merge_usage_dicts(base: Optional[Dict[str, Any]], latest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge token usage dictionaries, preferring the most recent non-null values."""
        merged: Dict[str, Any] = (base or {}).copy()

        if not latest:
            return merged

        for key in ('input_tokens', 'output_tokens', 'total_tokens'):
            value = latest.get(key)
            if value is not None:
                merged[key] = value

        return merged

    def _extract_usage_from_bedrock_event(self, event_json: Dict[str, Any]) -> Dict[str, Any]:
        """Extract token usage information from a Bedrock streaming event if available."""
        usage_candidates = []

        if isinstance(event_json.get('usage'), dict):
            usage_candidates.append(event_json['usage'])

        # Check metadata.usage for Nova models
        metadata = event_json.get('metadata')
        if isinstance(metadata, dict) and isinstance(metadata.get('usage'), dict):
            usage_candidates.append(metadata['usage'])

        delta = event_json.get('delta')
        if isinstance(delta, dict) and isinstance(delta.get('usage'), dict):
            usage_candidates.append(delta['usage'])

        for candidate in usage_candidates:
            input_tokens = (candidate.get('input_tokens') or
                            candidate.get('prompt_tokens') or
                            candidate.get('inputTokens'))
            output_tokens = (candidate.get('output_tokens') or
                             candidate.get('completion_tokens') or
                             candidate.get('outputTokens'))
            total_tokens = (candidate.get('total_tokens') or
                            candidate.get('totalTokens'))

            if total_tokens is None and (input_tokens is not None or output_tokens is not None):
                total_tokens = (input_tokens or 0) + (output_tokens or 0)

            if any(value is not None for value in (input_tokens, output_tokens, total_tokens)):
                return {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': total_tokens
                }

        return {}

    def _extract_text_from_bedrock_event(self, event_json: Dict[str, Any]) -> List[str]:
        """Extract textual deltas from a Bedrock streaming event."""
        if not isinstance(event_json, dict):
            return []

        segments: List[str] = []
        event_type = event_json.get('type')

        # Handle Nova's camelCase format: {"contentBlockDelta": {"delta": {"text": "..."}}}
        content_block_delta = event_json.get('contentBlockDelta')
        if isinstance(content_block_delta, dict):
            delta = content_block_delta.get('delta')
            if isinstance(delta, dict) and isinstance(delta.get('text'), str):
                segments.append(delta['text'])
                return segments  # Nova format found, return immediately

        # Handle Claude's format
        delta = event_json.get('delta')
        if event_type == 'content_block_delta' and isinstance(delta, dict):
            if delta.get('type') == 'text_delta' and isinstance(delta.get('text'), str):
                segments.append(delta['text'])
        elif event_type in ('output_text_delta', 'composed_text_delta'):
            if isinstance(delta, dict) and isinstance(delta.get('text'), str):
                segments.append(delta['text'])
            elif isinstance(event_json.get('text'), str):
                segments.append(event_json['text'])
        elif isinstance(event_json.get('text'), str) and event_type not in (
            'message_start', 'message_delta', 'message_stop', 'content_block_start', 'content_block_stop',
            'messageStart', 'messageDelta', 'messageStop', 'contentBlockStart', 'contentBlockStop',
            'contentBlockStop'
        ):
            segments.append(event_json['text'])

        content = event_json.get('content')
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'text' and isinstance(block.get('text'), str):
                        segments.append(block['text'])
                    elif isinstance(block.get('text'), str) and event_type in ('output_text', 'outputText'):
                        segments.append(block['text'])

        # Remove duplicates while preserving order
        unique_segments: List[str] = []
        seen = set()
        for segment in segments:
            if segment and segment not in seen:
                unique_segments.append(segment)
                seen.add(segment)

        return unique_segments

    @staticmethod
    def _normalize_usage_payload(usage_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize usage payload keys to the standard input/output/total_tokens fields."""
        if not isinstance(usage_payload, dict):
            return {}

        input_tokens = (usage_payload.get('input_tokens') or
                        usage_payload.get('prompt_tokens') or
                        usage_payload.get('inputTokens') or
                        usage_payload.get('promptTokens'))

        output_tokens = (usage_payload.get('output_tokens') or
                         usage_payload.get('completion_tokens') or
                         usage_payload.get('outputTokens') or
                         usage_payload.get('completionTokens'))

        total_tokens = (usage_payload.get('total_tokens') or
                        usage_payload.get('totalTokens'))

        if total_tokens is None and (input_tokens is not None or output_tokens is not None):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        normalized: Dict[str, Any] = {}
        if input_tokens is not None:
            normalized['input_tokens'] = input_tokens
        if output_tokens is not None:
            normalized['output_tokens'] = output_tokens
        if total_tokens is not None:
            normalized['total_tokens'] = total_tokens

        return normalized

    @staticmethod
    def _extract_text_from_openai_event(event_json: Dict[str, Any]) -> List[str]:
        """Extract textual segments from an OpenAI-compatible streaming event."""
        if not isinstance(event_json, dict):
            return []

        segments: List[str] = []

        choices = event_json.get('choices')
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue

                delta = choice.get('delta')
                if isinstance(delta, dict):
                    content = delta.get('content')
                    if isinstance(content, str) and content:
                        segments.append(content)

                    text_value = delta.get('text')
                    if isinstance(text_value, str) and text_value:
                        segments.append(text_value)

                    reasoning_content = delta.get('reasoning_content')
                    if isinstance(reasoning_content, str) and reasoning_content:
                        # EMD Qwen models send reasoning_content as a string
                        segments.append(reasoning_content)
                    elif isinstance(reasoning_content, list):
                        # Some models send it as a list of objects
                        for entry in reasoning_content:
                            if isinstance(entry, dict):
                                text_piece = entry.get('text')
                                if isinstance(text_piece, str) and text_piece:
                                    segments.append(text_piece)

                # Some providers stream using `text` at the top level of the choice
                choice_text = choice.get('text')
                if isinstance(choice_text, str) and choice_text:
                    segments.append(choice_text)

                message = choice.get('message')
                if isinstance(message, dict):
                    message_content = message.get('content')
                    if isinstance(message_content, str) and message_content:
                        segments.append(message_content)

        # Fallback keys that occasionally appear
        output_text = event_json.get('output_text')
        if isinstance(output_text, str) and output_text:
            segments.append(output_text)

        content_field = event_json.get('content')
        if isinstance(content_field, str) and content_field:
            segments.append(content_field)

        reasoning_field = event_json.get('reasoning_content')
        if isinstance(reasoning_field, list):
            for entry in reasoning_field:
                if isinstance(entry, dict):
                    text_piece = entry.get('text')
                    if isinstance(text_piece, str) and text_piece:
                        segments.append(text_piece)

        # Deduplicate while preserving order
        unique_segments: List[str] = []
        seen = set()
        for segment in segments:
            if segment and segment not in seen:
                unique_segments.append(segment)
                seen.add(segment)

        return unique_segments

    def _delay_stream_chunk(self) -> None:
        """Optional throttling between streaming chunk events for UI pacing."""
        if getattr(self, "_chunk_delay_seconds", 0.0) > 0:
            time.sleep(self._chunk_delay_seconds)

    def _stream_sagemaker_endpoint(
        self,
        runtime_client: Any,
        endpoint_name: str,
        payload: Dict[str, Any],
        model_key: str,
        start_time: datetime,
        result_queue: queue.Queue,
        provider: str = 'emd',
        label: Optional[str] = None
    ) -> bool:
        """Attempt to stream inference from a SageMaker endpoint. Returns True if streaming succeeded."""
        display_label = label or model_key
        stream_response = None
        try:
            stream_response = runtime_client.invoke_endpoint_with_response_stream(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )

            stream_body = stream_response.get('Body') if isinstance(stream_response, dict) else None

            aggregated_chunks: List[str] = []
            usage_info: Dict[str, Any] = {}
            raw_events: List[Any] = []

            if stream_body:
                for event in stream_body:
                    payload_bytes = None
                    if isinstance(event, dict):
                        payload_part = (
                            event.get('PayloadPart')
                            or event.get('payloadPart')
                            or event.get('chunk')
                            or event.get('Chunk')
                        )
                        if isinstance(payload_part, dict):
                            payload_bytes = (
                                payload_part.get('Bytes')
                                or payload_part.get('bytes')
                                or payload_part.get('value')
                            )

                    if not payload_bytes:
                        continue

                    decoded_payload = payload_bytes.decode('utf-8', errors='ignore')
                    if not decoded_payload.strip():
                        continue

                    lines = decoded_payload.splitlines()
                    if not lines:
                        lines = [decoded_payload]

                    for raw_line in lines:
                        stripped = raw_line.strip()
                        if not stripped or stripped.startswith(':'):
                            continue

                        payload_str = stripped[5:].strip() if stripped.startswith('data:') else stripped
                        if not payload_str or payload_str == '[DONE]':
                            continue

                        try:
                            event_json = json.loads(payload_str)
                            raw_events.append(event_json)
                        except json.JSONDecodeError:
                            raw_events.append(payload_str)
                            aggregated_chunks.append(payload_str)
                            result_queue.put({
                                'type': 'chunk',
                                'model': model_key,
                                'label': display_label,
                                'status': 'streaming',
                                'delta': payload_str,
                                'provider': provider
                            })
                            self._delay_stream_chunk()
                            continue

                        text_segments = self._extract_text_from_openai_event(event_json)
                        for segment in text_segments:
                            aggregated_chunks.append(segment)
                            result_queue.put({
                                'type': 'chunk',
                                'model': model_key,
                                'label': display_label,
                                'status': 'streaming',
                                'delta': segment,
                                'provider': provider
                            })
                            self._delay_stream_chunk()

                        usage_info = self._merge_usage_dicts(
                            usage_info,
                            self._normalize_usage_payload(event_json.get('usage'))
                        )

            final_content = ''.join(aggregated_chunks)
            if not final_content and raw_events:
                last_event = raw_events[-1]
                if isinstance(last_event, dict):
                    final_content = json.dumps(last_event, ensure_ascii=False)
                else:
                    final_content = str(last_event)

            result_queue.put({
                'type': 'result',
                'model': model_key,
                'label': display_label,
                'status': 'success',
                'result': {
                    'content': final_content,
                    'usage': usage_info,
                    'raw_response': raw_events
                },
                'duration_ms': (datetime.now() - start_time).total_seconds() * 1000
            })
            return True
        except Exception as stream_error:
            logger.warning(
                "Streaming invocation failed for %s on endpoint %s: %s",
                display_label,
                endpoint_name,
                stream_error,
                exc_info=True
            )
            return False
        finally:
            if stream_response:
                body = stream_response.get('Body') if isinstance(stream_response, dict) else None
                if hasattr(body, 'close'):
                    try:
                        body.close()
                    except Exception:  # pragma: no cover - best effort
                        pass

    def _process_bedrock_model(self, model: str, data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for a Bedrock model."""
        display_label = model
        try:
            start_time = datetime.now()

            # Resolve configuration
            config = None
            try:
                config = get_config()
            except Exception as conf_error:  # pragma: no cover - defensive guard
                logger.debug("Failed to access configuration while preparing Bedrock request: %s", conf_error)

            # FORCE us-east-1 for Bedrock - where US inference profiles are available
            bedrock_region = 'us-east-1'

            try:
                session = self._get_boto_session(bedrock_region)
                bedrock_client = session.client('bedrock-runtime', region_name=bedrock_region)
                try:
                    identity = session.client('sts').get_caller_identity()
                    logger.info("Using AWS identity %s for model %s", identity.get('Arn'), model)
                except Exception as sts_error:  # pragma: no cover - diagnostics only
                    logger.debug("Unable to fetch STS caller identity: %s", sts_error)
            except NoCredentialsError:
                raise ValueError(
                    "AWS credentials not configured. Please export AWS_PROFILE or set AWS_ACCESS_KEY_ID / "
                    "AWS_SECRET_ACCESS_KEY (optionally AWS_SESSION_TOKEN) before starting the backend."
                )
            except Exception as client_error:
                raise ValueError(f"Failed to initialize Bedrock client: {client_error}")

            # Get model configuration
            model_info = self.registry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Model {model} not found in registry")

            model_id = model_info.get('model_id')
            if not model_id:
                raise ValueError(f"No model_id found for model {model}")

            display_label = model_info.get('name', model)

            # Prepare request body based on model type
            text_prompt = data.get('text', '') or data.get('message', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)

            message_content = []

            if text_prompt:
                message_content.append({"type": "text", "text": text_prompt})

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

            if 'claude' in model.lower() or 'anthropic' in model_id.lower():
                # Use simple string format for text-only, array format for multimodal
                if len(message_content) == 1 and message_content[0].get('type') == 'text':
                    content = message_content[0]['text']  # Simple string for text-only
                else:
                    content = message_content  # Array format for multimodal
                
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": content
                        }
                    ]
                }
            elif 'nova' in model.lower() or 'amazon' in model_id.lower():
                # Nova requires array format for content, no 'type' field for text-only
                if len(message_content) == 1 and message_content[0].get('type') == 'text':
                    # Text-only: use simplified format without 'type' field
                    nova_content = [{"text": message_content[0]['text']}]
                else:
                    # Multimodal: keep full format
                    nova_content = message_content
                
                request_body = {
                    "messages": [
                        {
                            "role": "user",
                            "content": nova_content
                        }
                    ],
                    "inferenceConfig": {
                        "max_new_tokens": max_tokens,
                        "temperature": temperature
                    }
                }
            else:
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

            request_json = json.dumps(request_body)

            invoke_kwargs: Dict[str, Any] = {
                'body': request_json,
                'contentType': 'application/json',
                'accept': 'application/json'
            }

            logger.info(
                "Calling Bedrock model %s (%s) in region %s with request: %s",
                model_id,
                model,
                bedrock_region,
                request_body
            )


            streaming_supported = model_info.get('supports_streaming', True)
            stream_response = None

            if streaming_supported:
                try:
                    # Use the exact working pattern for streaming too
                    stream_response = bedrock_client.invoke_model_with_response_stream(
                        modelId=model_id,
                        body=request_json,
                        contentType='application/json',
                        accept='application/json'
                    )
                    stream_body = stream_response.get('body') if isinstance(stream_response, dict) else None

                    aggregated_chunks: List[str] = []
                    usage_info: Dict[str, Any] = {}
                    raw_events: List[Any] = []

                    if stream_body:
                        for event in stream_body:
                            payload_bytes = None
                            if isinstance(event, dict):
                                if 'chunk' in event and isinstance(event['chunk'], dict):
                                    payload_bytes = event['chunk'].get('bytes')
                                elif 'payloadPart' in event and isinstance(event['payloadPart'], dict):
                                    payload_bytes = event['payloadPart'].get('bytes')

                            if not payload_bytes:
                                continue

                            decoded_payload = payload_bytes.decode('utf-8')
                            if not decoded_payload.strip():
                                continue

                            lines = decoded_payload.splitlines()
                            if not lines:
                                lines = [decoded_payload]

                            for piece in lines:
                                piece = piece.strip()
                                if not piece:
                                    continue

                                try:
                                    event_json = json.loads(piece)
                                    raw_events.append(event_json)
                                except json.JSONDecodeError:
                                    raw_events.append(piece)
                                    aggregated_chunks.append(piece)
                                    result_queue.put({
                                        'type': 'chunk',
                                        'model': model,
                                        'label': display_label,
                                        'status': 'streaming',
                                        'delta': piece,
                                        'provider': 'bedrock'
                                    })
                                    self._delay_stream_chunk()
                                    continue

                                text_segments = self._extract_text_from_bedrock_event(event_json)
                                for segment in text_segments:
                                    aggregated_chunks.append(segment)
                                    result_queue.put({
                                        'type': 'chunk',
                                        'model': model,
                                        'label': display_label,
                                        'status': 'streaming',
                                        'delta': segment,
                                        'provider': 'bedrock'
                                    })
                                    self._delay_stream_chunk()
                                    # Add small delay for visible streaming
                                    import time
                                    time.sleep(0.05)

                                usage_info = self._merge_usage_dicts(
                                    usage_info,
                                    self._extract_usage_from_bedrock_event(event_json)
                                )

                    final_content = ''.join(aggregated_chunks)
                    if not final_content and raw_events:
                        last_event = raw_events[-1]
                        if isinstance(last_event, dict):
                            final_content = json.dumps(last_event, ensure_ascii=False)
                        else:
                            final_content = str(last_event)

                    result_queue.put({
                        'type': 'result',
                        'model': model,
                        'label': display_label,
                        'status': 'success',
                        'result': {
                            'content': final_content,
                            'usage': usage_info,
                            'raw_response': raw_events
                        },
                        'duration_ms': (datetime.now() - start_time).total_seconds() * 1000
                    })
                    return
                except Exception as stream_error:
                    logger.warning(
                        "Bedrock streaming invocation failed for %s (%s); falling back to standard invocation: %s",
                        model,
                        model_id,
                        stream_error,
                        exc_info=True
                    )
                finally:
                    if isinstance(stream_response, dict):
                        body = stream_response.get('body')
                        if hasattr(body, 'close'):
                            try:
                                body.close()
                            except Exception:
                                pass

            # Fallback to non-streaming invocation
            # Use the exact working pattern
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=request_json,
                contentType='application/json',
                accept='application/json'
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            logger.info(f"Bedrock response for {model}: {response_body}")

            content = ""
            usage = {}

            if 'claude' in model.lower() or 'anthropic' in model_id.lower():
                if 'content' in response_body and response_body['content']:
                    content_blocks = response_body['content']
                    if isinstance(content_blocks, list):
                        text_parts = [block.get('text', '') for block in content_blocks if block.get('type') == 'text']
                        content = ''.join(text_parts) if text_parts else content
                if 'usage' in response_body:
                    usage = {
                        'input_tokens': response_body['usage'].get('input_tokens', 0),
                        'output_tokens': response_body['usage'].get('output_tokens', 0),
                        'total_tokens': response_body['usage'].get('input_tokens', 0) + response_body['usage'].get('output_tokens', 0)
                    }
            elif 'nova' in model.lower() or 'amazon' in model_id.lower():
                # Nova response structure: output.message.content[] or metadata.usage
                if 'output' in response_body and 'message' in response_body['output']:
                    content_entries = response_body['output']['message'].get('content', [])
                    if isinstance(content_entries, list):
                        text_values = [item.get('text') for item in content_entries if item.get('text')]
                        if text_values:
                            content = ''.join(text_values)
                
                # Nova usage can be in 'usage' or 'metadata.usage'
                usage_data = response_body.get('usage') or (response_body.get('metadata', {}).get('usage'))
                if usage_data:
                    usage = {
                        'input_tokens': usage_data.get('inputTokens', 0),
                        'output_tokens': usage_data.get('outputTokens', 0),
                        'total_tokens': usage_data.get('totalTokens', 0)
                    }
                    if not usage.get('total_tokens'):
                        usage['total_tokens'] = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            else:
                content = response_body.get('output_text') or response_body.get('completion') or str(response_body)
                if 'usage' in response_body:
                    usage = {
                        'input_tokens': response_body['usage'].get('prompt_tokens', 0),
                        'output_tokens': response_body['usage'].get('completion_tokens', 0),
                        'total_tokens': response_body['usage'].get('total_tokens', 0)
                    }

            if not content:
                content = str(response_body)

            result = {
                'type': 'result',
                'model': model,
                'label': display_label,
                'status': 'success',
                'result': {
                    'content': content,
                    'usage': usage,
                    'raw_response': response_body
                },
                'duration_ms': (datetime.now() - start_time).total_seconds() * 1000
            }

            result_queue.put(result)

        except ClientError as client_error:
            logger.error(f"Bedrock client error for model {model}: {client_error}")
            error_message = client_error.response['Error'].get('Message', str(client_error))
            result_queue.put({
                        'type': 'error',
                        'model': model,
                        'label': display_label,
                        'status': 'error',
                        'message': error_message
                    })
        except Exception as e:
            logger.error(f"Error processing Bedrock model {model}: {e}")
            result_queue.put({
                'type': 'error',
                'model': model,
                'label': display_label,
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
        display_label = model
        try:
            import requests
            from .model_service import ModelService
            model_service = ModelService()
            
            # Check if model is deployed
            deployment_status = model_service.get_emd_deployment_status(model)

            if deployment_status.get('status') != 'deployed':
                result_queue.put({
                    'model': model,
                    'label': display_label,
                    'status': 'not_deployed',
                    'message': f'Model {model} is not deployed: {deployment_status.get("message", "Unknown status")}'
                })
                return
            
            start_time = datetime.now()
            
            # Get model information
            model_info = self.registry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Model {model} not found in registry")
            display_label = model_info.get('name', model)
            
            # Get model path for EMD lookup
            model_path = model_info.get('model_path', model)

            endpoint_url = deployment_status.get('endpoint')
            endpoint_from_lookup = False
            if not endpoint_url and deployment_status.get('tag'):
                try:
                    resolved_endpoint, used_fallback = resolve_deployment_api_url(
                        model_path,
                        deployment_status.get('tag')
                    )
                    if not used_fallback:
                        endpoint_url = resolved_endpoint
                        endpoint_from_lookup = True
                except RuntimeError as lookup_error:
                    logger.debug(
                        "Unable to resolve EMD streaming endpoint for %s: %s",
                        model,
                        lookup_error
                    )

            if endpoint_url:
                # Include deployment tag in model name for EMD endpoints (but not for external deployments)
                deployment_tag = deployment_status.get('tag')
                # Don't append 'external' tag to model name - it's from external registration
                if deployment_tag and deployment_tag != 'external':
                    full_model_name = f"{model_path}/{deployment_tag}"
                else:
                    full_model_name = model_path
                
                manual_config = {
                    'api_url': endpoint_url,
                    'model_name': full_model_name,
                    'label': display_label,
                    'model_key': model,
                    'allow_fallback': True
                }
                try:
                    logger.info(
                        "Streaming EMD model %s via OpenAI-compatible endpoint %s%s",
                        model,
                        endpoint_url,
                        " (resolved)" if endpoint_from_lookup else ""
                    )
                    self._process_manual_api(manual_config, data, result_queue)
                    return
                except Exception as stream_error:
                    logger.warning(
                        "EMD streaming request failed for %s (endpoint %s). Falling back to invoke_endpoint. Error: %s",
                        model,
                        endpoint_url,
                        stream_error,
                        exc_info=True
                    )
            
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
                endpoint_name = f"EMD-Model-{model_name_for_endpoint}-{deployment_tag}-endpoint"
                
                logger.info(f"Using EMD endpoint: {endpoint_name}")
                
                # Use boto3 SageMaker Runtime client directly
                runtime_client = boto3.client('sagemaker-runtime', region_name='us-east-1')

                if model_info.get('supports_streaming', True):
                    stream_payload = dict(emd_payload)
                    stream_payload['stream'] = True

                    if self._stream_sagemaker_endpoint(
                        runtime_client,
                        endpoint_name,
                        stream_payload,
                        model,
                        start_time,
                        result_queue,
                        provider='emd',
                        label=display_label
                    ):
                        return

                # Call EMD endpoint via SageMaker Runtime (non-streaming fallback)
                response = runtime_client.invoke_endpoint(
                    EndpointName=endpoint_name,
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
                    runtime_client = boto3.client('sagemaker-runtime', region_name='us-east-1')

                    if model_info.get('supports_streaming', True):
                        stream_payload = dict(emd_payload)
                        stream_payload['stream'] = True
                        if self._stream_sagemaker_endpoint(
                            runtime_client,
                            actual_endpoint_name,
                            stream_payload,
                            model,
                            start_time,
                            result_queue,
                            provider='emd',
                            label=display_label
                        ):
                            return

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
                'type': 'result',
                'model': model,
                'label': display_label,
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
                'type': 'error',
                'model': model,
                'label': display_label,
                'status': 'error',
                'message': str(e)
            })

    def _process_external_model(self, model: str, data: Dict[str, Any], result_queue: queue.Queue) -> None:
        """Process inference for an externally registered deployment."""

        display_label = model
        try:
            model_info = self.registry.get_model_info(model, "external")
            if not model_info:
                raise ValueError(f"External deployment {model} not found")

            endpoint_url = model_info.get('endpoint')
            if not endpoint_url:
                raise ValueError(f"External deployment {model} missing endpoint URL")

            model_name = model_info.get('model_name') or model_info.get('name') or model
            display_label = model_info.get('name') or model_name or model

            manual_config = {
                'api_url': endpoint_url,
                'model_name': model_name,
                'label': display_label,
                'model_key': model,
                'allow_fallback': False
            }

            self._process_manual_api(manual_config, data, result_queue)

        except Exception as exc:
            logger.error("Error processing external deployment %s: %s", model, exc)
            result_queue.put({
                'type': 'error',
                'model': model,
                'label': display_label,
                'status': 'error',
                'message': str(exc)
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
            label_override = manual_config.get('label')
            allow_fallback = bool(manual_config.get('allow_fallback'))

            label = label_override or (f"{model_name} (Manual API)" if model_name else 'Manual API')

            if not api_url or not model_name:
                raise ValueError("Both api_url and model_name are required in manual_config")

            model_key = (
                manual_config.get('model_key')
                or manual_config.get('key')
                or manual_config.get('label')
                or manual_config.get('model')
                or model_name
            )

            # Prepare request data
            text_prompt = data.get('text', '')
            frames = data.get('frames', [])
            max_tokens = data.get('max_tokens', 1000)
            temperature = data.get('temperature', 0.7)

            messages = []
            content_parts = []

            if text_prompt:
                content_parts.append({
                    "type": "text",
                    "text": text_prompt
                })

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

            base_payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            logger.info(f"Calling manual API {api_url} with model {model_name}")
            logger.debug(f"Request payload: {base_payload}")

            response = None
            attempted_stream = False
            request_payload = dict(base_payload)

            for stream_flag in (True, False):
                payload = dict(base_payload)
                if stream_flag:
                    payload['stream'] = True

                try:
                    response = requests.post(
                        api_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30,  # Reduced from 120s for faster failure feedback
                        stream=True
                    )
                except requests.exceptions.Timeout:
                    error_msg = f"Request to {api_url} timed out after 30 seconds"
                    logger.error(error_msg)
                    if stream_flag:
                        logger.warning("Manual API streaming request timed out, retrying without stream flag")
                        continue
                    raise ValueError(error_msg)
                except requests.exceptions.ConnectionError as conn_error:
                    error_msg = f"Connection error to {api_url}: {str(conn_error)}"
                    logger.error(error_msg)
                    if stream_flag:
                        logger.warning("Manual API streaming request failed, retrying without stream flag: %s", conn_error)
                        continue
                    raise ValueError(error_msg)
                except Exception as request_error:
                    if response is not None:
                        response.close()
                        response = None
                    if stream_flag:
                        logger.warning("Manual API streaming request failed, retrying without stream flag: %s", request_error)
                        continue
                    raise

                if response.ok:
                    attempted_stream = stream_flag
                    request_payload = payload
                    break

                error_text = response.text
                status_code = response.status_code
                response.close()
                response = None

                if stream_flag:
                    logger.warning("Manual API streaming request returned %s, retrying without stream flag: %s", status_code, error_text)
                    continue

                raise ValueError(f"API call failed with status {status_code}: {error_text}")

            if response is None:
                raise ValueError("Manual API request failed")

            aggregated_chunks = []
            raw_stream_events = []
            usage = {}
            streamed = False
            raw_body_lines = []

            # Use explicit UTF-8 decoding to prevent corruption
            for line_bytes in response.iter_lines(decode_unicode=False):
                if line_bytes is None:
                    continue
                # Explicitly decode as UTF-8
                try:
                    line = line_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning(f"Failed to decode line as UTF-8: {line_bytes[:100]}")
                    continue

                stripped = line.strip()
                if not stripped:
                    continue

                raw_body_lines.append(stripped)

                if stripped.startswith('data:'):
                    payload_str = stripped[5:].strip()
                    if not payload_str:
                        continue
                    if payload_str == '[DONE]':
                        streamed = True
                        break

                    streamed = True
                    try:
                        event_json = json.loads(payload_str)
                        raw_stream_events.append(event_json)
                    except json.JSONDecodeError:
                        aggregated_chunks.append(payload_str)
                        result_queue.put({
                            'type': 'chunk',
                            'model': model_key,
                            'label': label,
                            'delta': payload_str,
                            'status': 'streaming',
                            'api_url': api_url
                        })
                        self._delay_stream_chunk()
                        continue

                    text_segments = self._extract_text_from_openai_event(event_json)
                    for segment in text_segments:
                        aggregated_chunks.append(segment)
                        result_queue.put({
                            'type': 'chunk',
                            'model': model_key,
                            'label': label,
                            'delta': segment,
                            'status': 'streaming',
                            'api_url': api_url
                        })
                        self._delay_stream_chunk()
                        # Add small delay for visible streaming
                        import time
                        time.sleep(0.05)

                    usage = self._merge_usage_dicts(
                        usage,
                        self._normalize_usage_payload(event_json.get('usage'))
                    )

                elif attempted_stream:
                    # Some APIs stream plain text without SSE framing
                    streamed = True
                    aggregated_chunks.append(stripped)
                    result_queue.put({
                        'type': 'chunk',
                        'model': model_key,
                        'label': label,
                        'delta': stripped,
                        'status': 'streaming',
                        'api_url': api_url
                    })

            raw_body_text = '\n'.join(raw_body_lines).strip()

            if streamed:
                combined_content = ''.join(aggregated_chunks).strip()
                raw_response = raw_stream_events if raw_stream_events else raw_body_text

                result_queue.put({
                    'type': 'result',
                    'model': model_key,
                    'label': label,
                    'status': 'success',
                    'result': {
                        'content': combined_content or raw_body_text,
                        'usage': usage,
                        'raw_response': raw_response
                    },
                    'duration_ms': (datetime.now() - start_time).total_seconds() * 1000,
                    'api_url': api_url
                })

                response.close()
                return

            if not raw_body_text:
                raw_body_text = response.text.strip() if response.content else ''

            response.close()

            try:
                response_data = json.loads(raw_body_text) if raw_body_text else {}
            except json.JSONDecodeError:
                response_data = raw_body_text

            logger.info(f"Manual API response for {model_name}: {response_data}")

            # Extract content and usage from response
            content = ''
            usage = {} if not isinstance(response_data, dict) else usage

            if isinstance(response_data, dict) and response_data.get('choices'):
                choice = response_data['choices'][0]
                if isinstance(choice, dict) and 'message' in choice:
                    message = choice['message']
                    if isinstance(message, dict) and message.get('reasoning_content'):
                        reasoning = message.get('reasoning_content', '').strip()
                        main_content = message.get('content', '').strip() if message.get('content') else ''

                        if reasoning and main_content:
                            content = f"**Reasoning:**\n{reasoning}\n\n**Response:**\n{main_content}"
                        elif reasoning:
                            content = f"**Reasoning:**\n{reasoning}\n\n**Note:** The model's response was cut off due to token limits. The reasoning shows the model's thought process before generating the final answer."
                        elif main_content:
                            content = main_content
                        else:
                            content = "No content available"
                    elif isinstance(message, dict) and message.get('content'):
                        content = message['content']
                    else:
                        content = str(message)
                elif isinstance(choice, dict) and choice.get('text'):
                    content = choice['text']
                else:
                    content = str(choice)
            else:
                content = str(response_data)

            if isinstance(response_data, dict) and response_data.get('usage'):
                usage_obj = response_data['usage']
                usage = {
                    'input_tokens': usage_obj.get('prompt_tokens', usage_obj.get('input_tokens', 0)),
                    'output_tokens': usage_obj.get('completion_tokens', usage_obj.get('output_tokens', 0)),
                    'total_tokens': usage_obj.get('total_tokens', usage_obj.get('prompt_tokens', usage_obj.get('input_tokens', 0)) + usage_obj.get('completion_tokens', usage_obj.get('output_tokens', 0)))
                }

            result_queue.put({
                'type': 'result',
                'model': model_key,
                'label': label,
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
            if allow_fallback:
                raise
            result_queue.put({
                'type': 'error',
                'model': model_key,
                'label': label,
                'status': 'error',
                'message': str(e),
                'api_url': manual_config.get('api_url', 'Unknown')
            })
