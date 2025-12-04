"""API routes for model management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.model_service import ModelService
from utils import get_logger

logger = get_logger(__name__)
model_router = APIRouter(prefix="/api", tags=["models"])

# Initialize service
model_service = ModelService()


class DeployModelsRequest(BaseModel):
    models: List[str] = []
    instance_type: str = "g5.2xlarge"
    engine_type: str = "vllm"
    service_type: str = "vllm_realtime"
    tp_size: int = 1
    dp_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 2048


class CheckModelStatusRequest(BaseModel):
    models: List[str] = []
    force_refresh: bool = False


class StopModelRequest(BaseModel):
    model_key: str


class RegisterDeploymentRequest(BaseModel):
    model_key: str
    container_name: str
    port: int
    tag: Optional[str] = None


@model_router.get("/model-list")
def get_model_list():
    """Get list of all available models."""
    try:
        return model_service.get_model_list()
    except Exception as e:
        logger.error(f"Error getting model list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.get("/ec2/current-models")
def get_current_ec2_models():
    """Get currently deployed EC2 models."""
    try:
        deployed_models = model_service.get_current_ec2_models()
        return {"status": "success", "deployed": deployed_models}
    except Exception as e:
        logger.error(f"Error getting current EC2 models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.post("/deploy-models")
def deploy_models(data: DeployModelsRequest):
    """Deploy models using EC2 Docker deployment."""
    try:
        logger.info(f"🚀 Deploy request received:")
        logger.info(f"  Models: {data.models}")
        logger.info(f"  Instance type: {data.instance_type}")
        logger.info(f"  Engine type: {data.engine_type}")
        logger.info(f"  Service type: {data.service_type}")
        logger.info(f"  TP size: {data.tp_size}")
        logger.info(f"  DP size: {data.dp_size}")
        logger.info(f"  GPU memory utilization: {data.gpu_memory_utilization}")
        logger.info(f"  Max model length: {data.max_model_len}")

        results = {}
        for model_key in data.models:
            logger.info(f"🚀 Deploying model: {model_key}")

            port = 8000
            result = model_service.deploy_model_on_ec2(
                model_key=model_key,
                instance_type=data.instance_type,
                engine_type=data.engine_type,
                service_type=data.service_type,
                port=port,
                tp_size=data.tp_size,
                dp_size=data.dp_size,
                gpu_memory_utilization=data.gpu_memory_utilization,
                max_model_len=data.max_model_len
            )

            logger.info(f"🚀 Deployment result for {model_key}: {result}")
            results[model_key] = result

        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"Error deploying models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.post("/check-model-status")
def check_model_status(data: CheckModelStatusRequest):
    """Check status of multiple models.

    Uses cache for fast responses. Set force_refresh=true to bypass cache.
    """
    try:
        result = model_service.get_cached_model_status(data.models, force_refresh=data.force_refresh)
        return result
    except Exception as e:
        logger.error(f"Error checking model status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.get("/ec2/status")
def get_ec2_status():
    """Get EC2 deployment status."""
    try:
        deployed_models = model_service.get_current_ec2_models()
        return {
            "status": "success",
            "available": True,
            "deployed_models": deployed_models
        }
    except Exception as e:
        logger.error(f"Error getting EC2 status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.post("/stop-model")
def stop_model(data: StopModelRequest):
    """Stop an EC2 model deployment."""
    try:
        if not data.model_key:
            raise HTTPException(status_code=400, detail="Model key is required")

        result = model_service.stop_ec2_model(data.model_key)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.post("/register-deployment")
def register_existing_deployment(data: RegisterDeploymentRequest):
    """Register an existing Docker deployment that wasn't deployed through the platform."""
    try:
        result = model_service.register_existing_deployment(
            data.model_key, data.container_name, data.port, data.tag
        )
        return result
    except Exception as e:
        logger.error(f"Error registering existing deployment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@model_router.post("/clear-stale-status")
def clear_stale_status():
    """Clear stale deployment statuses (failed statuses older than 10 minutes)."""
    try:
        result = model_service.clear_stale_deployment_status()
        return result
    except Exception as e:
        logger.error(f"Error clearing stale status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
