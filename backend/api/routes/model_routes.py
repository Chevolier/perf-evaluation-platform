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

@model_bp.route('/emd/current-models', methods=['GET'])
def get_current_emd_models():
    """Get currently deployed EMD models."""
    try:
        deployed_models = model_service.get_current_emd_models()
        return jsonify({
            "status": "success",
            "deployed": deployed_models
        })
    except Exception as e:
        logger.error(f"Error getting current EMD models: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@model_bp.route('/emd/init', methods=['POST'])
def init_emd():
    """Initialize EMD environment."""
    try:
        data = request.get_json() or {}
        region = data.get('region', 'us-west-2')
        result = model_service.initialize_emd(region)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error initializing EMD: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@model_bp.route('/deploy-models', methods=['POST'])
def deploy_models():
    """Deploy models using different deployment methods."""
    try:
        data = request.get_json() or {}
        models = data.get('models', [])
        instance_type = data.get('instance_type', 'ml.g5.2xlarge')
        engine_type = data.get('engine_type', 'vllm')
        service_type = data.get('service_type', 'sagemaker_realtime')

        # Get deployment method - defaults to 'EMD' for backward compatibility
        method = data.get('method', 'EMD')

        # Get TP/DP parameters for EC2 deployment
        tp_size = data.get('tpSize', 1)
        dp_size = data.get('dpSize', 1)

        print(f"🚀 DEBUG: Deploy request received:")
        print(f"  Models: {models}")
        print(f"  Method: {method}")
        print(f"  Instance type: {instance_type}")
        print(f"  Engine type: {engine_type}")
        print(f"  Service type: {service_type}")
        print(f"  TP size: {tp_size}")
        print(f"  DP size: {dp_size}")

        results = {}
        for model_key in models:
            print(f"🚀 DEBUG: Deploying model: {model_key}")

            if method == 'EC2':
                # Use EC2 Docker deployment
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
            else:
                # Use EMD deployment (default)
                result = model_service.deploy_emd_model(
                    model_key=model_key,
                    instance_type=instance_type,
                    engine_type=engine_type,
                    service_type=service_type
                )

            print(f"🚀 DEBUG: Deployment result for {model_key}: {result}")
            results[model_key] = result

        return jsonify({
            "status": "success",
            "results": results
        })
    except Exception as e:
        logger.error(f"Error deploying models: {e}")
        print(f"❌ DEBUG: Error deploying models: {e}")
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

@model_bp.route('/emd/status', methods=['GET'])
def get_emd_status():
    """Get EMD environment status."""
    try:
        status_info = model_service.get_emd_info()
        return jsonify(status_info)
    except Exception as e:
        logger.error(f"Error getting EMD status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@model_bp.route('/emd/config/tag', methods=['POST'])
def set_emd_tag():
    """Set EMD deployment tag."""
    try:
        data = request.get_json() or {}
        tag = data.get('tag')
        if not tag:
            return jsonify({"success": False, "error": "Tag is required"}), 400
        
        result = model_service.set_emd_tag(tag)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error setting EMD tag: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@model_bp.route('/delete-model', methods=['POST'])
def delete_model():
    """Delete an EMD model deployment."""
    try:
        data = request.get_json() or {}
        model_key = data.get('model_key')
        
        if not model_key:
            return jsonify({"success": False, "error": "Model key is required"}), 400
        
        result = model_service.delete_emd_model(model_key)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        return jsonify({"success": False, "error": str(e)}), 500