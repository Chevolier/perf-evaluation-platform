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
    """Deploy EMD models."""
    try:
        data = request.get_json() or {}
        models = data.get('models', [])
        instance_type = data.get('instance_type', 'ml.g5.2xlarge')
        engine_type = data.get('engine_type', 'vllm')
        service_type = data.get('service_type', 'sagemaker_realtime')
        
        print(f"🚀 DEBUG: Deploy request received:")
        print(f"  Models: {models}")
        print(f"  Instance type: {instance_type}")
        print(f"  Engine type: {engine_type}")
        print(f"  Service type: {service_type}")
        
        results = {}
        for model_key in models:
            print(f"🚀 DEBUG: Deploying model: {model_key}")
            result = model_service.deploy_emd_model(model_key, instance_type, engine_type, service_type)
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


@model_bp.route('/register-deployment-endpoint', methods=['POST'])
def register_deployment_endpoint():
    """Register an external deployment endpoint (HyperPod, EKS, EC2, etc.)."""
    try:
        data = request.get_json() or {}

        deployment_method = data.get('deployment_method')
        endpoint_url = data.get('endpoint_url')
        deployment_id = data.get('deployment_id')
        model_name = data.get('model_name')
        model_key = data.get('model_key')
        metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else None
        status = data.get('status', 'active')

        if not deployment_method or not endpoint_url:
            return jsonify({
                "status": "error",
                "message": "deployment_method and endpoint_url are required"
            }), 400

        result = model_service.register_external_endpoint(
            deployment_method=deployment_method,
            endpoint_url=endpoint_url,
            deployment_id=deployment_id,
            model_name=model_name,
            model_key=model_key,
            metadata=metadata,
            status=status
        )

        return jsonify({
            "status": "success",
            "model_key": result["model_key"],
            "model": result["model"]
        })

    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        logger.exception("Error registering deployment endpoint: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500

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
