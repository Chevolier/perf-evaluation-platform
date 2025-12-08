"""Launch adapters for different deployment methods."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from utils import get_logger

logger = get_logger(__name__)


class LaunchAdapter(ABC):
    """Base class for launch method adapters."""
    
    def __init__(self, launch_service):
        """Initialize adapter with reference to launch service.
        
        Args:
            launch_service: Reference to the LaunchService instance
        """
        self._launch_service = launch_service
        self._db = launch_service._db
    
    @abstractmethod
    def execute(self, job_id: str, model_key: str, engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the launch.
        
        Args:
            job_id: Unique job identifier
            model_key: Model to launch
            engine: Inference engine to use
            params: Method-specific parameters
            
        Returns:
            Dictionary with 'success', 'deployment_id', and optional 'error' keys
        """
        pass
    
    @abstractmethod
    def poll_status(self, job_id: str, deployment_id: str) -> Dict[str, Any]:
        """Poll external system for status.
        
        Args:
            job_id: Job identifier
            deployment_id: External deployment identifier
            
        Returns:
            Dictionary with 'status', 'endpoint', and optional 'error' keys
        """
        pass
    
    @abstractmethod
    def cleanup(self, job_id: str, deployment_id: str) -> bool:
        """Cleanup resources for this launch.
        
        Args:
            job_id: Job identifier
            deployment_id: External deployment identifier
            
        Returns:
            True if cleanup was successful
        """
        pass
    
    def _update_job_status(self, job_id: str, status: str, **kwargs) -> None:
        """Update job status in database.
        
        Args:
            job_id: Job identifier
            status: New status
            **kwargs: Additional fields to update
        """
        update_fields = {'status': status}
        update_fields.update(kwargs)
        
        if status == 'running' and 'started_at' not in update_fields:
            update_fields['started_at'] = datetime.now().isoformat()
        elif status in ['completed', 'failed', 'cancelled'] and 'completed_at' not in update_fields:
            update_fields['completed_at'] = datetime.now().isoformat()
        
        self._db.update_launch_job(job_id, **update_fields)
    
    def _register_endpoint(self, model_key: str, endpoint_url: str, deployment_id: str, 
                          method: str, metadata: Dict[str, Any] = None) -> None:
        """Register successful endpoint with model service.
        
        Args:
            model_key: Model identifier
            endpoint_url: Endpoint URL
            deployment_id: External deployment identifier
            method: Launch method used
            metadata: Additional metadata
        """
        try:
            from services.model_service import ModelService
            model_service = ModelService()
            
            model_service.register_external_endpoint(
                deployment_method=method,
                endpoint_url=endpoint_url,
                deployment_id=deployment_id,
                model_name=model_key,
                metadata=metadata or {}
            )
            
            logger.info(f"Registered endpoint {endpoint_url} for model {model_key}")
        except Exception as e:
            logger.error(f"Failed to register endpoint for {model_key}: {e}")


