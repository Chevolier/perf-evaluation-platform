"""Shared streaming helpers for all inference methods.

This module provides unified helpers for:
- Bedrock (Claude, Nova) streaming
- OpenAI-compatible streaming (vLLM, Manual API)
- SageMaker streaming
- SSE buffering and usage finalization
"""

import base64
import json
import re
from typing import Dict, Any, Tuple, List, Optional


# === Bedrock Helpers ===

def classify_bedrock_model(model: str, model_id: str) -> Tuple[bool, bool]:
    """Classify Bedrock model type.

    Args:
        model: Model key (e.g., 'claude-opus-4.5')
        model_id: AWS model ID (e.g., 'us.anthropic.claude-opus-4-5-20251101-v1:0')

    Returns:
        Tuple of (is_claude, is_nova)
    """
    is_claude = 'claude' in model.lower() or 'anthropic' in model_id.lower()
    is_nova = 'nova' in model.lower() or 'amazon' in model_id.lower()
    return is_claude, is_nova


def build_bedrock_request(model: str, model_info: Dict, data: Dict) -> Dict:
    """Build request body for Bedrock models (Claude/Nova).

    Args:
        model: Model key
        model_info: Model info from registry
        data: Request data with text, frames, max_tokens, temperature

    Returns:
        Request body dict formatted for the specific model type
    """
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

    is_claude, is_nova = classify_bedrock_model(model, model_id)

    # Build request based on model type
    if is_claude:
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": message_content}]
        }
    elif is_nova:
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


def parse_bedrock_chunk(chunk_data: Dict, is_claude: bool, is_nova: bool) -> Tuple[str, bool, Dict]:
    """Parse Bedrock streaming chunk based on model type.

    Args:
        chunk_data: Parsed JSON chunk from Bedrock stream
        is_claude: Whether this is a Claude model
        is_nova: Whether this is a Nova model

    Returns:
        Tuple of (text_chunk, is_final, usage_dict)
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


# === OpenAI-Compatible Helpers (vLLM, Manual API) ===

def parse_openai_chunk(chunk_data: Dict) -> Tuple[str, bool, Dict]:
    """Parse OpenAI-compatible SSE chunk (vLLM/Manual API).

    Handles the standard OpenAI chat completions streaming format:
    - choices[0].delta.content for text
    - choices[0].finish_reason for completion
    - usage object for token counts

    Args:
        chunk_data: Parsed JSON chunk from SSE stream

    Returns:
        Tuple of (text_chunk, is_final, usage_dict)
    """
    text_chunk = ""
    is_final = False
    usage = {}

    if 'choices' in chunk_data and chunk_data['choices']:
        choice = chunk_data['choices'][0]
        delta = choice.get('delta', {})

        # Extract text content
        if 'content' in delta and delta['content']:
            text_chunk = delta['content']

        # Check for completion
        if choice.get('finish_reason') == 'stop':
            is_final = True

    # Extract usage (typically in final chunk with stream_options.include_usage)
    if 'usage' in chunk_data and chunk_data['usage']:
        usage = {
            'input_tokens': chunk_data['usage'].get('prompt_tokens', 0),
            'output_tokens': chunk_data['usage'].get('completion_tokens', 0),
            'total_tokens': chunk_data['usage'].get('total_tokens', 0)
        }

    return text_chunk, is_final, usage


# === SageMaker Helpers ===

def parse_sagemaker_chunk(chunk_data: Dict) -> Tuple[str, bool, Dict]:
    """Parse SageMaker streaming chunk.

    SageMaker endpoints typically use OpenAI-compatible format,
    so this delegates to parse_openai_chunk.

    Args:
        chunk_data: Parsed JSON chunk from SageMaker stream

    Returns:
        Tuple of (text_chunk, is_final, usage_dict)
    """
    return parse_openai_chunk(chunk_data)


# === Common Utilities ===

def finalize_usage(usage: Dict) -> Dict:
    """Finalize usage dict by adding total_tokens if missing.

    Args:
        usage: Usage dict with input_tokens and/or output_tokens

    Returns:
        Usage dict with total_tokens added if calculable
    """
    if 'total_tokens' not in usage and 'input_tokens' in usage and 'output_tokens' in usage:
        usage['total_tokens'] = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
    return usage


class SSEBuffer:
    """Buffer for handling split SSE chunks across network boundaries.

    SSE data can be split across multiple network packets. This buffer
    accumulates data and yields complete SSE lines as they become available.

    Usage:
        buffer = SSEBuffer()
        async for chunk_bytes in response.content:
            for data_str in buffer.add(chunk_bytes.decode('utf-8')):
                chunk_data = json.loads(data_str)
                # process chunk_data
    """

    def __init__(self):
        """Initialize empty buffer."""
        self.buffer = ""

    def add(self, chunk: str) -> List[str]:
        """Add chunk data and return complete SSE data lines.

        Args:
            chunk: Raw chunk string from network

        Returns:
            List of complete SSE data payloads (without 'data: ' prefix)
        """
        self.buffer += chunk
        lines = []

        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            line = line.strip()

            # Skip empty lines and SSE comments
            if not line or line.startswith(':'):
                continue

            # Extract data from SSE format
            if line.startswith('data: '):
                data = line[6:]  # Remove 'data: ' prefix
                if data != '[DONE]':
                    lines.append(data)

        return lines

    def flush(self) -> List[str]:
        """Flush any remaining data in buffer.

        Call this after stream ends to handle any incomplete final chunk.

        Returns:
            List of remaining SSE data payloads
        """
        if self.buffer.strip():
            line = self.buffer.strip()
            self.buffer = ""
            if line.startswith('data: '):
                data = line[6:]
                if data != '[DONE]':
                    return [data]
        return []


def detect_image_format(base64_data: str) -> str:
    """Detect image format from base64 data.

    Args:
        base64_data: Base64 encoded image data

    Returns:
        MIME type (e.g., 'image/jpeg', 'image/png')
    """
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


def extract_context_limits_from_error(error_text: str) -> Optional[Tuple[int, int]]:
    """Extract (max_context_tokens, input_tokens) from an OpenAI-compatible error payload.

    vLLM (and some other OpenAI-compatible servers) return 400 errors like:
      "'max_tokens' ... is too large ... maximum context length is 2048 tokens and your request has 12 input tokens ..."

    Args:
        error_text: Raw response body (JSON string or plain text)

    Returns:
        (max_context_tokens, input_tokens) if detected, else None.
    """
    message = error_text
    try:
        parsed = json.loads(error_text)
        if isinstance(parsed, dict):
            message = (
                parsed.get("error", {}).get("message")
                or parsed.get("message")
                or error_text
            )
    except Exception:
        pass

    if not isinstance(message, str):
        return None

    max_ctx_match = re.search(r"maximum context length is\s+(\d+)\s+tokens", message)
    input_match = re.search(r"request has\s+(\d+)\s+input tokens", message)

    if not max_ctx_match or not input_match:
        return None

    try:
        return int(max_ctx_match.group(1)), int(input_match.group(1))
    except Exception:
        return None
