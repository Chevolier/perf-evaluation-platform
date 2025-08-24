"""API routes for model inference."""

from flask import Blueprint, request, Response
from ...services.inference_service import InferenceService
from ...utils import get_logger

logger = get_logger(__name__)
inference_bp = Blueprint('inference', __name__)

# Initialize service
inference_service = InferenceService()

@inference_bp.route('/multi-inference', methods=['POST'])
def multi_inference():
    """Run inference on multiple models simultaneously with streaming results."""
    try:
        data = request.get_json()
        logger.info(f"Multi-inference request received with data: {data}")
        
        if not data:
            logger.error("No JSON data provided in multi-inference request")
            return {"status": "error", "message": "No JSON data provided"}, 400
        
        # Stream results back to client using Server-Sent Events
        logger.info("Starting streaming response for multi-inference")
        return Response(
            inference_service.multi_inference(data),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in multi-inference: {e}")
        return {"status": "error", "message": str(e)}, 500

@inference_bp.route('/inference', methods=['POST'])
def single_inference():
    """Run inference on a single model."""
    try:
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "No JSON data provided"}, 400
        
        model = data.get('model')
        if not model:
            return {"status": "error", "message": "No model specified"}, 400
        
        # Use multi-inference with single model for consistency
        results = list(inference_service.multi_inference({**data, 'models': [model]}))
        
        # Return the first (and only) result
        if results:
            import json
            return json.loads(results[0])
        else:
            return {"status": "error", "message": "No results returned"}, 500
            
    except Exception as e:
        logger.error(f"Error in single inference: {e}")
        return {"status": "error", "message": str(e)}, 500