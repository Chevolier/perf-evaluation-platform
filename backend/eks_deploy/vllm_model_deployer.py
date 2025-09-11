
import logging
import time

from eks_api_client import EksApiClient
from kubernetes import client
from kubernetes.client.exceptions import ApiException


class VllmModelDeployer:

    def __init__(self, eks_cluster_name: str, region: str = 'us-east-1'):
        self.eks_cluster_name = eks_cluster_name
        self.region = region

        self.k8s_api_client = EksApiClient(
            eks_cluster_name, region).eks_api_client()

    def create_server_deployment(self, replicas: int = 1, vllm_model: str = "Qwen/Qwen3-8B", tp_size: int = 1, gpu_request: int = 1,
                                 gpu_memory_utilization: float = 0.9, max_model_len: int = 2048):

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "vllm-qwen3-8b-server",
                "labels": {
                    "app.kubernetes.io/name": "vllm-qwen3-8b-server"
                }
            },
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": "vllm-qwen3-8b-server"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": "vllm-qwen3-8b-server"
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "vllm-server",
                                "image": "vllm/vllm-openai:latest",
                                "args": [
                                    "--model",
                                    f"{vllm_model}",
                                    "--tensor-parallel-size",
                                    f"{tp_size}",
                                    "--gpu-memory-utilization",
                                    f"{gpu_memory_utilization}",
                                    "--max-model-len",
                                    f"{max_model_len}",
                                ],
                                "ports": [
                                    {
                                        "containerPort": 8000,
                                        "name": "http",
                                        "protocol": "TCP"
                                    }
                                ],
                                "resources": {
                                    "limits": {
                                        "nvidia.com/gpu": gpu_request
                                    },
                                    "requests": {
                                        "nvidia.com/gpu": gpu_request
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
                                        "path": "/ping",
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

        app_v1_api = client.AppsV1Api(self.k8s_api_client)
        try:
            resp = app_v1_api.create_namespaced_deployment(
                namespace="default", body=manifest
            )
            logging.info(f"deployment create success: {resp}")
        except ApiException as e:
            if e.status == 409:
                logging.info(f"deployment already exists, ignoring: {e.body}")
            else:
                raise e

        return True

    def create_model_service(self):
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "vllm-qwen3-8b-server-svc"
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
                    "app.kubernetes.io/name": "vllm-qwen3-8b-server"
                }
            }
        }

        app_v1_api = client.CoreV1Api(self.k8s_api_client)
        try:
            resp = app_v1_api.create_namespaced_service(
                namespace="default", body=manifest)
            logging.info(f"service create success: {resp}")
        except ApiException as e:
            if e.status == 409:
                logging.info(f"service already exists, ignoring: {e.body}")
            else:
                raise e

        return True

    def create_ingress(self, ingress_name: str = "vllm-model-ingress"):
        manifest = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": ingress_name,
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
                                            "name": "vllm-qwen3-8b-server-svc",
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

        networking_v1_api = client.NetworkingV1Api(self.k8s_api_client)
        try:
            resp = networking_v1_api.create_namespaced_ingress(
                namespace="default", body=manifest)
            logging.info(f"ingress create success: {resp}")
        except ApiException as e:
            if e.status == 409:
                logging.info(f"ingress already exists, ignoring: {e.body}")
            else:
                raise e

        return True

    def get_ingress_host(self, ingress_name: str, timeout=300):
        network_api = client.NetworkingV1Api(self.k8s_api_client)
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                ingress = network_api.read_namespaced_ingress(
                    name=ingress_name, namespace="default")
                ingress_status = ingress.status.load_balancer.ingress
                if ingress_status:
                    if hasattr(ingress_status[0], 'hostname') and ingress_status[0].hostname:
                        return ingress_status[0].hostname
                logging.info("Ingress is not ready, please wait...")
                time.sleep(5)
            except ApiException as e:
                if e.status == 404:
                    logging.info(f"ingress {ingress_name} not exist.")
                    break
                else:
                    raise e

        logging.info("get ingress host fail, pls check...")
        return False

    @staticmethod
    def deploy(eks_cluster_name, replicas, vllm_model, tp_size, gpu_request, region, ingress_name):
        model_deployer = VllmModelDeployer(eks_cluster_name, region)
        model_deployer.create_server_deployment(
            replicas, vllm_model, tp_size, gpu_request)
        model_deployer.create_model_service()
        model_deployer.create_ingress(ingress_name)

        return model_deployer.get_ingress_host(ingress_name)
