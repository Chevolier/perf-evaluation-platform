"""Model management service for deployment and status tracking."""

import time
import random
from typing import Dict, Any, List
from datetime import datetime

try:
    from emd.sdk.status import get_model_status
    from emd.sdk.deploy import deploy as emd_deploy
    EMD_AVAILABLE = True
except ImportError:
    EMD_AVAILABLE = False

from ..core.models import model_registry, EMDModel
from ..config import get_config
from ..utils import get_logger


logger = get_logger(__name__)


class ModelService:
    """Service for managing model deployment and status."""
    
    def __init__(self):
        """Initialize model service."""
        self.registry = model_registry
        self._deployment_status = {}
        self._current_emd_tag = None
        
        # Circuit breaker for AWS throttling
        self._circuit_breaker = {
            'state': 'closed',  # closed, open, half_open
            'failure_count': 0,
            'last_failure_time': None,
            'failure_threshold': 3,  # Open circuit after 3 consecutive failures
            'recovery_timeout': 60,  # Try again after 60 seconds
            'half_open_success_threshold': 1  # Close circuit after 1 success in half-open
        }
        
        # Enhanced caching for throttling scenarios
        self._emd_status_cache = {
            'data': None,
            'timestamp': None,
            'extended_ttl': 300  # 5 minutes extended cache for throttling
        }
    
    def _should_circuit_break(self) -> bool:
        """Check if circuit breaker should prevent EMD calls."""
        circuit = self._circuit_breaker
        now = time.time()
        
        if circuit['state'] == 'closed':
            return False
        elif circuit['state'] == 'open':
            # Check if recovery timeout has passed
            if circuit['last_failure_time'] and (now - circuit['last_failure_time']) > circuit['recovery_timeout']:
                circuit['state'] = 'half_open'
                logger.info("🔄 Circuit breaker switching to half-open state")
                return False
            return True
        elif circuit['state'] == 'half_open':
            return False
        
        return False
    
    def _record_circuit_success(self):
        """Record successful EMD call."""
        circuit = self._circuit_breaker
        if circuit['state'] == 'half_open':
            circuit['state'] = 'closed'
            circuit['failure_count'] = 0
            logger.info("✅ Circuit breaker closed - EMD calls restored")
        elif circuit['state'] == 'closed':
            circuit['failure_count'] = max(0, circuit['failure_count'] - 1)
    
    def _record_circuit_failure(self):
        """Record failed EMD call."""
        circuit = self._circuit_breaker
        circuit['failure_count'] += 1
        circuit['last_failure_time'] = time.time()
        
        if circuit['failure_count'] >= circuit['failure_threshold']:
            circuit['state'] = 'open'
            logger.warning(f"🚫 Circuit breaker opened - EMD calls suspended for {circuit['recovery_timeout']}s due to {circuit['failure_count']} consecutive failures")
    
    def _get_cached_emd_data(self) -> Dict[str, Any]:
        """Get cached EMD data if available."""
        cache = self._emd_status_cache
        if cache['data'] and cache['timestamp']:
            age = time.time() - cache['timestamp']
            # Use extended TTL during circuit breaker scenarios
            ttl = cache['extended_ttl'] if self._circuit_breaker['state'] != 'closed' else 60
            if age < ttl:
                logger.info(f"🎯 Using cached EMD data (age: {age:.1f}s, circuit: {self._circuit_breaker['state']})")
                return cache['data']
        return None
    
    def _cache_emd_data(self, data: Dict[str, Any]):
        """Cache EMD data."""
        self._emd_status_cache['data'] = data
        self._emd_status_cache['timestamp'] = time.time()
    
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
                        "status": "inprogress",  # Frontend expects 'inprogress'
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
    
    def _retry_with_exponential_backoff(self, func, max_retries=3, base_delay=1):
        """Retry function with exponential backoff for throttling errors."""
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                error_str = str(e).lower()
                if 'throttling' in error_str or 'rate exceeded' in error_str:
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Throttling detected, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded for throttling error: {e}")
                        # Return empty result instead of failing completely
                        return {"deployed": {}, "inprogress": {}, "failed": {}}
                else:
                    # Non-throttling error, re-raise immediately
                    raise e
        return {"deployed": {}, "inprogress": {}, "failed": {}}
    
    def _get_current_emd_models(self) -> Dict[str, Any]:
        """Get current EMD models using the same approach as original backend.
        
        Returns:
            Dictionary with deployed, inprogress, and failed models
        """
        # Check circuit breaker and use cached data if available
        if self._should_circuit_break():
            cached_data = self._get_cached_emd_data()
            if cached_data:
                return cached_data
            else:
                logger.warning("🚫 Circuit breaker active but no cached data available")
                return {"deployed": {}, "inprogress": {}, "failed": {}}
        
        # Try to use cached data first (normal 60s TTL when circuit is closed)
        cached_data = self._get_cached_emd_data()
        if cached_data:
            return cached_data
        
        def _get_status():
            status = get_model_status()
            logger.info(f"EMD SDK get_model_status returned: {status}")
            return status
        
        try:
            # Use retry wrapper for AWS API calls that might get throttled
            status = self._retry_with_exponential_backoff(_get_status, max_retries=2, base_delay=0.5)
            
            # Create reverse mapping from model_path to model_key
            reverse_mapping = {}
            for model_key, model_info in self.registry.get_emd_models().items():
                model_path = model_info.get("model_path", model_key)
                reverse_mapping[model_path] = model_key
            
            # print(f"🔍 DEBUG: Reverse mapping: {reverse_mapping}")
            # print(f"🔍 DEBUG: Models in EMD status - completed: {[m.get('model_id') for m in status.get('completed', [])]}")
            # print(f"🔍 DEBUG: Models in EMD status - inprogress: {[m.get('model_id') for m in status.get('inprogress', [])]}")
            
            deployed = {}
            inprogress = {}
            failed = {}
            
            # First, process completed models (higher priority)
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
            
            # Process in-progress models (only if not already in deployed/failed)
            for model in status.get("inprogress", []):
                model_id = model.get("model_id")
                model_tag = model.get("model_tag")
                stack_status = model.get("stack_status", "")  # Use stack_status, not status
                
                if model_id in reverse_mapping:
                    model_key = reverse_mapping[model_id]
                    
                    # Skip if already processed as deployed or failed
                    if model_key in deployed or model_key in failed:
                        continue
                    
                    # Check execution_info for pipeline status (more accurate than stack_status for in-progress)
                    execution_info = model.get("execution_info", {})
                    pipeline_status = execution_info.get("status", "")
                    
                    # If pipeline failed, move to failed category
                    if pipeline_status == "Failed":
                        failed[model_key] = {
                            "tag": model_tag,
                            "model_id": model_id,
                            "status": pipeline_status,
                            "stage": model.get("stage_name", "")
                        }
                    else:
                        # Still in progress
                        inprogress[model_key] = {
                            "tag": model_tag,
                            "model_id": model_id,
                            "status": stack_status or pipeline_status,
                            "stage": model.get("stage_name", "")
                        }
            
            result = {
                "deployed": deployed,
                "inprogress": inprogress,
                "failed": failed
            }
            # print(f"🔍 DEBUG: Processed EMD status - deployed: {deployed}, inprogress: {inprogress}, failed: {failed}")
            
            # Cache successful result and record circuit breaker success
            self._cache_emd_data(result)
            self._record_circuit_success()
            
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Record circuit breaker failure
            self._record_circuit_failure()
            
            if 'throttling' in error_str or 'rate exceeded' in error_str or 'timeout' in error_str:
                logger.warning(f"🔥 AWS API issue detected (circuit: {self._circuit_breaker['state']}): {e}")
                
                # Try to return cached data during failures
                cached_data = self._get_cached_emd_data()
                if cached_data:
                    logger.info("🎯 Returning cached data due to AWS API failure")
                    return cached_data
            else:
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
    
    def deploy_emd_model(self, model_key: str, instance_type: str = "g5.2xlarge",
                        engine_type: str = "vllm", service_type: str = "sagemaker_realtime") -> Dict[str, Any]:
        """Deploy an EMD model.
        
        Args:
            model_key: Model to deploy
            instance_type: AWS instance type
            engine_type: Inference engine type
            service_type: Service type (sagemaker_realtime, sagemaker_async, ecs, local)
            
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
            "status": "inprogress",  # Frontend expects 'inprogress'
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
                print(f"🚀 DEBUG: Starting EMD deployment for {model_key} (model_path: {model_path}) with tag {deployment_tag}")
                
                # Call EMD deployment with correct parameters matching CLI format
                result = emd_deploy(
                    model_id=model_path,
                    instance_type=instance_type,
                    engine_type=framework_type,
                    service_type=service_type,  # Use the service_type parameter from API request
                    framework_type="fastapi",  # Default framework type
                    model_tag=deployment_tag,
                    waiting_until_deploy_complete=False  # Don't wait, return immediately
                )
                
                logger.info(f"EMD deployment initiated for {model_key}: {result}")
                
                # Update status to inprogress (matches frontend expectation)
                self._deployment_status[model_key] = {
                    "status": "inprogress",  # Frontend expects 'inprogress' not 'deploying'
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
                print(f"❌ DEBUG: Failed to deploy {model_key} via EMD: {e}")
                print(f"❌ DEBUG: Error type: {type(e)}")
                print(f"❌ DEBUG: Error args: {e.args}")
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
        """Check deployment status for multiple models with throttling protection.
        
        Args:
            models: List of model keys to check
            
        Returns:
            Status results for all models
        """
        def _check_status():
            model_status = {}
            
            # Get all EMD model statuses in a single call to reduce API calls
            emd_models = [model_key for model_key in models if self.registry.is_emd_model(model_key)]
            emd_status_cache = {}
            
            if emd_models and EMD_AVAILABLE:
                try:
                    # Single call to get all EMD statuses
                    current_emd_models = self._get_current_emd_models()
                    
                    # Cache the results for all EMD models
                    for model_key in emd_models:
                        if model_key in current_emd_models.get("deployed", {}):
                            model_info = current_emd_models["deployed"][model_key]
                            emd_status_cache[model_key] = {
                                "status": "deployed",
                                "message": "Model is deployed and ready",
                                "tag": model_info.get("tag"),
                                "endpoint": model_info.get("endpoint")
                            }
                        elif model_key in current_emd_models.get("inprogress", {}):
                            emd_status_cache[model_key] = {
                                "status": "inprogress",
                                "message": "Model is being deployed",
                                "tag": current_emd_models["inprogress"][model_key].get("tag")
                            }
                        elif model_key in current_emd_models.get("failed", {}):
                            emd_status_cache[model_key] = {
                                "status": "failed",
                                "message": "Deployment failed",
                                "tag": current_emd_models["failed"][model_key].get("tag")
                            }
                        else:
                            # Check cached status or default
                            if model_key in self._deployment_status:
                                emd_status_cache[model_key] = self._deployment_status[model_key]
                            else:
                                emd_status_cache[model_key] = {
                                    "status": "not_deployed",
                                    "message": "Model not deployed",
                                    "tag": None
                                }
                except Exception as e:
                    logger.warning(f"Failed to get batch EMD status: {e}")
                    # Fallback to cached status for all EMD models
                    for model_key in emd_models:
                        if model_key in self._deployment_status:
                            emd_status_cache[model_key] = self._deployment_status[model_key]
                        else:
                            emd_status_cache[model_key] = {
                                "status": "not_deployed",
                                "message": "Status check failed - may need to refresh",
                                "tag": None
                            }
            
            # Process all models using the cached EMD data
            for model_key in models:
                if self.registry.is_emd_model(model_key):
                    if model_key in emd_status_cache:
                        status_info = emd_status_cache[model_key]
                    else:
                        # Fallback for models not in cache
                        status_info = {
                            "status": "not_deployed",
                            "message": "Model not deployed",
                            "tag": None
                        }
                    
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
            return model_status
        
        try:
            # Use retry wrapper for status checks that might get throttled
            model_status = self._retry_with_exponential_backoff(_check_status, max_retries=2, base_delay=0.3)
            
            return {
                "status": "success",
                "model_status": model_status  # Frontend expects 'model_status' not 'results'
            }
        except Exception as e:
            logger.error(f"Error in batch status check: {e}")
            # Return partial results for known models
            fallback_status = {}
            for model_key in models:
                fallback_status[model_key] = {
                    "status": "not_deployed" if self.registry.is_emd_model(model_key) else "available",
                    "message": "Status check failed - refresh may help" if self.registry.is_emd_model(model_key) else "Bedrock model is always available"
                }
            
            return {
                "status": "partial_success",
                "model_status": fallback_status,
                "warning": "Some status checks failed due to API limits"
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
            "deploying": "inprogress",  # Map 'deploying' to 'inprogress' for frontend
            "inprogress": "inprogress",
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