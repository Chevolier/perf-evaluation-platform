"""API routes for model inference."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from services.inference_service import InferenceService
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
    max_tokens: int = 1024
    temperature: float = 0.7
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
    max_tokens: int = 1024
    temperature: float = 0.7

    class Config:
        extra = "allow"


@inference_router.post("/multi-inference")
def multi_inference(data: MultiInferenceRequest):
    """Run inference on multiple models simultaneously with streaming results."""
    try:
        logger.info(f"Multi-inference request received with data: {data.model_dump()}")

        # Create fresh InferenceService instance to ensure latest code is used
        inference_service = InferenceService()

        # Stream results back to client
        logger.info("Starting streaming response for multi-inference")
        return StreamingResponse(
            inference_service.multi_inference(data.model_dump()),
            media_type='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )

    except Exception as e:
        logger.error(f"Error in multi-inference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@inference_router.post("/inference")
def single_inference(data: SingleInferenceRequest):
    """Run inference on a single model."""
    try:
        if not data.model:
            raise HTTPException(status_code=400, detail="No model specified")

        # Create fresh InferenceService instance and use multi-inference with single model
        inference_service = InferenceService()
        request_data = data.model_dump()
        request_data['models'] = [data.model]
        results = list(inference_service.multi_inference(request_data))

        # Return the first (and only) result
        if results:
            import json
            return json.loads(results[0])
        else:
            raise HTTPException(status_code=500, detail="No results returned")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in single inference: {e}")
        raise HTTPException(status_code=500, detail=str(e))
