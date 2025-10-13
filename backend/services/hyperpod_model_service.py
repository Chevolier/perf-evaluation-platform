"""Service for deploying and managing models on HyperPod clusters."""

from __future__ import annotations

import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..utils import get_logger

logger = get_logger(__name__)


class HyperPodModelService:
    """Manage model deployments on HyperPod EKS clusters."""

    def __init__(self) -> None:
        self._config_manager = get_config()
        self._project_root = Path(__file__).resolve().parents[2]
        self._scripts_dir = self._project_root / "scripts"
        self._k8s_dir = self._project_root / "k8s" / "hyperpod"
        
        self._deployments: Dict[str, Dict[str, Any]] = {}
        self._deployments_lock = threading.Lock()
        
        # Ensure directories exist
        self._k8s_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        """Check if HyperPod model deployment is available."""
        deploy_script = self._scripts_dir / "deploy_hyperpod_model.sh"
        return deploy_script.exists() and deploy_script.is_file()

    def deploy_model(
        self,
        model_name: str,
        *,
        cluster_name: str = "eks",
        region: str = "us-east-1",
        role_arn: Optional[str] = None,
        engine: str = "vllm",
        use_fsx: bool = False,
        namespace: str = "default",
        dry_run: bool = False,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deploy a model to HyperPod cluster.
        
        Args:
            model_name: Model identifier (e.g., 'qwen3-0.6b')
            cluster_name: EKS cluster name
            region: AWS region
            role_arn: IAM role ARN for cluster access
            engine: Inference engine (vllm, sglang)
            use_fsx: Use FSx Lustre for model storage
            namespace: Kubernetes namespace
            dry_run: Simulate deployment without executing
            user_id: User identifier for tracking
            
        Returns:
            Deployment information dictionary
        """
        deployment_id = str(uuid.uuid4())
        now_iso = datetime.utcnow().isoformat()
        
        deployment = {
            "id": deployment_id,
            "model_name": model_name,
            "cluster_name": cluster_name,
            "region": region,
            "engine": engine,
            "use_fsx": use_fsx,
            "namespace": namespace,
            "status": "queued",
            "created_at": now_iso,
            "updated_at": now_iso,
            "user_id": user_id,
            "dry_run": dry_run,
            "endpoint": None,
            "error": None,
        }
        
        with self._deployments_lock:
            self._deployments[deployment_id] = deployment
        
        # Start deployment in background thread
        thread = threading.Thread(
            target=self._execute_deployment,
            args=(deployment_id, role_arn),
            daemon=True
        )
        thread.start()
        
        logger.info(
            "HyperPod model deployment queued",
            extra={
                "deployment_id": deployment_id,
                "model": model_name,
                "engine": engine,
                "dry_run": dry_run
            }
        )
        
        return self._public_snapshot(deployment)

    def _execute_deployment(self, deployment_id: str, role_arn: Optional[str]) -> None:
        """Execute model deployment in background."""
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return
        
        self._update_deployment(deployment_id, status="deploying", started_at=datetime.utcnow().isoformat())
        
        try:
            # Build command
            cmd = [
                str(self._scripts_dir / "deploy_hyperpod_model.sh"),
                "--cluster-name", deployment["cluster_name"],
                "--region", deployment["region"],
                "--model", deployment["model_name"],
                "--engine", deployment["engine"],
                "--namespace", deployment["namespace"],
            ]
            
            if role_arn:
                cmd.extend(["--role-arn", role_arn])
            
            if deployment["use_fsx"]:
                cmd.append("--use-fsx")
            
            if deployment["dry_run"]:
                cmd.append("--dry-run")
            
            # Execute deployment script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,  # 15 minutes
            )
            
            if result.returncode == 0:
                # Extract endpoint from output
                endpoint = self._extract_endpoint(result.stdout)
                
                self._update_deployment(
                    deployment_id,
                    status="deployed",
                    endpoint=endpoint,
                    finished_at=datetime.utcnow().isoformat(),
                )
                
                logger.info(
                    "HyperPod model deployment completed",
                    extra={"deployment_id": deployment_id, "endpoint": endpoint}
                )
            else:
                error_msg = f"Deployment failed: {result.stderr}"
                self._update_deployment(
                    deployment_id,
                    status="failed",
                    error=error_msg,
                    finished_at=datetime.utcnow().isoformat(),
                )
                
                logger.error(
                    "HyperPod model deployment failed",
                    extra={"deployment_id": deployment_id, "error": error_msg}
                )
        
        except subprocess.TimeoutExpired:
            error_msg = "Deployment timed out after 15 minutes"
            self._update_deployment(
                deployment_id,
                status="failed",
                error=error_msg,
                finished_at=datetime.utcnow().isoformat(),
            )
            logger.error("HyperPod model deployment timed out", extra={"deployment_id": deployment_id})
        
        except Exception as exc:
            error_msg = f"Deployment error: {exc}"
            self._update_deployment(
                deployment_id,
                status="failed",
                error=error_msg,
                finished_at=datetime.utcnow().isoformat(),
            )
            logger.exception("HyperPod model deployment exception", extra={"deployment_id": deployment_id})

    def _extract_endpoint(self, output: str) -> Optional[str]:
        """Extract endpoint URL from deployment script output."""
        for line in output.split("\n"):
            if "Endpoint:" in line:
                parts = line.split("Endpoint:", 1)
                if len(parts) == 2:
                    endpoint = parts[1].strip()
                    if endpoint.startswith("http"):
                        return endpoint
        return None

    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Get deployment information."""
        with self._deployments_lock:
            deployment = self._deployments.get(deployment_id)
            if not deployment:
                return None
            return self._public_snapshot(deployment)

    def list_deployments(self) -> List[Dict[str, Any]]:
        """List all model deployments."""
        with self._deployments_lock:
            deployments = [self._public_snapshot(d) for d in self._deployments.values()]
        
        return sorted(deployments, key=lambda x: x["created_at"], reverse=True)

    def scale_deployment(
        self,
        deployment_id: str,
        replicas: int,
        *,
        role_arn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scale a model deployment.
        
        Args:
            deployment_id: Deployment identifier
            replicas: Number of replicas (0 to scale down)
            role_arn: IAM role ARN for cluster access
            
        Returns:
            Updated deployment information
        """
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")
        
        if deployment["status"] != "deployed":
            raise ValueError(f"Deployment is not in deployed state: {deployment['status']}")
        
        try:
            # Build kubectl command
            cmd = ["kubectl", "scale", "deployment"]
            
            # Construct deployment name
            model_name = deployment["model_name"]
            engine = deployment["engine"]
            deployment_name = f"{model_name}-{engine}"
            
            cmd.extend([
                deployment_name,
                f"--replicas={replicas}",
                f"--namespace={deployment['namespace']}",
            ])
            
            # Update kubeconfig first
            self._update_kubeconfig(
                deployment["cluster_name"],
                deployment["region"],
                role_arn
            )
            
            # Execute scale command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                status = "scaled_down" if replicas == 0 else "deployed"
                self._update_deployment(
                    deployment_id,
                    status=status,
                    replicas=replicas,
                )
                
                logger.info(
                    "HyperPod deployment scaled",
                    extra={"deployment_id": deployment_id, "replicas": replicas}
                )
            else:
                raise RuntimeError(f"Scale command failed: {result.stderr}")
        
        except Exception as exc:
            logger.error(
                "Failed to scale deployment",
                extra={"deployment_id": deployment_id, "error": str(exc)}
            )
            raise
        
        return self.get_deployment(deployment_id)

    def delete_deployment(
        self,
        deployment_id: str,
        *,
        role_arn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete a model deployment.
        
        Args:
            deployment_id: Deployment identifier
            role_arn: IAM role ARN for cluster access
            
        Returns:
            Deletion status
        """
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")
        
        try:
            # Update kubeconfig
            self._update_kubeconfig(
                deployment["cluster_name"],
                deployment["region"],
                role_arn
            )
            
            # Delete Kubernetes resources
            model_name = deployment["model_name"]
            namespace = deployment["namespace"]
            
            # Delete by label
            subprocess.run(
                ["kubectl", "delete", "all", "-l", f"model={model_name}", "-n", namespace],
                capture_output=True,
                timeout=60,
            )
            
            self._update_deployment(deployment_id, status="deleted")
            
            logger.info("HyperPod deployment deleted", extra={"deployment_id": deployment_id})
        
        except Exception as exc:
            logger.error(
                "Failed to delete deployment",
                extra={"deployment_id": deployment_id, "error": str(exc)}
            )
            raise
        
        return self.get_deployment(deployment_id)

    def _update_kubeconfig(
        self,
        cluster_name: str,
        region: str,
        role_arn: Optional[str],
    ) -> None:
        """Update kubectl configuration for cluster access."""
        cmd = [
            "aws", "eks", "update-kubeconfig",
            "--name", cluster_name,
            "--region", region,
        ]
        
        if role_arn:
            cmd.extend(["--role-arn", role_arn])
        
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)

    def _update_deployment(self, deployment_id: str, **fields: Any) -> None:
        """Update deployment fields."""
        with self._deployments_lock:
            deployment = self._deployments.get(deployment_id)
            if deployment:
                deployment.update(fields)
                deployment["updated_at"] = datetime.utcnow().isoformat()

    def _public_snapshot(self, deployment: Dict[str, Any]) -> Dict[str, Any]:
        """Create public snapshot of deployment."""
        return {
            "deployment_id": deployment["id"],
            "model_name": deployment["model_name"],
            "cluster_name": deployment["cluster_name"],
            "region": deployment["region"],
            "engine": deployment["engine"],
            "use_fsx": deployment["use_fsx"],
            "namespace": deployment["namespace"],
            "status": deployment["status"],
            "endpoint": deployment.get("endpoint"),
            "replicas": deployment.get("replicas"),
            "created_at": deployment["created_at"],
            "updated_at": deployment["updated_at"],
            "started_at": deployment.get("started_at"),
            "finished_at": deployment.get("finished_at"),
            "error": deployment.get("error"),
            "dry_run": deployment["dry_run"],
            "user_id": deployment.get("user_id"),
        }

