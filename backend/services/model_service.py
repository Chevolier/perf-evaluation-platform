"""Model management service for deployment and status tracking."""

import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

try:
    from emd.sdk.status import get_model_status
    from emd.sdk.deploy import deploy as emd_deploy
    EMD_AVAILABLE = True
except ImportError:
    EMD_AVAILABLE = False

from ..core.models import ModelRegistry, model_registry, EMDModel, BedrockModel
from ..config import get_config
from ..utils import get_logger, generate_session_id


logger = get_logger(__name__)


class ModelService:
    """Service for managing model deployment and status."""
    
    def __init__(self):
        """Initialize model service."""
        self.registry = model_registry
        self._deployment_status = {}
        self._current_emd_tag = None
    
    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all available models.
        
        Returns:
            Dictionary of all models organized by type
        """
        return self.registry.get_all_models()
    
    def get_model_list(self) -> Dict[str, Any]:
        """Get formatted model list for API responses.
        
        Returns:
            Formatted model list with status information
        """
        all_models = self.get_all_models()
        
        # Add deployment status for EMD models
        emd_models_with_status = {}
        for key, model_info in all_models["emd"].items():
            emd_model_info = model_info.copy()
            emd_model_info["deployment_status"] = self.get_emd_deployment_status(key)
            emd_models_with_status[key] = emd_model_info
        
        return {
            "status": "success",
            "models": {
                "bedrock": all_models["bedrock"],
                "emd": emd_models_with_status
            }
        }
    
    def get_emd_deployment_status(self, model_key: str) -> Dict[str, Any]:
        """Get deployment status for an EMD model.
        
        Args:
            model_key: EMD model key
            
        Returns:
            Deployment status information
        """
        if not self.registry.is_emd_model(model_key):
            return {"status": "unknown", "message": "Model not found"}
        
        # Try to get real EMD status if SDK is available
        if EMD_AVAILABLE:
            try:
                # Get all deployed models using the same approach as original backend
                deployed_models = self._get_current_emd_models()
                
                if model_key in deployed_models.get("deployed", {}):
                    model_info = deployed_models["deployed"][model_key]
                    return {
                        "status": "deployed",
                        "message": "Model is deployed and ready",
                        "tag": model_info.get("tag"),
                        "endpoint": model_info.get("endpoint")
                    }
                elif model_key in deployed_models.get("inprogress", {}):
                    return {
                        "status": "deploying",
                        "message": "Model is being deployed",
                        "tag": deployed_models["inprogress"][model_key].get("tag")
                    }
                elif model_key in deployed_models.get("failed", {}):
                    return {
                        "status": "failed",
                        "message": "Deployment failed",
                        "tag": deployed_models["failed"][model_key].get("tag")
                    }
                
            except Exception as e:
                logger.warning(f"Failed to get EMD status for {model_key}: {e}")
        
        # Fallback to cached status or default
        if model_key in self._deployment_status:
            return self._deployment_status[model_key]
        
        return {
            "status": "not_deployed",
            "message": "Model not deployed",
            "tag": None
        }
    
    def _get_current_emd_models(self) -> Dict[str, Any]:
        """Get current EMD models using the same approach as original backend.
        
        Returns:
            Dictionary with deployed, inprogress, and failed models
        """
        try:
            # Call get_model_status() without parameters to get all models
            status = get_model_status()
            logger.info(f"EMD SDK get_model_status returned: {status}")
            
            # Create reverse mapping from model_path to model_key
            reverse_mapping = {}
            for model_key, model_info in self.registry.get_emd_models().items():
                model_path = model_info.get("model_path", model_key)
                reverse_mapping[model_path] = model_key
            
            deployed = {}
            inprogress = {}
            failed = {}
            
            # Process completed models
            for model in status.get("completed", []):
                model_id = model.get("model_id")
                model_tag = model.get("model_tag")
                stack_status = model.get("stack_status", "")  # Use stack_status, not status
                
                if model_id in reverse_mapping:
                    model_key = reverse_mapping[model_id]
                    if "CREATE_COMPLETE" in stack_status:
                        deployed[model_key] = {
                            "tag": model_tag,
                            "model_id": model_id,
                            "status": stack_status
                        }
                    elif "FAILED" in stack_status:
                        failed[model_key] = {
                            "tag": model_tag,
                            "model_id": model_id,
                            "status": stack_status
                        }
            
            # Process in-progress models
            for model in status.get("inprogress", []):
                model_id = model.get("model_id")
                model_tag = model.get("model_tag")
                stack_status = model.get("stack_status", "")  # Use stack_status, not status
                
                if model_id in reverse_mapping:
                    model_key = reverse_mapping[model_id]
                    inprogress[model_key] = {
                        "tag": model_tag,
                        "model_id": model_id,
                        "status": stack_status
                    }
            
            return {
                "deployed": deployed,
                "inprogress": inprogress,
                "failed": failed
            }
            
        except Exception as e:
            logger.error(f"Failed to get current EMD models: {e}")
            return {"deployed": {}, "inprogress": {}, "failed": {}}
    
    def get_current_emd_models(self) -> List[str]:
        """Get list of currently deployed EMD models.
        
        Returns:
            List of deployed model keys
        """
        try:
            current_models = self._get_current_emd_models()
            return list(current_models.get("deployed", {}).keys())
        except Exception as e:
            logger.error(f"Failed to get current EMD models: {e}")
            return []
    
    def initialize_emd(self, region: str = "us-west-2") -> Dict[str, Any]:
        """Initialize EMD environment.
        
        Args:
            region: AWS region
            
        Returns:
            Initialization result
        """
        try:
            # Mock implementation - in production this would use EMD SDK
            logger.info(f"Initializing EMD environment in region {region}")
            return {
                "success": True,
                "message": f"EMD environment initialized in {region}",
                "region": region
            }
        except Exception as e:
            logger.error(f"Failed to initialize EMD: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def deploy_emd_model(self, model_key: str, instance_type: str = "ml.g5.2xlarge",
                        engine_type: str = "vllm") -> Dict[str, Any]:
        """Deploy an EMD model.
        
        Args:
            model_key: Model to deploy
            instance_type: AWS instance type
            engine_type: Inference engine type
            
        Returns:
            Deployment result
        """
        if not self.registry.is_emd_model(model_key):
            return {
                "success": False,
                "error": f"Model {model_key} not found in EMD registry"
            }
        
        model_config = self.registry.get_model_info(model_key, "emd")
        emd_model = EMDModel(model_key, model_config)
        
        # Validate deployment configuration
        is_valid, error_msg = emd_model.validate_deployment_config(instance_type, engine_type)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg
            }
        
        # Generate deployment tag
        deployment_tag = emd_model.generate_tag()
        
        # Update deployment status
        self._deployment_status[model_key] = {
            "status": "deploying",
            "message": f"Deploying {model_key} with tag {deployment_tag}",
            "tag": deployment_tag,
            "instance_type": instance_type,
            "engine_type": engine_type,
            "started_at": datetime.now().isoformat()
        }
        
        # Trigger actual EMD deployment
        if EMD_AVAILABLE:
            try:
                model_path = model_config.get("model_path", model_key)
                
                # Map frontend engine types to EMD framework types
                framework_mapping = {
                    "vllm": "vllm",
                    "sglang": "sglang", 
                    "tgi": "tgi",
                    "transformers": "hf"
                }
                framework_type = framework_mapping.get(engine_type, engine_type)
                
                logger.info(f"Starting EMD deployment for {model_key} (model_path: {model_path}) with tag {deployment_tag}")
                
                # Call EMD deployment
                result = emd_deploy(
                    model_id=model_path,
                    instance_type=instance_type,
                    engine_type=framework_type,
                    model_tag=deployment_tag,
                    waiting_until_deploy_complete=False  # Don't wait, return immediately
                )
                
                logger.info(f"EMD deployment initiated for {model_key}: {result}")
                
                # Update status to deploying
                self._deployment_status[model_key] = {
                    "status": "deploying",
                    "message": f"Deployment in progress for {model_key}",
                    "tag": deployment_tag,
                    "instance_type": instance_type,
                    "engine_type": engine_type,
                    "started_at": datetime.now().isoformat()
                }
                
                return {
                    "success": True,
                    "message": f"Deployment started for {model_key}",
                    "tag": deployment_tag,
                    "model_key": model_key,
                    "deployment_result": result
                }
                
            except Exception as e:
                logger.error(f"Failed to deploy {model_key} via EMD: {e}")
                # Update status to failed
                self._deployment_status[model_key] = {
                    "status": "failed",
                    "message": f"Deployment failed: {str(e)}",
                    "tag": deployment_tag,
                    "error": str(e)
                }
                return {
                    "success": False,
                    "error": f"Deployment failed: {str(e)}",
                    "model_key": model_key
                }
        else:
            logger.warning("EMD SDK not available - deployment will be mocked")
            logger.info(f"Mock deployment started for {model_key} with tag {deployment_tag}")
            
            return {
                "success": True,
                "message": f"Mock deployment started for {model_key}",
                "tag": deployment_tag,
                "model_key": model_key,
                "note": "EMD SDK not available - this is a mock deployment"
            }
    
    def check_multiple_model_status(self, models: List[str]) -> Dict[str, Any]:
        """Check deployment status for multiple models.
        
        Args:
            models: List of model keys to check
            
        Returns:
            Status results for all models
        """
        model_status = {}
        
        for model_key in models:
            if self.registry.is_emd_model(model_key):
                status_info = self.get_emd_deployment_status(model_key)
                # Map our status format to what frontend expects
                model_status[model_key] = {
                    "status": self._map_status_for_frontend(status_info.get("status")),
                    "message": status_info.get("message", ""),
                    "tag": status_info.get("tag"),
                    "endpoint": status_info.get("endpoint")
                }
            elif self.registry.is_bedrock_model(model_key):
                model_status[model_key] = {
                    "status": "available",
                    "message": "Bedrock model is always available"
                }
            else:
                model_status[model_key] = {
                    "status": "unknown",
                    "message": "Model not found"
                }
        
        return {
            "status": "success",
            "model_status": model_status  # Frontend expects 'model_status' not 'results'
        }
    
    def _map_status_for_frontend(self, backend_status: str) -> str:
        """Map backend status to frontend status format.
        
        Args:
            backend_status: Status from backend
            
        Returns:
            Status format expected by frontend
        """
        status_mapping = {
            "deployed": "deployed",
            "deploying": "deploying", 
            "not_deployed": "not_deployed",
            "failed": "failed",
            "unknown": "unknown"
        }
        return status_mapping.get(backend_status, "unknown")
    
    def get_emd_info(self) -> Dict[str, Any]:
        """Get EMD environment information.
        
        Returns:
            EMD environment info
        """
        try:
            config = get_config()
            return {
                "status": "success",
                "base_url": config.get("models.emd.base_url", "http://localhost:8000"),
                "current_tag": self._current_emd_tag,
                "available": EMD_AVAILABLE,
                "deployed_models": self.get_current_emd_models()
            }
        except Exception as e:
            logger.error(f"Error getting EMD info: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def set_emd_tag(self, tag: str) -> Dict[str, Any]:
        """Set EMD deployment tag.
        
        Args:
            tag: Deployment tag to set
            
        Returns:
            Operation result
        """
        try:
            self._current_emd_tag = tag
            logger.info(f"Set EMD tag to: {tag}")
            return {
                "success": True,
                "message": f"EMD tag set to {tag}",
                "tag": tag
            }
        except Exception as e:
            logger.error(f"Error setting EMD tag: {e}")
            return {
                "success": False,
                "error": str(e)
            }