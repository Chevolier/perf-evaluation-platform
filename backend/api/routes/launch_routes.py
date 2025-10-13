"""Launch API routes for unified model deployment."""

from flask import Blueprint, request, jsonify
from typing import Dict, Any

from ...services.launch_service import LaunchService
from ...utils import get_logger

logger = get_logger(__name__)

# Create blueprint
launch_bp = Blueprint('launch', __name__)

# Initialize launch service
launch_service = LaunchService()


@launch_bp.route('/launch-methods', methods=['GET'])
def get_launch_methods():
    """Return available launch methods and their schemas.
    
    Returns:
        JSON response with launch method definitions
    """
    try:
        result = launch_service.get_launch_methods()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting launch methods: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@launch_bp.route('/launches', methods=['POST'])
def create_launch():
    """Create a new launch job.
    
    Request body:
        {
            "method": "SAGEMAKER_ENDPOINT",
            "model_key": "qwen3-8b",
            "engine": "vllm",
            "params": {...},
            "user_id": "optional"
        }
    
    Returns:
        JSON response with job information
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        # Extract required fields
        method = data.get('method')
        model_key = data.get('model_key')
        engine = data.get('engine')
        params = data.get('params', {})
        user_id = data.get('user_id')
        
        # Validate required fields
        if not method:
            return jsonify({
                'success': False,
                'error': 'method is required'
            }), 400
        
        if not model_key:
            return jsonify({
                'success': False,
                'error': 'model_key is required'
            }), 400
        
        if not engine:
            return jsonify({
                'success': False,
                'error': 'engine is required'
            }), 400
        
        # Create launch
        result = launch_service.create_launch(
            method=method,
            model_key=model_key,
            engine=engine,
            params=params,
            user_id=user_id
        )
        
        if result.get('success'):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating launch: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@launch_bp.route('/launches/<job_id>', methods=['GET'])
def get_launch_status(job_id: str):
    """Get launch job status.
    
    Args:
        job_id: Job identifier
        
    Returns:
        JSON response with job status
    """
    try:
        result = launch_service.get_launch_status(job_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error getting launch status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@launch_bp.route('/launches', methods=['GET'])
def list_launches():
    """List launch jobs with pagination.
    
    Query parameters:
        - method: Filter by launch method
        - status: Filter by job status
        - model_key: Filter by model
        - user_id: Filter by user
        - limit: Maximum number of results (default: 50)
        - offset: Number of results to skip (default: 0)
    
    Returns:
        JSON response with list of jobs
    """
    try:
        # Extract query parameters
        filters = {}
        if request.args.get('method'):
            filters['method'] = request.args.get('method')
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('model_key'):
            filters['model_key'] = request.args.get('model_key')
        if request.args.get('user_id'):
            filters['user_id'] = request.args.get('user_id')
        
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Validate parameters
        if limit < 1 or limit > 1000:
            return jsonify({
                'success': False,
                'error': 'limit must be between 1 and 1000'
            }), 400
        
        if offset < 0:
            return jsonify({
                'success': False,
                'error': 'offset must be >= 0'
            }), 400
        
        result = launch_service.list_launches(
            filters=filters if filters else None,
            limit=limit,
            offset=offset
        )
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid parameter: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Error listing launches: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@launch_bp.route('/launches/<job_id>', methods=['DELETE'])
def cancel_launch(job_id: str):
    """Cancel a launch job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        JSON response with cancellation result
    """
    try:
        result = launch_service.cancel_launch(job_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error cancelling launch: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@launch_bp.route('/launches/<job_id>/status', methods=['POST'])
def poll_launch_status(job_id: str):
    """Poll external system for launch job status update.
    
    Args:
        job_id: Job identifier
        
    Returns:
        JSON response with updated status
    """
    try:
        result = launch_service.poll_job_status(job_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error polling launch status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@launch_bp.route('/models/<model_key>/launch-info', methods=['GET'])
def get_model_launch_info(model_key: str):
    """Get launch information for a specific model.
    
    Args:
        model_key: Model identifier
        
    Returns:
        JSON response with model launch capabilities
    """
    try:
        result = launch_service.get_model_launch_info(model_key)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error getting model launch info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
