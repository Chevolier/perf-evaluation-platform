"""API routes for stress testing functionality."""

from flask import Blueprint, request, jsonify, make_response
from ...services.stress_test_service import StressTestService
from ...utils import get_logger

logger = get_logger(__name__)
stress_test_bp = Blueprint('stress_test', __name__)

# Initialize service
stress_test_service = StressTestService()

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
        test_params = data.get('params', {})
        
        # Handle both dropdown selection and manual input
        if model_key:
            # Traditional dropdown selection
            session_id = stress_test_service.start_stress_test(model_key, test_params)
        elif api_url and model_name:
            # Manual API URL and model name input
            session_id = stress_test_service.start_stress_test_with_custom_api(
                api_url, model_name, test_params
            )
        else:
            logger.error("No model specified in stress test request - need either 'model' or both 'api_url' and 'model_name'")
            return jsonify({
                "status": "error", 
                "message": "Either 'model' or both 'api_url' and 'model_name' are required"
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
        
        # Generate PDF report
        pdf_content = stress_test_service.generate_pdf_report(session_id)
        
        if not pdf_content:
            logger.error(f"Failed to generate PDF report for session {session_id}")
            return jsonify({"status": "error", "message": "Failed to generate report"}), 500
        
        # Return PDF file
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=stress_test_report_{session_id}.pdf'
        
        logger.info(f"PDF report generated for session {session_id}")
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