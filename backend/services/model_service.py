"""Model management service for deployment and status tracking."""

import time
import subprocess
import threading
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# EMD functionality removed - only EC2 deployment supported

from ..core.models import model_registry
from ..utils import get_logger

logger = get_logger(__name__)

class ModelService:
    """Service for managing model deployment and status."""
    
    def __init__(self):
        """Initialize model service."""
        self.registry = model_registry
        self._deployment_status = {}

        # EC2 Docker deployment tracking
        self._ec2_deployments = {}  # Store running Docker containers info
        self._ec2_status_checkers = {}  # Store status checker threads

        # Deployment state persistence
        self._state_dir = Path("data/deployment_state")
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._deployments_file = self._state_dir / "ec2_deployments.json"
        self._status_file = self._state_dir / "deployment_status.json"

        # Load existing deployment state on startup
        self._load_deployment_state()

    def _save_deployment_state(self):
        """Save current deployment state to files."""
        try:
            # Save EC2 deployments
            with open(self._deployments_file, 'w') as f:
                json.dump(self._ec2_deployments, f, indent=2, default=str)

            # Save deployment status
            with open(self._status_file, 'w') as f:
                json.dump(self._deployment_status, f, indent=2, default=str)

            logger.debug(f"💾 Saved deployment state: {len(self._ec2_deployments)} deployments, {len(self._deployment_status)} statuses")
        except Exception as e:
            logger.error(f"❌ Failed to save deployment state: {e}")

    def _load_deployment_state(self):
        """Load deployment state from files on startup."""
        try:
            # Load EC2 deployments
            if self._deployments_file.exists():
                with open(self._deployments_file, 'r') as f:
                    self._ec2_deployments = json.load(f)
                logger.info(f"📂 Loaded {len(self._ec2_deployments)} EC2 deployments from state file")

            # Load deployment status
            if self._status_file.exists():
                with open(self._status_file, 'r') as f:
                    self._deployment_status = json.load(f)
                logger.info(f"📂 Loaded {len(self._deployment_status)} deployment statuses from state file")

            # Validate loaded deployments against running containers
            self._validate_loaded_deployments()

        except Exception as e:
            logger.error(f"❌ Failed to load deployment state: {e}")
            # Initialize with empty state on error
            self._ec2_deployments = {}
            self._deployment_status = {}

    def _validate_loaded_deployments(self):
        """Validate that loaded deployments match actual running containers."""
        if not self._ec2_deployments:
            return

        invalid_deployments = []
        for model_key, deployment_info in self._ec2_deployments.items():
            container_name = deployment_info.get("container_name")
            if not container_name or not self._check_container_running(container_name):
                logger.warning(f"⚠️ Container {container_name} for model {model_key} is not running, marking as failed")
                invalid_deployments.append(model_key)

                # Update status to reflect container not running - use not_deployed instead of failed
                # since this indicates the deployment no longer exists rather than a failure
                self._deployment_status[model_key] = {
                    "status": "not_deployed",
                    "message": "Model not currently deployed",
                    "tag": None,
                    "container_name": None
                }

        # Remove invalid deployments
        for model_key in invalid_deployments:
            del self._ec2_deployments[model_key]

        if invalid_deployments:
            logger.info(f"🧹 Cleaned up {len(invalid_deployments)} invalid deployments on startup")
            # Save the cleaned state
            self._save_deployment_state()

        # Also clean up any other stale "failed" statuses that are old
        self._cleanup_stale_failed_status()

    def _cleanup_stale_failed_status(self):
        """Clean up stale failed status entries that are no longer relevant."""
        try:
            stale_statuses = []
            current_time = datetime.now()

            for model_key, status_info in self._deployment_status.items():
                # If status is "failed" and model is not currently being deployed
                if status_info.get("status") == "failed":
                    # Check if this is a recent failure (within last 10 minutes)
                    try:
                        if "started_at" in status_info:
                            started_time = datetime.fromisoformat(status_info["started_at"])
                            time_diff = (current_time - started_time).total_seconds()
                            # If failure is older than 10 minutes, reset to not_deployed
                            if time_diff > 600:  # 10 minutes
                                stale_statuses.append(model_key)
                        else:
                            # No timestamp, consider it stale
                            stale_statuses.append(model_key)
                    except (ValueError, TypeError):
                        # Invalid timestamp, consider it stale
                        stale_statuses.append(model_key)

            # Reset stale failed statuses to not_deployed
            for model_key in stale_statuses:
                logger.info(f"🧹 Resetting stale failed status for {model_key}")
                self._deployment_status[model_key] = {
                    "status": "not_deployed",
                    "message": "Model not currently deployed",
                    "tag": None,
                    "container_name": None
                }

            if stale_statuses:
                logger.info(f"🧹 Reset {len(stale_statuses)} stale failed statuses")
                self._save_deployment_state()

        except Exception as e:
            logger.error(f"❌ Error cleaning up stale failed statuses: {e}")

    def clear_stale_deployment_status(self) -> Dict[str, Any]:
        """Manually clear stale deployment statuses. Public method for API use.

        Returns:
            Result dictionary with success status and cleared count
        """
        try:
            original_count = len([k for k, v in self._deployment_status.items() if v.get("status") == "failed"])
            self._cleanup_stale_failed_status()
            new_count = len([k for k, v in self._deployment_status.items() if v.get("status") == "failed"])
            cleared_count = original_count - new_count

            return {
                "success": True,
                "message": f"Cleared {cleared_count} stale deployment statuses",
                "cleared_count": cleared_count
            }
        except Exception as e:
            logger.error(f"❌ Error in manual status cleanup: {e}")
            return {
                "success": False,
                "error": str(e)
            }

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

        # Add deployment status for EC2 models
        ec2_models_with_status = {}
        for key, model_info in all_models.get("ec2", {}).items():
            ec2_model_info = model_info.copy()
            ec2_model_info["deployment_status"] = self.get_ec2_deployment_status(key)
            ec2_models_with_status[key] = ec2_model_info

        return {
            "status": "success",
            "models": {
                "bedrock": all_models.get("bedrock", {}),
                "ec2": ec2_models_with_status
            }
        }
    
    def get_ec2_deployment_status(self, model_key: str) -> Dict[str, Any]:
        """Get deployment status for an EC2 model.

        Args:
            model_key: EC2 model key

        Returns:
            Deployment status information
        """
        # Allow both registry EC2 models and custom models
        # Only reject Bedrock models since they don't use EC2 deployment
        if self.registry.is_bedrock_model(model_key):
            return {"status": "unknown", "message": "Bedrock models don't use EC2 deployment"}

        # Check if model is in EC2 deployments
        if model_key in self._ec2_deployments:
            deployment_info = self._ec2_deployments[model_key]
            container_name = deployment_info["container_name"]

            # Check if container is still running
            if self._check_container_running(container_name):
                # Check if health check has completed by looking at deployment status
                if model_key in self._deployment_status and self._deployment_status[model_key].get("status") == "deployed":
                    return {
                        "status": "deployed",
                        "message": "Model is deployed and ready",
                        "tag": deployment_info.get("tag"),
                        "endpoint": f"http://localhost:{deployment_info.get('port')}"
                    }
                else:
                    # Container running but health check not complete
                    current_status = self._deployment_status.get(model_key, {})
                    return {
                        "status": "inprogress",
                        "message": current_status.get("message", "Model is starting, health check in progress"),
                        "tag": deployment_info.get("tag"),
                        "endpoint": f"http://localhost:{deployment_info.get('port')}"
                    }
            else:
                # Container stopped, clean up
                if model_key in self._ec2_deployments:
                    del self._ec2_deployments[model_key]
                self._deployment_status[model_key] = {
                    "status": "not_deployed",
                    "message": "Container stopped unexpectedly",
                    "tag": None
                }

        # Fallback to cached status or default
        if model_key in self._deployment_status:
            return self._deployment_status[model_key]

        return {
            "status": "not_deployed",
            "message": "Model not deployed",
            "tag": None
        }
    
    
    def _get_current_ec2_models(self) -> Dict[str, Any]:
        """Get current EC2 deployed models.

        Returns:
            Dictionary with deployed, inprogress, and failed models
        """
        deployed = {}
        inprogress = {}
        failed = {}

        # Check EC2 deployments
        for model_key, deployment_info in self._ec2_deployments.items():
            container_name = deployment_info["container_name"]

            # Check if container is still running
            if self._check_container_running(container_name):
                # Check actual deployment status to see if health check has passed
                current_status = self._deployment_status.get(model_key, {})
                if current_status.get("status") == "deployed":
                    # Health check passed - truly deployed
                    deployed[model_key] = {
                        "tag": deployment_info.get("tag"),
                        "container_name": container_name,
                        "port": deployment_info.get("port"),
                        "endpoint": f"http://localhost:{deployment_info.get('port')}"
                    }
                else:
                    # Container running but health check not complete - still in progress
                    inprogress[model_key] = {
                        "tag": deployment_info.get("tag"),
                        "container_name": container_name,
                        "port": deployment_info.get("port"),
                        "message": current_status.get("message", "Model is starting, health check in progress")
                    }
            else:
                # Container stopped, mark as failed
                failed[model_key] = {
                    "tag": deployment_info.get("tag"),
                    "container_name": container_name,
                    "error": "Container stopped unexpectedly"
                }

        # Check deployment status for models that might be starting but not yet in _ec2_deployments
        for model_key, status_info in self._deployment_status.items():
            if (status_info.get("status") == "inprogress" and
                model_key not in deployed and
                model_key not in inprogress and
                model_key not in failed):
                inprogress[model_key] = {
                    "tag": status_info.get("tag"),
                    "container_name": status_info.get("container_name"),
                    "message": status_info.get("message", "Model deployment in progress")
                }

        return {
            "deployed": deployed,
            "inprogress": inprogress,
            "failed": failed
        }
    
    def get_current_ec2_models(self) -> List[str]:
        """Get list of currently deployed EC2 models.

        Returns:
            List of deployed model keys
        """
        try:
            current_models = self._get_current_ec2_models()
            return list(current_models.get("deployed", {}).keys())
        except Exception as e:
            logger.error(f"Failed to get current EC2 models: {e}")
            return []
    
    def check_multiple_model_status(self, models: List[str]) -> Dict[str, Any]:
        """Check deployment status for multiple models.

        Args:
            models: List of model keys to check

        Returns:
            Status results for all models
        """
        model_status = {}

        # Get all models (both registry EC2 models and custom models)
        # Consider any model that's not a bedrock model as a potential EC2/custom model
        ec2_models = [model_key for model_key in models if not self.registry.is_bedrock_model(model_key)]
        ec2_status_cache = {}

        if ec2_models:
            try:
                # Single call to get all EC2 statuses
                current_ec2_models = self._get_current_ec2_models()

                # Cache the results for all EC2 models
                for model_key in ec2_models:
                    if model_key in current_ec2_models.get("deployed", {}):
                        model_info = current_ec2_models["deployed"][model_key]
                        ec2_status_cache[model_key] = {
                            "status": "deployed",
                            "message": "Model is deployed and ready",
                            "tag": model_info.get("tag"),
                            "endpoint": model_info.get("endpoint")
                        }
                    elif model_key in current_ec2_models.get("inprogress", {}):
                        ec2_status_cache[model_key] = {
                            "status": "inprogress",
                            "message": "Model is being deployed",
                            "tag": current_ec2_models["inprogress"][model_key].get("tag")
                        }
                    elif model_key in current_ec2_models.get("failed", {}):
                        ec2_status_cache[model_key] = {
                            "status": "failed",
                            "message": "Deployment failed",
                            "tag": current_ec2_models["failed"][model_key].get("tag")
                        }
                    else:
                        # Check cached status or default
                        if model_key in self._deployment_status:
                            ec2_status_cache[model_key] = self._deployment_status[model_key]
                        else:
                            ec2_status_cache[model_key] = {
                                "status": "not_deployed",
                                "message": "Model not deployed",
                                "tag": None
                            }
            except Exception as e:
                logger.warning(f"Failed to get batch EC2 status: {e}")
                # Fallback to cached status for all EC2 models
                for model_key in ec2_models:
                    if model_key in self._deployment_status:
                        ec2_status_cache[model_key] = self._deployment_status[model_key]
                    else:
                        ec2_status_cache[model_key] = {
                            "status": "not_deployed",
                            "message": "Status check failed - may need to refresh",
                            "tag": None
                        }

        # Process all models using the cached EC2 data
        for model_key in models:
            if not self.registry.is_bedrock_model(model_key):
                # Handle both registry EC2 models and custom models
                if model_key in ec2_status_cache:
                    status_info = ec2_status_cache[model_key]
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
        try:
            return {
                "status": "success",
                "model_status": model_status  # Frontend expects 'model_status' not 'results'
            }
        except Exception as e:
            logger.error(f"Error in batch status check: {e}")
            # Return partial results for known models
            fallback_status = {}
            for model_key in models:
                if self.registry.is_bedrock_model(model_key):
                    fallback_status[model_key] = {
                        "status": "available",
                        "message": "Bedrock model is always available"
                    }
                else:
                    # Treat any non-Bedrock model as EC2/custom model
                    fallback_status[model_key] = {
                        "status": "not_deployed",
                        "message": "Status check failed - refresh may help"
                    }

            return {
                "status": "partial_success",
                "model_status": fallback_status,
                "warning": "Some status checks failed"
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
            "deleting": "deleting",
            "delete_failed": "failed",
            "not_deployed": "not_deployed",
            "failed": "failed",
            "unknown": "unknown"
        }
        return status_mapping.get(backend_status, "unknown")
    
    

    def deploy_model_on_ec2(self, model_key: str, instance_type: str = "g5.2xlarge",
                           engine_type: str = "vllm", service_type: str = "vllm_realtime",
                           port: int = 8000, tp_size: int = 1, dp_size: int = 1,
                           gpu_memory_utilization: float = 0.9, max_model_len: int = 2048) -> Dict[str, Any]:
        """Deploy a model using Docker on EC2.

        Args:
            model_key: Model to deploy
            instance_type: AWS instance type (for reference only)
            engine_type: Inference engine type (vllm, sglang)
            service_type: Service type
            port: Port to expose the service
            tp_size: Tensor parallelism size
            dp_size: Data parallelism size
            gpu_memory_utilization: GPU memory utilization fraction (0.1-1.0)
            max_model_len: Maximum model sequence length

        Returns:
            Deployment result
        """
        # Check if model is in registry, if not treat as custom model
        if self.registry.is_ec2_model(model_key):
            # Model is in registry, use registry configuration
            model_config = self.registry.get_model_info(model_key, "ec2")
            huggingface_repo = model_config.get("huggingface_repo", model_key)
            model_path = model_config.get("model_path", model_key)
        else:
            # Custom model - use model_key as Hugging Face repo name directly
            huggingface_repo = model_key
            model_path = model_key
            logger.info(f"🤗 Deploying custom model: {model_key} (not in registry)")

        # Generate deployment tag
        deployment_tag = f"{model_key}-{int(time.time())}"
        # Sanitize model_key for container name (replace slashes and underscores)
        safe_model_name = model_key.replace('/', '-').replace('_', '-').lower()
        container_name = f"{safe_model_name}-{int(time.time())}"

        # Check if model is already deployed
        if model_key in self._ec2_deployments:
            existing_container = self._ec2_deployments[model_key]
            if self._check_container_running(existing_container["container_name"]):
                return {
                    "success": False,
                    "error": f"Model {model_key} is already deployed in container {existing_container['container_name']}"
                }

        # Update deployment status to starting
        self._deployment_status[model_key] = {
            "status": "inprogress",
            "message": f"Starting Docker deployment for {model_key}",
            "tag": deployment_tag,
            "container_name": container_name,
            "port": port,
            "started_at": datetime.now().isoformat()
        }

        try:
            logger.info(f"🚀 Starting Docker deployment for {model_key} with model path {model_path} using {engine_type}")
            logger.info(f"📊 Deployment config: instance_type={instance_type}, service_type={service_type}, port={port}")
            logger.info(f"🔧 Resource config: tp_size={tp_size}, dp_size={dp_size}, gpu_memory_utilization={gpu_memory_utilization}, max_model_len={max_model_len}")

            # Construct Docker command based on framework
            if engine_type.lower() == "sglang":
                # SGLang deployment
                docker_cmd = [
                    "docker", "run", "-d",
                    "--gpus", "all",
                    "--shm-size", "32g",
                    "-v", f"{self._get_hf_cache_dir()}:/root/.cache/huggingface",
                    "-p", f"{port}:{port}",
                    "--ipc=host",
                    "--name", container_name
                ]

                # Add HuggingFace token if available
                hf_token = self._get_hf_token()
                if hf_token:
                    docker_cmd.extend(["--env", f"HF_TOKEN={hf_token}"])

                # Add SGLang image and launch command
                docker_cmd.extend([
                    "lmsysorg/sglang:latest",
                    "python3", "-m", "sglang.launch_server",
                    "--model-path", huggingface_repo,
                    "--host", "0.0.0.0",
                    "--port", str(port),
                    "--mem-fraction-static", str(gpu_memory_utilization),
                    "--max-total-tokens", str(max_model_len)
                ])

                # Add TP/DP parameters for SGLang
                if tp_size > 1:
                    docker_cmd.extend(["--tp-size", str(tp_size)])
                if dp_size > 1:
                    docker_cmd.extend(["--dp-size", str(dp_size)])

            else:
                # vLLM deployment (default)
                docker_cmd = [
                    "docker", "run", "-d",
                    "--runtime", "nvidia",
                    "--gpus", "all",
                    "-v", f"{self._get_hf_cache_dir()}:/root/.cache/huggingface",
                    "-p", f"{port}:{port}",
                    "--ipc=host",
                    "--name", container_name
                ]

                # Add HuggingFace token if available
                hf_token = self._get_hf_token()
                if hf_token:
                    docker_cmd.extend(["--env", f"HUGGING_FACE_HUB_TOKEN={hf_token}"])

                # Add vLLM image and model arguments
                docker_cmd.extend([
                    "vllm/vllm-openai:latest",
                    "--model", huggingface_repo,
                    "--host", "0.0.0.0",
                    "--port", str(port),
                    "--enable-prompt-tokens-details",
                    "--trust-remote-code",
                    "--gpu-memory-utilization", str(gpu_memory_utilization),
                    "--max-model-len", str(max_model_len)
                ])

                # Add TP/DP parameters for vLLM
                if tp_size > 1:
                    docker_cmd.extend(["--tensor-parallel-size", str(tp_size)])
                if dp_size > 1:
                    docker_cmd.extend(["--pipeline-parallel-size", str(dp_size)])

            logger.info(f"🐳 Running Docker command: {' '.join(docker_cmd)}")

            # Start Docker container
            result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=1800)

            if result.returncode == 0:
                container_id = result.stdout.strip()
                logger.info(f"✅ Docker container started successfully: {container_id}")

                # Store deployment info
                self._ec2_deployments[model_key] = {
                    "container_name": container_name,
                    "container_id": container_id,
                    "port": port,
                    "model_path": model_path,
                    "tag": deployment_tag,
                    "engine_type": engine_type,
                    "tp_size": tp_size,
                    "dp_size": dp_size,
                    "gpu_memory_utilization": gpu_memory_utilization,
                    "max_model_len": max_model_len,
                    "started_at": datetime.now().isoformat()
                }

                # Save deployment state to persist across restarts
                self._save_deployment_state()

                # Start status monitoring thread
                self._start_ec2_status_monitoring(model_key, container_name, port)

                # Update status
                self._deployment_status[model_key] = {
                    "status": "inprogress",
                    "message": f"Docker container starting, waiting for model to load...",
                    "tag": deployment_tag,
                    "container_name": container_name,
                    "container_id": container_id,
                    "port": port,
                    "engine_type": engine_type,
                    "tp_size": tp_size,
                    "dp_size": dp_size,
                    "gpu_memory_utilization": gpu_memory_utilization,
                    "max_model_len": max_model_len,
                    "started_at": datetime.now().isoformat()
                }

                return {
                    "success": True,
                    "message": f"Docker deployment started for {model_key}",
                    "tag": deployment_tag,
                    "container_name": container_name,
                    "container_id": container_id,
                    "port": port,
                    "model_key": model_key
                }

            else:
                error_msg = result.stderr or result.stdout or "Unknown Docker error"
                logger.error(f"❌ Docker deployment failed: {error_msg}")

                self._deployment_status[model_key] = {
                    "status": "failed",
                    "message": f"Docker deployment failed: {error_msg}",
                    "tag": deployment_tag,
                    "error": error_msg
                }

                return {
                    "success": False,
                    "error": f"Docker deployment failed: {error_msg}",
                    "model_key": model_key
                }

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Docker deployment timeout for {model_key}")
            self._deployment_status[model_key] = {
                "status": "failed",
                "message": "Docker deployment timeout",
                "tag": deployment_tag,
                "error": "Deployment timeout after 30 seconds"
            }
            return {
                "success": False,
                "error": "Docker deployment timeout",
                "model_key": model_key
            }
        except Exception as e:
            logger.error(f"❌ Docker deployment error for {model_key}: {e}")
            self._deployment_status[model_key] = {
                "status": "failed",
                "message": f"Docker deployment error: {str(e)}",
                "tag": deployment_tag,
                "error": str(e)
            }
            return {
                "success": False,
                "error": f"Docker deployment error: {str(e)}",
                "model_key": model_key
            }

    def _get_hf_cache_dir(self) -> str:
        """Get HuggingFace cache directory."""
        import os
        # Check multiple possible locations for HuggingFace cache
        possible_paths = [
            "/home/ubuntu/.cache/huggingface",  # Common on EC2 instances
            os.path.expanduser("~/.cache/huggingface"),  # Current user
            "/root/.cache/huggingface"  # Root user
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Default to ubuntu path (most common on EC2)
        return "/home/ubuntu/.cache/huggingface"

    def _get_hf_token(self) -> str:
        """Get HuggingFace token from environment."""
        import os
        return os.environ.get("HUGGING_FACE_HUB_TOKEN", os.environ.get("HF_TOKEN", ""))

    def _check_container_running(self, container_name: str) -> bool:
        """Check if Docker container is running."""
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name, "--format", "{{.State.Running}}"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0 and result.stdout.strip().lower() == "true"
        except:
            return False

    def _start_ec2_status_monitoring(self, model_key: str, container_name: str, port: int):
        """Start a background thread to monitor EC2 deployment status."""
        def monitor_status():
            max_wait_time = 600  # 10 minutes max wait
            check_interval = 10  # Check every 10 seconds
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                try:
                    # Check if container is still running
                    if not self._check_container_running(container_name):
                        logger.error(f"❌ Container {container_name} stopped unexpectedly")
                        self._deployment_status[model_key] = {
                            "status": "failed",
                            "message": "Docker container stopped unexpectedly",
                            "tag": self._deployment_status[model_key].get("tag"),
                            "container_name": container_name
                        }
                        break

                    # Check if model server is ready by making a health check
                    if self._check_model_health(port):
                        logger.info(f"✅ Model {model_key} is ready and healthy")
                        self._deployment_status[model_key] = {
                            "status": "deployed",
                            "message": f"Model {model_key} deployed successfully on EC2",
                            "tag": self._deployment_status[model_key].get("tag"),
                            "container_name": container_name,
                            "port": port,
                            "endpoint": f"http://localhost:{port}"
                        }
                        # Save state when deployment becomes ready
                        self._save_deployment_state()
                        break

                    time.sleep(check_interval)

                except Exception as e:
                    logger.warning(f"Status check error for {model_key}: {e}")
                    time.sleep(check_interval)

            else:
                # Timeout reached
                logger.error(f"❌ Deployment timeout for {model_key} after {max_wait_time}s")
                self._deployment_status[model_key] = {
                    "status": "failed",
                    "message": f"Deployment timeout after {max_wait_time} seconds",
                    "tag": self._deployment_status[model_key].get("tag"),
                    "container_name": container_name
                }

            # Clean up monitoring thread
            if model_key in self._ec2_status_checkers:
                del self._ec2_status_checkers[model_key]

        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_status, daemon=True)
        monitor_thread.start()
        self._ec2_status_checkers[model_key] = monitor_thread
        logger.info(f"🔍 Started status monitoring for {model_key}")

    def _check_model_health(self, port: int) -> bool:
        """Check if the model server is healthy and ready."""
        try:
            import requests
            health_url = f"http://localhost:{port}/health"
            response = requests.get(health_url, timeout=5)
            return response.status_code == 200
        except:
            # Try alternative endpoints that vLLM might expose
            try:
                import requests
                models_url = f"http://localhost:{port}/v1/models"
                response = requests.get(models_url, timeout=5)
                return response.status_code == 200
            except:
                return False

    def stop_ec2_model(self, model_key: str) -> Dict[str, Any]:
        """Stop an EC2 Docker deployment."""
        if model_key not in self._ec2_deployments:
            return {
                "success": False,
                "error": f"Model {model_key} not found in EC2 deployments"
            }

        deployment_info = self._ec2_deployments[model_key]
        container_name = deployment_info["container_name"]

        try:
            logger.info(f"🛑 Stopping Docker container for {model_key}: {container_name}")

            # Stop and remove container
            stop_result = subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True, text=True, timeout=30
            )

            subprocess.run(
                ["docker", "rm", container_name],
                capture_output=True, text=True, timeout=30
            )

            if stop_result.returncode == 0:
                logger.info(f"✅ Docker container stopped successfully: {container_name}")

                # Clean up tracking
                del self._ec2_deployments[model_key]
                if model_key in self._ec2_status_checkers:
                    del self._ec2_status_checkers[model_key]

                # Update status
                self._deployment_status[model_key] = {
                    "status": "not_deployed",
                    "message": "Model stopped successfully",
                    "tag": None
                }

                return {
                    "success": True,
                    "message": f"Model {model_key} stopped successfully",
                    "model_key": model_key
                }
            else:
                error_msg = stop_result.stderr or "Unknown error stopping container"
                logger.error(f"❌ Failed to stop container {container_name}: {error_msg}")
                return {
                    "success": False,
                    "error": f"Failed to stop container: {error_msg}",
                    "model_key": model_key
                }

        except Exception as e:
            logger.error(f"❌ Error stopping EC2 model {model_key}: {e}")
            return {
                "success": False,
                "error": f"Error stopping model: {str(e)}",
                "model_key": model_key
            }

    def register_existing_deployment(self, model_key: str, container_name: str, port: int, tag: str = None) -> Dict[str, Any]:
        """Register an existing Docker deployment that wasn't deployed through the platform.

        Args:
            model_key: Model key in the registry (e.g., "qwen3-8b")
            container_name: Name of the running Docker container
            port: Port the container is running on
            tag: Optional deployment tag

        Returns:
            Success/failure result
        """
        try:
            # Allow both registry EC2 models and custom models
            # Only reject Bedrock models since they don't use EC2 deployment
            if self.registry.is_bedrock_model(model_key):
                return {
                    "success": False,
                    "error": f"Model {model_key} is a Bedrock model and doesn't use EC2 deployment"
                }

            # Check if container is actually running
            if not self._check_container_running(container_name):
                return {
                    "success": False,
                    "error": f"Container {container_name} is not running"
                }

            # Check if already registered
            if model_key in self._ec2_deployments:
                existing = self._ec2_deployments[model_key]
                if existing["container_name"] == container_name:
                    return {
                        "success": True,
                        "message": f"Model {model_key} already registered with container {container_name}",
                        "model_key": model_key
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Model {model_key} already registered with different container {existing['container_name']}"
                    }

            # Generate tag if not provided
            if not tag:
                tag = f"manual-{int(time.time())}"

            # Get container ID
            try:
                container_id_result = subprocess.run(
                    ["docker", "inspect", container_name, "--format", "{{.Id}}"],
                    capture_output=True, text=True, timeout=10
                )
                container_id = container_id_result.stdout.strip() if container_id_result.returncode == 0 else "unknown"
            except:
                container_id = "unknown"

            # Register the deployment
            # Get model info from registry if available, otherwise use model_key as path
            if self.registry.is_ec2_model(model_key):
                model_info = self.registry.get_model_info(model_key)
                model_path = model_info.get("model_path", model_key)
            else:
                # Custom model - use model_key as path
                model_path = model_key

            self._ec2_deployments[model_key] = {
                "container_name": container_name,
                "container_id": container_id,
                "port": port,
                "model_path": model_path,
                "tag": tag,
                "deployment_time": time.time(),
                "registered_manually": True
            }

            # Set deployment status as deployed (since container is running)
            self._deployment_status[model_key] = {
                "status": "deployed",
                "message": "Model is deployed and ready (registered manually)",
                "tag": tag,
                "endpoint": f"http://localhost:{port}"
            }

            logger.info(f"✅ Manually registered existing deployment: {model_key} -> {container_name}:{port}")

            # Save state after manual registration
            self._save_deployment_state()

            return {
                "success": True,
                "message": f"Successfully registered existing deployment for {model_key}",
                "model_key": model_key,
                "container_name": container_name,
                "port": port,
                "tag": tag
            }

        except Exception as e:
            logger.error(f"❌ Error registering existing deployment: {e}")
            return {
                "success": False,
                "error": f"Error registering deployment: {str(e)}"
            }

