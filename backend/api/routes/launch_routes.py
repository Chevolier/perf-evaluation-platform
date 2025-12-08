"""Launch API routes for unified model deployment."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from services.launch_service import LaunchService
from utils import get_logger

logger = get_logger(__name__)

# Create router
launch_router = APIRouter(prefix="/api", tags=["launch"])

# Initialize launch service
launch_service = LaunchService()


class CreateLaunchRequest(BaseModel):
    """Request model for creating a launch job."""
    method: str
    model_key: str
    engine: str
    params: Dict[str, Any] = {}
    user_id: Optional[str] = None


@launch_router.get("/launch-methods")
def get_launch_methods():
    """Return available launch methods and their schemas."""
    try:
        result = launch_service.get_launch_methods()
        return result
    except Exception as e:
        logger.error(f"Error getting launch methods: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@launch_router.post("/launches", status_code=201)
def create_launch(data: CreateLaunchRequest):
    """Create a new launch job.

    Request body:
        {
            "method": "SAGEMAKER_ENDPOINT",
            "model_key": "qwen3-8b",
            "engine": "vllm",
            "params": {...},
            "user_id": "optional"
        }
    """
    try:
        result = launch_service.create_launch(
            method=data.method,
            model_key=data.model_key,
            engine=data.engine,
            params=data.params,
            user_id=data.user_id
        )

        if result.get('success'):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Launch creation failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating launch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@launch_router.get("/launches/{job_id}")
def get_launch_status(job_id: str):
    """Get launch job status."""
    try:
        result = launch_service.get_launch_status(job_id)

        if result.get('success'):
            return result
        else:
            raise HTTPException(status_code=404, detail=result.get('error', 'Job not found'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting launch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@launch_router.get("/launches")
def list_launches(
    method: Optional[str] = Query(None, description="Filter by launch method"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    model_key: Optional[str] = Query(None, description="Filter by model"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """List launch jobs with pagination."""
    try:
        filters = {}
        if method:
            filters['method'] = method
        if status:
            filters['status'] = status
        if model_key:
            filters['model_key'] = model_key
        if user_id:
            filters['user_id'] = user_id

        result = launch_service.list_launches(
            filters=filters if filters else None,
            limit=limit,
            offset=offset
        )

        return result

    except Exception as e:
        logger.error(f"Error listing launches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@launch_router.delete("/launches/{job_id}")
def cancel_launch(job_id: str):
    """Cancel a launch job."""
    try:
        result = launch_service.cancel_launch(job_id)

        if result.get('success'):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Cancellation failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling launch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@launch_router.post("/launches/{job_id}/status")
def poll_launch_status(job_id: str):
    """Poll external system for launch job status update."""
    try:
        result = launch_service.poll_job_status(job_id)

        if result.get('success'):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Poll failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error polling launch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@launch_router.get("/models/{model_key}/launch-info")
def get_model_launch_info(model_key: str):
    """Get launch information for a specific model."""
    try:
        result = launch_service.get_model_launch_info(model_key)

        if result.get('success'):
            return result
        else:
            raise HTTPException(status_code=404, detail=result.get('error', 'Model not found'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model launch info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