class EMDLaunchAdapter(LaunchAdapter):
    """Adapter for SageMaker Endpoint (EMD) launches."""
    
    def execute(self, job_id: str, model_key: str, engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute EMD launch."""
        try:
            from services.model_service import ModelService
            model_service = ModelService()
            
            instance_type = params.get('instance_type', 'ml.g5.2xlarge')
            service_type = params.get('service_type', 'sagemaker_realtime')
            
            # Update job status to running
            self._update_job_status(job_id, 'running')
            
            # Call existing EMD deployment
            result = model_service.deploy_emd_model(
                model_key=model_key,
                instance_type=instance_type,
                engine_type=engine,
                service_type=service_type
            )
            
            if result.get('success'):
                deployment_tag = result.get('tag')
                self._db.update_launch_job(job_id, deployment_id=deployment_tag)
                return {
                    'success': True,
                    'deployment_id': deployment_tag
                }
            else:
                error_msg = result.get('error', 'EMD deployment failed')
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"EMD launch failed: {str(e)}"
            logger.error(error_msg)
            self._update_job_status(job_id, 'failed', error_message=error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def poll_status(self, job_id: str, deployment_id: str) -> Dict[str, Any]:
        """Poll EMD status."""
        try:
            from services.model_service import ModelService
            model_service = ModelService()
            
            # Get model key from job
            job = self._db.get_launch_job(job_id)
            if not job:
                return {'status': 'failed', 'error': 'Job not found'}
            
            model_key = job['model_key']
            
            # Get EMD deployment status
            status_info = model_service.get_emd_deployment_status(model_key)
            status = status_info.get('status', 'unknown')
            endpoint = status_info.get('endpoint')
            
            # Map EMD status to launch status
            if status == 'deployed':
                if endpoint:
                    # Register endpoint and mark as completed
                    self._register_endpoint(
                        model_key=model_key,
                        endpoint_url=endpoint,
                        deployment_id=deployment_id,
                        method='SageMaker Endpoint (EMD)',
                        metadata={'deployment_tag': deployment_id}
                    )
                    self._update_job_status(job_id, 'completed', endpoint_url=endpoint)
                    return {'status': 'completed', 'endpoint': endpoint}
                else:
                    return {'status': 'running'}
            elif status == 'failed':
                self._update_job_status(job_id, 'failed', error_message='EMD deployment failed')
                return {'status': 'failed', 'error': 'EMD deployment failed'}
            elif status == 'inprogress':
                return {'status': 'running'}
            else:
                return {'status': 'running'}
                
        except Exception as e:
            error_msg = f"EMD status polling failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'failed', 'error': error_msg}
    
    def cleanup(self, job_id: str, deployment_id: str) -> bool:
        """Cleanup EMD deployment."""
        try:
            from services.model_service import ModelService
            model_service = ModelService()
            
            # Get model key from job
            job = self._db.get_launch_job(job_id)
            if not job:
                return False
            
            model_key = job['model_key']
            
            # Call existing EMD deletion
            result = model_service.delete_emd_model(model_key)
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"EMD cleanup failed: {e}")
            return False


class HyperPodLaunchAdapter(LaunchAdapter):
    """Adapter for SageMaker HyperPod launches."""
    
    def execute(self, job_id: str, model_key: str, engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HyperPod launch."""
        try:
            from .hyperpod_service import HyperPodService
            hyperpod_service = HyperPodService()
            
            # Transform launch params to HyperPod request format
            request = {
                'preset': params.get('preset', 'small'),
                'region': params.get('region', 'us-east-1'),
                'config': {
                    'instance_type': params.get('instance_type', 'ml.p4d.24xlarge'),
                    'instance_count': params.get('instance_count', 2),
                    'gpus_per_pod': params.get('gpus_per_pod', 8),
                    'replicas': params.get('replicas', 1)
                }
            }
            
            # Update job status to running
            self._update_job_status(job_id, 'running')
            
            # Start HyperPod deployment
            result = hyperpod_service.start_deployment(request, user_id=job_id)
            
            if result and 'job_id' in result:
                hyperpod_job_id = result['job_id']
                self._db.update_launch_job(job_id, deployment_id=hyperpod_job_id)
                return {
                    'success': True,
                    'deployment_id': hyperpod_job_id
                }
            else:
                error_msg = 'HyperPod deployment failed to start'
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"HyperPod launch failed: {str(e)}"
            logger.error(error_msg)
            self._update_job_status(job_id, 'failed', error_message=error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def poll_status(self, job_id: str, deployment_id: str) -> Dict[str, Any]:
        """Poll HyperPod status."""
        try:
            from .hyperpod_service import HyperPodService
            hyperpod_service = HyperPodService()
            
            # Get HyperPod job status
            status_info = hyperpod_service.get_job_status(deployment_id)
            if not status_info:
                return {'status': 'failed', 'error': 'HyperPod job not found'}
            
            status = status_info.get('status', 'unknown')
            
            # Map HyperPod status to launch status
            if status == 'succeeded':
                # HyperPod completed successfully, endpoint should be registered by _ingest_job_outputs
                # Check if we have an endpoint URL
                job = self._db.get_launch_job(job_id)
                if job and job.get('endpoint_url'):
                    self._update_job_status(job_id, 'completed')
                    return {'status': 'completed', 'endpoint': job['endpoint_url']}
                else:
                    # Still waiting for endpoint registration
                    return {'status': 'running'}
            elif status in ['failed', 'destroy_failed']:
                error_msg = status_info.get('error', 'HyperPod deployment failed')
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {'status': 'failed', 'error': error_msg}
            else:
                return {'status': 'running'}
                
        except Exception as e:
            error_msg = f"HyperPod status polling failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'failed', 'error': error_msg}
    
    def cleanup(self, job_id: str, deployment_id: str) -> bool:
        """Cleanup HyperPod deployment."""
        try:
            from .hyperpod_service import HyperPodService
            hyperpod_service = HyperPodService()
            
            # Start HyperPod destroy
            request = {'job_id': deployment_id}
            result = hyperpod_service.start_destroy(request, user_id=job_id)
            return result is not None
            
        except Exception as e:
            logger.error(f"HyperPod cleanup failed: {e}")
            return False


class EKSLaunchAdapter(LaunchAdapter):
    """Adapter for EKS deployments."""
    
    def execute(self, job_id: str, model_key: str, engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute EKS launch."""
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'eks_deploy'))
            from eks_deployment import get_eks_api_client, create_qwen3_model_deployment, create_qwen3_model_service, create_qwen3_model_ingress
            
            cluster_name = params.get('cluster_name')
            namespace = params.get('namespace', 'default')
            replicas = params.get('replicas', 1)
            gpus_per_pod = params.get('gpus_per_pod', 1)
            region = params.get('region', 'us-east-1')
            container_image = params.get('container_image')
            
            if not cluster_name:
                error_msg = 'cluster_name is required for EKS deployment'
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Update job status to running
            self._update_job_status(job_id, 'running')
            
            # Get EKS API client
            api_client = get_eks_api_client(cluster_name, region)
            
            # Generate deployment name based on model and job
            deployment_name = f"{engine}-{model_key.replace('.', '-')}-{job_id[:8]}"
            service_name = f"{deployment_name}-svc"
            ingress_name = f"{deployment_name}-ingress"
            
            # Create deployment manifest
            deployment_manifest = self._create_deployment_manifest(
                deployment_name, model_key, engine, replicas, gpus_per_pod, 
                container_image, namespace
            )
            
            # Create service manifest
            service_manifest = self._create_service_manifest(
                service_name, deployment_name, namespace
            )
            
            # Create ingress manifest
            ingress_manifest = self._create_ingress_manifest(
                ingress_name, service_name, namespace
            )
            
            # Apply manifests
            from kubernetes import client
            from kubernetes.client.exceptions import ApiException
            
            apps_v1_api = client.AppsV1Api(api_client)
            core_v1_api = client.CoreV1Api(api_client)
            networking_v1_api = client.NetworkingV1Api(api_client)
            
            # Create deployment
            try:
                apps_v1_api.create_namespaced_deployment(
                    namespace=namespace, body=deployment_manifest
                )
                logger.info(f"Created deployment {deployment_name}")
            except ApiException as e:
                if e.status == 409:
                    logger.info(f"Deployment {deployment_name} already exists")
                else:
                    raise e
            
            # Create service
            try:
                core_v1_api.create_namespaced_service(
                    namespace=namespace, body=service_manifest
                )
                logger.info(f"Created service {service_name}")
            except ApiException as e:
                if e.status == 409:
                    logger.info(f"Service {service_name} already exists")
                else:
                    raise e
            
            # Create ingress
            try:
                networking_v1_api.create_namespaced_ingress(
                    namespace=namespace, body=ingress_manifest
                )
                logger.info(f"Created ingress {ingress_name}")
            except ApiException as e:
                if e.status == 409:
                    logger.info(f"Ingress {ingress_name} already exists")
                else:
                    raise e
            
            # Store deployment info
            deployment_id = f"{cluster_name}:{namespace}:{deployment_name}"
            self._db.update_launch_job(job_id, deployment_id=deployment_id)
            
            return {
                'success': True,
                'deployment_id': deployment_id
            }
            
        except Exception as e:
            error_msg = f"EKS launch failed: {str(e)}"
            logger.error(error_msg)
            self._update_job_status(job_id, 'failed', error_message=error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _create_deployment_manifest(self, name: str, model_key: str, engine: str, 
                                  replicas: int, gpus_per_pod: int, container_image: str, 
                                  namespace: str) -> Dict[str, Any]:
        """Create Kubernetes deployment manifest."""
        # Map model key to actual model path
        model_path_map = {
            'qwen3-8b': 'Qwen/Qwen3-8B',
            'qwen3-0.6b': 'Qwen/Qwen3-0.6B',
            'qwen2.5-7b-instruct': 'Qwen/Qwen2.5-7B-Instruct',
            'qwen2-vl-7b': 'Qwen/Qwen2-VL-7B-Instruct',
            'qwen2.5-vl-32b': 'Qwen/Qwen2.5-VL-32B-Instruct'
        }
        model_path = model_path_map.get(model_key, model_key)
        
        # Default container images
        default_images = {
            'vllm': 'vllm/vllm-openai:latest',
            'sglang': 'lmsysorg/sglang:latest'
        }
        image = container_image or default_images.get(engine, f'{engine}/{engine}:latest')
        
        # Build args based on engine
        if engine == 'vllm':
            args = [
                '--model', model_path,
                '--tensor-parallel-size', str(gpus_per_pod),
                '--port', '8000',
                '--host', '0.0.0.0'
            ]
        elif engine == 'sglang':
            args = [
                'python', '-m', 'sglang.launch_server',
                '--model-path', model_path,
                '--tensor-parallel-size', str(gpus_per_pod),
                '--port', '8000',
                '--host', '0.0.0.0'
            ]
        else:
            args = ['--model', model_path, '--port', '8000']
        
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": name
                }
            },
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": name
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": f"{engine}-server",
                                "image": image,
                                "args": args,
                                "ports": [
                                    {
                                        "containerPort": 8000,
                                        "name": "http",
                                        "protocol": "TCP"
                                    }
                                ],
                                "resources": {
                                    "limits": {
                                        "nvidia.com/gpu": gpus_per_pod
                                    },
                                    "requests": {
                                        "nvidia.com/gpu": gpus_per_pod
                                    }
                                },
                                "env": [
                                    {
                                        "name": "NVIDIA_VISIBLE_DEVICES",
                                        "value": "all"
                                    }
                                ],
                                "startupProbe": {
                                    "httpGet": {
                                        "path": "/health",
                                        "port": 8000
                                    },
                                    "periodSeconds": 10,
                                    "failureThreshold": 60
                                },
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": "/health",
                                        "port": 8000
                                    },
                                    "periodSeconds": 30,
                                    "timeoutSeconds": 10,
                                    "successThreshold": 1,
                                    "failureThreshold": 5
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": "/health",
                                        "port": 8000
                                    },
                                    "periodSeconds": 10,
                                    "timeoutSeconds": 5,
                                    "successThreshold": 1,
                                    "failureThreshold": 3
                                }
                            }
                        ]
                    }
                }
            }
        }
    
    def _create_service_manifest(self, name: str, deployment_name: str, namespace: str) -> Dict[str, Any]:
        """Create Kubernetes service manifest."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "ports": [
                    {
                        "port": 8000,
                        "targetPort": 8000,
                        "protocol": "TCP"
                    }
                ],
                "selector": {
                    "app.kubernetes.io/name": deployment_name
                }
            }
        }
    
    def _create_ingress_manifest(self, name: str, service_name: str, namespace: str) -> Dict[str, Any]:
        """Create Kubernetes ingress manifest."""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "annotations": {
                    "alb.ingress.kubernetes.io/scheme": "internet-facing",
                    "alb.ingress.kubernetes.io/target-type": "ip",
                    "alb.ingress.kubernetes.io/healthcheck-path": "/health",
                    "alb.ingress.kubernetes.io/healthcheck-port": "8000",
                    "alb.ingress.kubernetes.io/healthcheck-protocol": "HTTP",
                    "alb.ingress.kubernetes.io/healthcheck-interval-seconds": "30",
                    "alb.ingress.kubernetes.io/healthy-threshold-count": "2"
                }
            },
            "spec": {
                "ingressClassName": "alb",
                "rules": [
                    {
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": service_name,
                                            "port": {
                                                "number": 8000
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    
    def poll_status(self, job_id: str, deployment_id: str) -> Dict[str, Any]:
        """Poll EKS deployment status."""
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'eks_deploy'))
            from eks_deployment import get_eks_api_client
            from kubernetes import client
            from kubernetes.client.exceptions import ApiException
            
            # Parse deployment_id: cluster:namespace:deployment_name
            parts = deployment_id.split(':')
            if len(parts) != 3:
                return {'status': 'failed', 'error': 'Invalid deployment_id format'}
            
            cluster_name, namespace, deployment_name = parts
            
            # Get EKS API client
            api_client = get_eks_api_client(cluster_name, 'us-east-1')  # Default region
            
            # Check deployment status
            apps_v1_api = client.AppsV1Api(api_client)
            deployment = apps_v1_api.read_namespaced_deployment(
                name=deployment_name, namespace=namespace
            )
            
            # Check if deployment is ready
            if deployment.status.ready_replicas == deployment.spec.replicas:
                # Get ingress to find endpoint
                networking_v1_api = client.NetworkingV1Api(api_client)
                ingress_name = f"{deployment_name}-ingress"
                
                try:
                    ingress = networking_v1_api.read_namespaced_ingress(
                        name=ingress_name, namespace=namespace
                    )
                    
                    # Extract endpoint from ingress
                    if ingress.status.load_balancer.ingress:
                        lb_ingress = ingress.status.load_balancer.ingress[0]
                        if lb_ingress.hostname:
                            endpoint = f"https://{lb_ingress.hostname}"
                        elif lb_ingress.ip:
                            endpoint = f"http://{lb_ingress.ip}"
                        else:
                            endpoint = None
                        
                        if endpoint:
                            # Register endpoint and mark as completed
                            job = self._db.get_launch_job(job_id)
                            if job:
                                model_key = job['model_key']
                                self._register_endpoint(
                                    model_key=model_key,
                                    endpoint_url=endpoint,
                                    deployment_id=deployment_id,
                                    method='EKS Deployment',
                                    metadata={
                                        'cluster_name': cluster_name,
                                        'namespace': namespace,
                                        'deployment_name': deployment_name
                                    }
                                )
                                self._update_job_status(job_id, 'completed', endpoint_url=endpoint)
                                return {'status': 'completed', 'endpoint': endpoint}
                    
                    return {'status': 'running'}  # Deployment ready but no endpoint yet
                    
                except ApiException as e:
                    if e.status == 404:
                        return {'status': 'running'}  # Ingress not ready yet
                    else:
                        raise e
            
            return {'status': 'running'}
            
        except ApiException as e:
            if e.status == 404:
                return {'status': 'failed', 'error': 'Deployment not found'}
            else:
                error_msg = f"EKS status polling failed: {str(e)}"
                logger.error(error_msg)
                return {'status': 'failed', 'error': error_msg}
        except Exception as e:
            error_msg = f"EKS status polling failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'failed', 'error': error_msg}
    
    def cleanup(self, job_id: str, deployment_id: str) -> bool:
        """Cleanup EKS deployment."""
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'eks_deploy'))
            from eks_deployment import get_eks_api_client
            from kubernetes import client
            from kubernetes.client.exceptions import ApiException
            
            # Parse deployment_id: cluster:namespace:deployment_name
            parts = deployment_id.split(':')
            if len(parts) != 3:
                return False
            
            cluster_name, namespace, deployment_name = parts
            
            # Get EKS API client
            api_client = get_eks_api_client(cluster_name, 'us-east-1')  # Default region
            
            # Delete resources
            apps_v1_api = client.AppsV1Api(api_client)
            core_v1_api = client.CoreV1Api(api_client)
            networking_v1_api = client.NetworkingV1Api(api_client)
            
            service_name = f"{deployment_name}-svc"
            ingress_name = f"{deployment_name}-ingress"
            
            # Delete deployment
            try:
                apps_v1_api.delete_namespaced_deployment(
                    name=deployment_name, namespace=namespace
                )
                logger.info(f"Deleted deployment {deployment_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete deployment {deployment_name}: {e}")
            
            # Delete service
            try:
                core_v1_api.delete_namespaced_service(
                    name=service_name, namespace=namespace
                )
                logger.info(f"Deleted service {service_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete service {service_name}: {e}")
            
            # Delete ingress
            try:
                networking_v1_api.delete_namespaced_ingress(
                    name=ingress_name, namespace=namespace
                )
                logger.info(f"Deleted ingress {ingress_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete ingress {ingress_name}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"EKS cleanup failed: {e}")
            return False


class EC2LaunchAdapter(LaunchAdapter):
    """Adapter for EC2 instance launches."""
    
    def execute(self, job_id: str, model_key: str, engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute EC2 launch."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            instance_type = params.get('instance_type')
            ami_id = params.get('ami_id')
            iam_instance_profile = params.get('iam_instance_profile')
            security_group_ids = params.get('security_group_ids', '').split(',')
            subnet_id = params.get('subnet_id')
            region = params.get('region', 'us-east-1')
            
            # Validate required parameters
            if not instance_type:
                error_msg = 'instance_type is required for EC2 deployment'
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {'success': False, 'error': error_msg}
            
            if not iam_instance_profile:
                error_msg = 'iam_instance_profile is required for EC2 deployment'
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {'success': False, 'error': error_msg}
            
            if not security_group_ids or not security_group_ids[0]:
                error_msg = 'security_group_ids is required for EC2 deployment'
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {'success': False, 'error': error_msg}
            
            if not subnet_id:
                error_msg = 'subnet_id is required for EC2 deployment'
                self._update_job_status(job_id, 'failed', error_message=error_msg)
                return {'success': False, 'error': error_msg}
            
            # Update job status to running
            self._update_job_status(job_id, 'running')
            
            # Get default AMI if not provided
            if not ami_id:
                ami_id = self._get_default_ami(region)
            
            # Create EC2 client
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Generate user data script
            user_data = self._generate_user_data_script(model_key, engine)
            
            # Launch instance
            response = ec2_client.run_instances(
                ImageId=ami_id,
                MinCount=1,
                MaxCount=1,
                InstanceType=instance_type,
                SecurityGroupIds=security_group_ids,
                SubnetId=subnet_id,
                IamInstanceProfile={'Arn': iam_instance_profile},
                UserData=user_data,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'{engine}-{model_key}-{job_id[:8]}'},
                            {'Key': 'LaunchJobId', 'Value': job_id},
                            {'Key': 'ModelKey', 'Value': model_key},
                            {'Key': 'Engine', 'Value': engine}
                        ]
                    }
                ]
            )
            
            instance_id = response['Instances'][0]['InstanceId']
            logger.info(f"Launched EC2 instance {instance_id} for job {job_id}")
            
            # Store deployment info
            deployment_id = f"ec2:{region}:{instance_id}"
            self._db.update_launch_job(job_id, deployment_id=deployment_id)
            
            return {
                'success': True,
                'deployment_id': deployment_id
            }
            
        except ClientError as e:
            error_msg = f"EC2 launch failed: {e.response['Error']['Message']}"
            logger.error(error_msg)
            self._update_job_status(job_id, 'failed', error_message=error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"EC2 launch failed: {str(e)}"
            logger.error(error_msg)
            self._update_job_status(job_id, 'failed', error_message=error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _get_default_ami(self, region: str) -> str:
        """Get default Deep Learning AMI for the region."""
        try:
            import boto3
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Get the latest Deep Learning AMI
            response = ec2_client.describe_images(
                Owners=['amazon'],
                Filters=[
                    {'Name': 'name', 'Values': ['Deep Learning AMI GPU PyTorch*']},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )
            
            if response['Images']:
                # Sort by creation date and get the latest
                latest_ami = max(response['Images'], key=lambda x: x['CreationDate'])
                return latest_ami['ImageId']
            else:
                # Fallback to a known AMI
                return 'ami-003b184e823d3e894'  # Deep Learning AMI in us-east-1
                
        except Exception as e:
            logger.warning(f"Failed to get default AMI: {e}")
            return 'ami-003b184e823d3e894'  # Fallback
    
    def _generate_user_data_script(self, model_key: str, engine: str) -> str:
        """Generate user data script to install and run the model."""
        # Map model key to actual model path
        model_path_map = {
            'qwen3-8b': 'Qwen/Qwen3-8B',
            'qwen3-0.6b': 'Qwen/Qwen3-0.6B',
            'qwen2.5-7b-instruct': 'Qwen/Qwen2.5-7B-Instruct',
            'qwen2-vl-7b': 'Qwen/Qwen2-VL-7B-Instruct',
            'qwen2.5-vl-32b': 'Qwen/Qwen2.5-VL-32B-Instruct'
        }
        model_path = model_path_map.get(model_key, model_key)
        
        if engine == 'vllm':
            script = f"""#!/bin/bash
# Install vLLM
pip install vllm

# Start vLLM server
vllm serve {model_path} --port 8000 --host 0.0.0.0 --tensor-parallel-size 1
"""
        elif engine == 'sglang':
            script = f"""#!/bin/bash
# Install SGLang
pip install "sglang[all]"

# Start SGLang server
python -m sglang.launch_server --model-path {model_path} --port 8000 --host 0.0.0.0 --tensor-parallel-size 1
"""
        else:
            script = f"""#!/bin/bash
# Generic model server setup
echo "Starting {engine} server for {model_path}"
# Add custom setup logic here
"""
        
        # Encode as base64
        import base64
        return base64.b64encode(script.encode()).decode()
    
    def poll_status(self, job_id: str, deployment_id: str) -> Dict[str, Any]:
        """Poll EC2 instance status."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Parse deployment_id: ec2:region:instance_id
            parts = deployment_id.split(':')
            if len(parts) != 3 or parts[0] != 'ec2':
                return {'status': 'failed', 'error': 'Invalid deployment_id format'}
            
            region, instance_id = parts[1], parts[2]
            
            # Create EC2 client
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Describe instance
            response = ec2_client.describe_instances(InstanceIds=[instance_id])
            
            if not response['Reservations']:
                return {'status': 'failed', 'error': 'Instance not found'}
            
            instance = response['Reservations'][0]['Instances'][0]
            state = instance['State']['Name']
            
            if state == 'running':
                # Check if instance is ready by trying to connect to health endpoint
                public_ip = instance.get('PublicIpAddress')
                private_ip = instance.get('PrivateIpAddress')
                
                if public_ip or private_ip:
                    # Try to connect to health endpoint
                    import requests
                    import time
                    
                    endpoint_ip = public_ip or private_ip
                    health_url = f"http://{endpoint_ip}:8000/health"
                    
                    try:
                        response = requests.get(health_url, timeout=5)
                        if response.status_code == 200:
                            # Instance is healthy, register endpoint
                            endpoint_url = f"http://{endpoint_ip}:8000/v1"
                            
                            job = self._db.get_launch_job(job_id)
                            if job:
                                model_key = job['model_key']
                                self._register_endpoint(
                                    model_key=model_key,
                                    endpoint_url=endpoint_url,
                                    deployment_id=deployment_id,
                                    method='EC2 Instance',
                                    metadata={
                                        'instance_id': instance_id,
                                        'region': region,
                                        'public_ip': public_ip,
                                        'private_ip': private_ip
                                    }
                                )
                                self._update_job_status(job_id, 'completed', endpoint_url=endpoint_url)
                                return {'status': 'completed', 'endpoint': endpoint_url}
                    except requests.exceptions.RequestException:
                        # Instance is running but not ready yet
                        pass
                
                return {'status': 'running'}
            elif state in ['pending', 'shutting-down', 'stopping', 'stopped']:
                return {'status': 'running'}
            elif state == 'terminated':
                return {'status': 'failed', 'error': 'Instance was terminated'}
            else:
                return {'status': 'failed', 'error': f'Instance in unknown state: {state}'}
            
        except ClientError as e:
            error_msg = f"EC2 status polling failed: {e.response['Error']['Message']}"
            logger.error(error_msg)
            return {'status': 'failed', 'error': error_msg}
        except Exception as e:
            error_msg = f"EC2 status polling failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'failed', 'error': error_msg}
    
    def cleanup(self, job_id: str, deployment_id: str) -> bool:
        """Cleanup EC2 deployment."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Parse deployment_id: ec2:region:instance_id
            parts = deployment_id.split(':')
            if len(parts) != 3 or parts[0] != 'ec2':
                return False
            
            region, instance_id = parts[1], parts[2]
            
            # Create EC2 client
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Terminate instance
            ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated EC2 instance {instance_id}")
            
            return True
            
        except ClientError as e:
            logger.error(f"EC2 cleanup failed: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"EC2 cleanup failed: {e}")
            return False
