"""API routes for model management."""

from flask import Blueprint, request, jsonify
from ...services.model_service import ModelService
from ...utils import get_logger

logger = get_logger(__name__)
model_bp = Blueprint('model', __name__)

# Initialize service
model_service = ModelService()

@model_bp.route('/model-list', methods=['GET'])
def get_model_list():
    """Get list of all available models."""
    try:
        return jsonify(model_service.get_model_list())
    except Exception as e:
        logger.error(f"Error getting model list: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@model_bp.route('/ec2/current-models', methods=['GET'])
def get_current_ec2_models():
    """Get currently deployed EC2 models."""
    try:
        deployed_models = model_service.get_current_ec2_models()
        return jsonify({
            "status": "success",
            "deployed": deployed_models
        })
    except Exception as e:
        logger.error(f"Error getting current EC2 models: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@model_bp.route('/deploy-models', methods=['POST'])
def deploy_models():
    """Deploy models using EC2 Docker deployment."""
    try:
        data = request.get_json() or {}
        models = data.get('models', [])
        instance_type = data.get('instance_type', 'g5.2xlarge')
        engine_type = data.get('engine_type', 'vllm')
        service_type = data.get('service_type', 'vllm_realtime')

        # Get TP/DP parameters for EC2 deployment
        tp_size = data.get('tpSize', 1)
        dp_size = data.get('dpSize', 1)

        logger.info(f"🚀 Deploy request received:")
        logger.info(f"  Models: {models}")
        logger.info(f"  Instance type: {instance_type}")
        logger.info(f"  Engine type: {engine_type}")
        logger.info(f"  Service type: {service_type}")
        logger.info(f"  TP size: {tp_size}")
        logger.info(f"  DP size: {dp_size}")

        results = {}
        for model_key in models:
            logger.info(f"🚀 Deploying model: {model_key}")

            # Use EC2 Docker deployment only
            port = 8000  # Default port, could be made configurable
            result = model_service.deploy_model_on_ec2(
                model_key=model_key,
                instance_type=instance_type,
                engine_type=engine_type,
                service_type=service_type,
                port=port,
                tp_size=tp_size,
                dp_size=dp_size
            )

            logger.info(f"🚀 Deployment result for {model_key}: {result}")
            results[model_key] = result

        return jsonify({
            "status": "success",
            "results": results
        })
    except Exception as e:
        logger.error(f"Error deploying models: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@model_bp.route('/check-model-status', methods=['POST'])
def check_model_status():
    """Check status of multiple models."""
    try:
        data = request.get_json() or {}
        models = data.get('models', [])
        result = model_service.check_multiple_model_status(models)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error checking model status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@model_bp.route('/ec2/status', methods=['GET'])
def get_ec2_status():
    """Get EC2 deployment status."""
    try:
        # Return current EC2 models status
        deployed_models = model_service.get_current_ec2_models()
        return jsonify({
            "status": "success",
            "available": True,  # EC2 is always available
            "deployed_models": deployed_models
        })
    except Exception as e:
        logger.error(f"Error getting EC2 status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@model_bp.route('/stop-model', methods=['POST'])
def stop_model():
    """Stop an EC2 model deployment."""
    try:
        data = request.get_json() or {}
        model_key = data.get('model_key')

        if not model_key:
            return jsonify({"success": False, "error": "Model key is required"}), 400

        result = model_service.stop_ec2_model(model_key)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error stopping model: {e}")
        return jsonify({"success": False, "error": str(e)}), 500