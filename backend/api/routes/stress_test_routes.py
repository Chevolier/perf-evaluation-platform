"""API routes for stress testing functionality."""

import math
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Any, Optional
from services.stress_test_service import StressTestService
from utils import get_logger

logger = get_logger(__name__)
stress_test_router = APIRouter(prefix="/api", tags=["stress-test"])


def sanitize_for_json(obj):
    """Recursively sanitize an object for JSON serialization.

    Replaces inf, -inf, and nan float values with None to prevent JSON serialization errors.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    else:
        return obj

# Initialize service
stress_test_service = StressTestService()

# Test route-level logging immediately
logger.info("🚀 Stress test routes loaded and service initialized")


class SageMakerConfig(BaseModel):
    endpoint_name: str
    model_name: str


class StressTestStartRequest(BaseModel):
    model: Optional[str] = None
    api_url: Optional[str] = None
    model_name: Optional[str] = None
    sagemaker_config: Optional[SageMakerConfig] = None
    params: Dict[str, Any] = {}


class SaveHtmlReportRequest(BaseModel):
    session_id: str
    html_content: str
    filename: str = "stress-test-report.html"


@stress_test_router.post("/stress-test/start")
def start_stress_test(data: StressTestStartRequest):
    """Start a stress test session."""
    try:
        logger.info(f"Stress test start request received: {data.model_dump()}")

        model_key = data.model
        api_url = data.api_url
        model_name = data.model_name
        sagemaker_config = data.sagemaker_config
        test_params = data.params

        # Handle dropdown selection, manual input, and SageMaker endpoint
        if model_key:
            # Traditional dropdown selection
            session_id = stress_test_service.start_stress_test(model_key, test_params)
        elif api_url and model_name:
            # Manual API URL and model name input
            session_id = stress_test_service.start_stress_test_with_custom_api(
                api_url, model_name, test_params
            )
        elif sagemaker_config:
            # SageMaker endpoint configuration
            if not sagemaker_config.endpoint_name:
                logger.error("SageMaker endpoint_name is required")
                raise HTTPException(status_code=400, detail="SageMaker endpoint_name is required")

            if not sagemaker_config.model_name:
                logger.error("SageMaker model_name is required")
                raise HTTPException(status_code=400, detail="SageMaker model_name is required")

            session_id = stress_test_service.start_stress_test_with_sagemaker_endpoint(
                sagemaker_config.endpoint_name, sagemaker_config.model_name, test_params
            )
        else:
            logger.error("No model specified in stress test request")
            raise HTTPException(
                status_code=400,
                detail="Either 'model', 'api_url'+'model_name', or 'sagemaker_config' are required"
            )

        logger.info(f"Stress test started with session ID: {session_id}")
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Stress test started successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting stress test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.get("/stress-test/status/{session_id}")
def get_stress_test_status(session_id: str):
    """Get the status of a stress test session."""
    try:
        logger.info(f"Status request for stress test session: {session_id}")

        session_data = stress_test_service.get_test_status(session_id)

        if not session_data:
            # Try to reconstruct session from results files
            reconstructed_session = stress_test_service.reconstruct_session_from_files(session_id)
            if reconstructed_session:
                logger.info(f"Reconstructed session {session_id} from results files")
                session_data = reconstructed_session
            else:
                logger.warning(f"Stress test session {session_id} not found")
                raise HTTPException(status_code=404, detail="Test session not found")

        logger.info(f"Session {session_id} status: {session_data.get('status')}, progress: {session_data.get('progress')}")

        # Sanitize data to prevent JSON serialization errors with inf/nan values
        sanitized_data = sanitize_for_json(session_data)

        return {"status": "success", "test_session": sanitized_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stress test status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.get("/stress-test/download/{session_id}")
def download_stress_test_report(session_id: str):
    """Download a PDF report for a completed stress test session."""
    try:
        logger.info(f"Report download request for session: {session_id}")

        session_data = stress_test_service.get_test_status(session_id)

        if not session_data:
            logger.warning(f"Stress test session {session_id} not found for report download")
            raise HTTPException(status_code=404, detail="Test session not found")

        if session_data.get("status") != "completed" or not session_data.get("results"):
            logger.warning(f"Session {session_id} not completed or no results available")
            raise HTTPException(status_code=400, detail="Test not completed or no results available")

        # Generate PDF report and zip session folder
        zip_content = stress_test_service.generate_pdf_report_and_zip_session(session_id)

        if not zip_content:
            logger.error(f"Failed to generate report for session {session_id}")
            raise HTTPException(status_code=500, detail="Failed to generate report")

        logger.info(f"Session zip file generated for session {session_id}")
        return Response(
            content=zip_content,
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename=stress_test_session_{session_id}.zip'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading stress test report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.post("/stress-test/recover/{session_id}")
def recover_stress_test_session(session_id: str):
    """Manually recover a stuck stress test session."""
    try:
        logger.info(f"Manual recovery request for session: {session_id}")

        success = stress_test_service.recover_stuck_session(session_id)

        if success:
            return {"status": "success", "message": f"Session {session_id} recovered successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to recover session {session_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recovering stress test session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.delete("/stress-test/delete/{session_id}")
def delete_stress_test_session(session_id: str):
    """Delete a stress test session and its associated files."""
    try:
        logger.info(f"Delete request for session: {session_id}")

        success = stress_test_service.delete_session_folder(session_id)

        if success:
            return {"status": "success", "message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Failed to delete session {session_id} - session not found or already deleted"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting stress test session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.post("/stress-test/save-report")
def save_html_report(data: SaveHtmlReportRequest):
    """Save HTML report to session folder."""
    try:
        logger.info(f"Saving HTML report for session: {data.session_id}")

        success = stress_test_service.save_html_report(data.session_id, data.html_content, data.filename)

        if success:
            return {"status": "success", "message": "HTML report saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save HTML report")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving HTML report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.get("/stress-test/download-zip/{session_id}")
def download_session_zip(session_id: str):
    """Download session folder as ZIP file."""
    try:
        logger.info(f"ZIP download request for session: {session_id}")

        zip_content = stress_test_service.create_session_zip(session_id)

        if not zip_content:
            logger.error(f"Failed to create ZIP for session {session_id}")
            raise HTTPException(status_code=500, detail="Failed to create session ZIP")

        logger.info(f"Session ZIP created and ready for download: {session_id}")
        return Response(
            content=zip_content,
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename=stress-test-session-{session_id}.zip'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session ZIP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stress_test_router.get("/stress-test/litellm-logs/{session_id}")
def get_litellm_logs(session_id: str):
    """Get litellm server logs for a session."""
    try:
        logger.info(f"Litellm logs request for session: {session_id}")

        log_content = stress_test_service.get_litellm_logs(session_id)

        if log_content is None:
            raise HTTPException(status_code=404, detail=f"No litellm logs found for session {session_id}")

        return {
            "status": "success",
            "session_id": session_id,
            "logs": log_content,
            "log_size": len(log_content)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving litellm logs for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
