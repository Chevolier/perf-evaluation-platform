"""API routes for stress testing functionality."""

from flask import Blueprint, request, jsonify, make_response
from ...services.stress_test_service import StressTestService
from ...utils import get_logger

logger = get_logger(__name__)
stress_test_bp = Blueprint('stress_test', __name__)

# Initialize service
stress_test_service = StressTestService()

# Test route-level logging immediately
logger.info("🚀 Stress test routes loaded and service initialized")

@stress_test_bp.route('/stress-test/start', methods=['POST'])
def start_stress_test():
    """Start a stress test session."""
    try:
        data = request.get_json()
        logger.info(f"Stress test start request received: {data}")
        
        if not data:
            logger.error("No JSON data provided in stress test start request")
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        model_key = data.get('model')
        api_url = data.get('api_url')
        model_name = data.get('model_name')
        sagemaker_config = data.get('sagemaker_config')
        test_params = data.get('params', {})

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
            endpoint_name = sagemaker_config.get('endpoint_name')
            sagemaker_model_name = sagemaker_config.get('model_name')

            if not endpoint_name:
                logger.error("SageMaker endpoint_name is required")
                return jsonify({
                    "status": "error",
                    "message": "SageMaker endpoint_name is required"
                }), 400

            if not sagemaker_model_name:
                logger.error("SageMaker model_name is required")
                return jsonify({
                    "status": "error",
                    "message": "SageMaker model_name is required"
                }), 400

            session_id = stress_test_service.start_stress_test_with_sagemaker_endpoint(
                endpoint_name, sagemaker_model_name, test_params
            )
        else:
            logger.error("No model specified in stress test request - need either 'model', 'api_url'+'model_name', or 'sagemaker_config'")
            return jsonify({
                "status": "error",
                "message": "Either 'model', 'api_url'+'model_name', or 'sagemaker_config' are required"
            }), 400
        
        logger.info(f"Stress test started with session ID: {session_id}")
        return jsonify({
            "status": "success",
            "session_id": session_id,
            "message": "Stress test started successfully"
        })
        
    except Exception as e:
        logger.error(f"Error starting stress test: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@stress_test_bp.route('/stress-test/status/<session_id>', methods=['GET'])
def get_stress_test_status(session_id):
    """Get the status of a stress test session."""
    try:
        logger.info(f"Status request for stress test session: {session_id}")
        
        session_data = stress_test_service.get_test_status(session_id)
        
        if not session_data:
            # Try to reconstruct session from results files (for cases when backend was restarted)
            reconstructed_session = stress_test_service.reconstruct_session_from_files(session_id)
            if reconstructed_session:
                logger.info(f"Reconstructed session {session_id} from results files")
                session_data = reconstructed_session
            else:
                logger.warning(f"Stress test session {session_id} not found and no results files available")
                return jsonify({"status": "error", "message": "Test session not found"}), 404
        
        logger.info(f"Session {session_id} status: {session_data.get('status')}, progress: {session_data.get('progress')}")
        
        return jsonify({
            "status": "success",
            "test_session": session_data
        })
        
    except Exception as e:
        logger.error(f"Error getting stress test status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@stress_test_bp.route('/stress-test/download/<session_id>', methods=['GET'])
def download_stress_test_report(session_id):
    """Download a PDF report for a completed stress test session."""
    try:
        logger.info(f"Report download request for session: {session_id}")
        
        session_data = stress_test_service.get_test_status(session_id)
        
        if not session_data:
            logger.warning(f"Stress test session {session_id} not found for report download")
            return jsonify({"status": "error", "message": "Test session not found"}), 404
        
        if session_data.get("status") != "completed" or not session_data.get("results"):
            logger.warning(f"Session {session_id} not completed or no results available")
            return jsonify({"status": "error", "message": "Test not completed or no results available"}), 400
        
        # Generate PDF report and zip session folder
        zip_content = stress_test_service.generate_pdf_report_and_zip_session(session_id)
        
        if not zip_content:
            logger.error(f"Failed to generate report and zip session folder for session {session_id}")
            return jsonify({"status": "error", "message": "Failed to generate report"}), 500
        
        # Return ZIP file
        response = make_response(zip_content)
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename=stress_test_session_{session_id}.zip'
        
        logger.info(f"Session zip file generated for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error downloading stress test report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@stress_test_bp.route('/stress-test/recover/<session_id>', methods=['POST'])
def recover_stress_test_session(session_id):
    """Manually recover a stuck stress test session."""
    try:
        logger.info(f"Manual recovery request for session: {session_id}")
        
        success = stress_test_service.recover_stuck_session(session_id)
        
        if success:
            return jsonify({
                "status": "success", 
                "message": f"Session {session_id} recovered successfully"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": f"Failed to recover session {session_id}"
            }), 400
        
    except Exception as e:
        logger.error(f"Error recovering stress test session: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@stress_test_bp.route('/stress-test/delete/<session_id>', methods=['DELETE'])
def delete_stress_test_session(session_id):
    """Delete a stress test session and its associated files."""
    try:
        logger.info(f"Delete request for session: {session_id}")
        
        success = stress_test_service.delete_session_folder(session_id)
        
        if success:
            return jsonify({
                "status": "success", 
                "message": f"Session {session_id} deleted successfully"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": f"Failed to delete session {session_id} - session not found or already deleted"
            }), 404
        
    except Exception as e:
        logger.error(f"Error deleting stress test session: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@stress_test_bp.route('/stress-test/save-report', methods=['POST'])
def save_html_report():
    """Save HTML report to session folder."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        html_content = data.get('html_content')
        filename = data.get('filename', 'stress-test-report.html')

        logger.info(f"Saving HTML report for session: {session_id}")

        if not session_id or not html_content:
            return jsonify({"status": "error", "message": "Missing session_id or html_content"}), 400

        success = stress_test_service.save_html_report(session_id, html_content, filename)

        if success:
            return jsonify({"status": "success", "message": "HTML report saved successfully"})
        else:
            return jsonify({"status": "error", "message": "Failed to save HTML report"}), 500

    except Exception as e:
        logger.error(f"Error saving HTML report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@stress_test_bp.route('/stress-test/download-zip/<session_id>', methods=['GET'])
def download_session_zip(session_id):
    """Download session folder as ZIP file."""
    try:
        logger.info(f"ZIP download request for session: {session_id}")

        zip_content = stress_test_service.create_session_zip(session_id)

        if not zip_content:
            logger.error(f"Failed to create ZIP for session {session_id}")
            return jsonify({"status": "error", "message": "Failed to create session ZIP"}), 500

        # Create response with ZIP content
        response = make_response(zip_content)
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename=stress-test-session-{session_id}.zip'

        logger.info(f"Session ZIP created and ready for download: {session_id}")
        return response

    except Exception as e:
        logger.error(f"Error creating session ZIP: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500