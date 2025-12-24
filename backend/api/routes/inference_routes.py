"""API routes for model inference."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from services.async_inference_service import AsyncInferenceService
from utils import get_logger

logger = get_logger(__name__)
inference_router = APIRouter(prefix="/api", tags=["inference"])


class MultiInferenceRequest(BaseModel):
    models: List[str] = []
    prompt: Optional[str] = None
    text: Optional[str] = None  # Frontend sends 'text' field
    messages: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[str]] = None
    frames: Optional[List[str]] = None  # Frontend sends 'frames' field
    mediaType: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    # Image resize parameters (optional - if not specified, no resize)
    resize_width: Optional[int] = None
    resize_height: Optional[int] = None
    # Manual API configuration
    manual_config: Optional[Dict[str, Any]] = None
    # SageMaker configuration
    sagemaker_config: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"  # Allow extra fields


class SingleInferenceRequest(BaseModel):
    model: str
    prompt: Optional[str] = None
    text: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[str]] = None
    frames: Optional[List[str]] = None
    max_tokens: int = 4096
    temperature: float = 0.7

    class Config:
        extra = "allow"


@inference_router.post("/multi-inference")
async def multi_inference(data: MultiInferenceRequest):
    """Run inference on multiple models simultaneously with streaming results.

    Uses async streaming for incremental frontend display.
    """
    try:
        logger.info(f"Multi-inference request received with data: {data.model_dump()}")

        # Create async inference service for true streaming
        async_inference_service = AsyncInferenceService()

        # Stream results back to client using async generator
        logger.info("Starting async streaming response for multi-inference")
        return StreamingResponse(
            async_inference_service.multi_inference(data.model_dump()),
            media_type='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'X-Accel-Buffering': 'no'  # Disable nginx buffering
            }
        )

    except Exception as e:
        logger.error(f"Error in multi-inference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@inference_router.post("/inference")
async def single_inference(data: SingleInferenceRequest):
    """Run inference on a single model."""
    try:
        import json

        if not data.model:
            raise HTTPException(status_code=400, detail="No model specified")

        # Create async inference service and collect results
        async_inference_service = AsyncInferenceService()
        request_data = data.model_dump()
        request_data['models'] = [data.model]

        results = []
        async for chunk in async_inference_service.multi_inference(request_data):
            results.append(chunk)

        # Return the first result with actual content (skip heartbeats)
        for result in results:
            if result.startswith('data: '):
                parsed = json.loads(result[6:].strip())
                if parsed.get('status') in ['success', 'error']:
                    return parsed

        raise HTTPException(status_code=500, detail="No results returned")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in single inference: {e}")
        raise HTTPException(status_code=500, detail=str(e))
