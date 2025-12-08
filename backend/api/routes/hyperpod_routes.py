"""API routes for managing InfraForge-powered HyperPod deployments."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional

from services.hyperpod_service import HyperPodService
from utils import get_logger

logger = get_logger(__name__)

hyperpod_router = APIRouter(prefix="/api", tags=["hyperpod"])
_service = HyperPodService()


class HyperPodDeployRequest(BaseModel):
    """Request model for HyperPod deployment."""
    requested_by: Optional[str] = None
    user_id: Optional[str] = None
    # Additional deployment parameters can be added here
    model_config = {"extra": "allow"}  # Allow extra fields


class HyperPodDestroyRequest(BaseModel):
    """Request model for HyperPod destroy."""
    requested_by: Optional[str] = None
    user_id: Optional[str] = None
    model_config = {"extra": "allow"}  # Allow extra fields


@hyperpod_router.post("/hyperpod/deploy", status_code=202)
def deploy_hyperpod(payload: HyperPodDeployRequest):
    """Trigger a new HyperPod deployment via InfraForge."""
    user_id = payload.requested_by or payload.user_id

    if not _service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="HyperPod deployment backend is not configured. Check infraforge settings."
        )

    try:
        # Convert pydantic model to dict for the service
        payload_dict = payload.model_dump(exclude_none=True)
        job = _service.start_deployment(payload_dict, user_id=user_id)
    except ValueError as exc:
        logger.warning("Invalid HyperPod deploy request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unable to start HyperPod deployment: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to start HyperPod deployment")

    return {
        "status": "submitted",
        "job": job,
    }


@hyperpod_router.post("/hyperpod/destroy", status_code=202)
def destroy_hyperpod(payload: HyperPodDestroyRequest):
    """Trigger a HyperPod destroy workflow via InfraForge."""
    user_id = payload.requested_by or payload.user_id

    if not _service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="HyperPod deployment backend is not configured. Check infraforge settings."
        )

    try:
        payload_dict = payload.model_dump(exclude_none=True)
        job = _service.start_destroy(payload_dict, user_id=user_id)
    except ValueError as exc:
        logger.warning("Invalid HyperPod destroy request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unable to start HyperPod destroy: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to start HyperPod destroy workflow")

    return {
        "status": "submitted",
        "job": job,
    }


@hyperpod_router.get("/hyperpod/jobs")
def list_hyperpod_jobs():
    """List tracked HyperPod jobs."""
    jobs = _service.list_jobs()
    return {
        "status": "success",
        "jobs": jobs,
    }


@hyperpod_router.get("/hyperpod/presets")
def list_hyperpod_presets():
    """Return available HyperPod presets."""
    presets = _service.get_presets()
    return {
        "status": "success",
        "presets": presets,
    }


@hyperpod_router.get("/hyperpod/jobs/{job_id}")
def get_hyperpod_job(job_id: str):
    """Return status information for a specific HyperPod job."""
    status_payload = _service.get_job_status(job_id)
    if not status_payload:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown HyperPod job: {job_id}"
        )

    return {
        "status": "success",
        "job": status_payload,
    }


@hyperpod_router.get("/hyperpod/jobs/{job_id}/logs")
def get_hyperpod_job_logs(
    job_id: str,
    tail: Optional[int] = Query(None, description="Number of tail lines to return")
):
    """Return logs for a HyperPod job."""
    try:
        log_payload = _service.get_job_logs(job_id, tail=tail)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown HyperPod job: {job_id}"
        )
    except Exception as exc:
        logger.exception("Unable to read HyperPod logs for %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail="Failed to read HyperPod logs")

    return {
        "status": "success",
        "logs": log_payload,
    }


@hyperpod_router.get("/hyperpod/status")
def legacy_hyperpod_status(
    jobId: Optional[str] = Query(None, alias="jobId"),
    job_id: Optional[str] = Query(None),
    executionArn: Optional[str] = Query(None)
):
    """Backward compatible status endpoint using the jobId query parameter."""
    actual_job_id = jobId or job_id or executionArn
    if not actual_job_id:
        raise HTTPException(
            status_code=400,
            detail="jobId query parameter is required"
        )

    status_payload = _service.get_job_status(actual_job_id)
    if not status_payload:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown HyperPod job: {actual_job_id}"
        )

    return {
        "status": "success",
        "job": status_payload,
    }
