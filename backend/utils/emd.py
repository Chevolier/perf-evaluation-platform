"""Helper utilities for working with EMD deployments."""

from __future__ import annotations

import ast
import json
from typing import Any, Dict, Optional, Tuple

# Keys that may contain endpoint style URLs in EMD status payloads
_ENDPOINT_KEYS = (
    "BaseURL",
    "base_url",
    "EndpointURL",
    "endpoint_url",
    "EndpointUrl",
    "endpointUrl",
    "InferenceURL",
    "inference_url",
    "InferenceUrl",
    "ApiUrl",
    "apiUrl",
    "URL",
    "Url",
    "url",
)


def _parse_outputs_field(outputs: Any) -> Dict[str, Any]:
    """Best-effort parser for the `outputs` field returned by EMD status."""
    if isinstance(outputs, dict):
        return outputs

    if isinstance(outputs, str):
        candidate = outputs.strip()
        if not candidate:
            return {}
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                return {}
    return {}


def _normalize_base_url(raw: str) -> Optional[str]:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None

    if value.startswith(("http://", "https://")):
        normalized = value.rstrip('/')
    else:
        normalized = f"http://{value.strip('/')}"
    return normalized or None


def _ensure_chat_completions_path(base_url: str) -> str:
    normalized = base_url.rstrip('/')
    if "v1/chat/completions" in normalized:
        return normalized
    return f"{normalized}/v1/chat/completions"


def _extract_from_mapping(mapping: Dict[str, Any]) -> Optional[str]:
    for key in _ENDPOINT_KEYS:
        value = mapping.get(key)
        if isinstance(value, str):
            candidate = _normalize_base_url(value)
            if candidate:
                return _ensure_chat_completions_path(candidate)
    return None


def extract_endpoint_from_model_entry(model_entry: Dict[str, Any]) -> Optional[str]:
    """Extract an OpenAI-compatible inference endpoint from an EMD status entry."""
    if not isinstance(model_entry, dict):
        return None

    # direct endpoint fields on the record itself
    direct_endpoint = _extract_from_mapping(model_entry)
    if direct_endpoint:
        return direct_endpoint

    dns_name = model_entry.get("DNSName") or model_entry.get("dnsName")
    if isinstance(dns_name, str) and dns_name.strip():
        candidate = _normalize_base_url(dns_name)
        if candidate:
            return _ensure_chat_completions_path(candidate)

    outputs = _parse_outputs_field(model_entry.get("outputs"))
    if outputs:
        output_endpoint = _extract_from_mapping(outputs)
        if output_endpoint:
            return output_endpoint

    return None


def resolve_deployment_api_url(model_path: str, deployment_tag: str) -> Tuple[str, bool]:
    """Find the chat-completions endpoint for a given EMD deployment.

    Returns a tuple of (endpoint_url, used_fallback). The fallback flag is True when
    the resolved endpoint belongs to a different deployment than requested (e.g.,
    when the specific stack lacks URL metadata but another completed deployment
    exposes a usable endpoint).
    """
    try:
        from emd.sdk.status import get_model_status  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("EMD SDK 不可用，无法获取API端点") from exc

    status = get_model_status() or {}

    completed_entries = status.get("completed", []) or []

    # First, try to locate the exact deployment record
    for entry in completed_entries:
        if entry.get("model_id") == model_path and entry.get("model_tag") == deployment_tag:
            endpoint = extract_endpoint_from_model_entry(entry)
            if endpoint:
                return endpoint, False
            # If the record exists but lacks endpoint metadata, fall back to other entries
            break

    # Fallback to any completed deployment that exposes an endpoint
    for entry in completed_entries:
        endpoint = extract_endpoint_from_model_entry(entry)
        if endpoint:
            return endpoint, True

    # No usable endpoint found; check whether deployment is still in progress for clearer messaging
    inprogress_entries = status.get("inprogress", []) or []
    for entry in inprogress_entries:
        if entry.get("model_id") == model_path and entry.get("model_tag") == deployment_tag:
            raise RuntimeError("模型仍在部署中，暂不可用")

    raise RuntimeError(
        f"无法找到模型 {model_path}/{deployment_tag} 的API端点。请检查模型是否已正确部署。"
    )


__all__ = [
    "extract_endpoint_from_model_entry",
    "resolve_deployment_api_url",
]
