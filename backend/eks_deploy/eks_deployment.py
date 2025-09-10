import base64
import json
import logging
import re
import tempfile
import time

import boto3
from botocore.signers import RequestSigner
from kubernetes import client
from kubernetes.client.exceptions import ApiException

log_format = '%(asctime)s [%(process)d] [%(threadName)s] %(levelname)s %(filename)s:%(funcName)s:%(lineno)d - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)


def get_eks_api_client(cluster_name, region):
    eks = boto3.client('eks')
    info = eks.describe_cluster(name=cluster_name)
    certificate = info['cluster']['certificateAuthority']['data']
    endpoint = info['cluster']['endpoint']

    ca_file = tempfile.NamedTemporaryFile(delete=False)
    ca_file.write(base64.b64decode(certificate))
    ca_file.close()

    config = client.Configuration(host=endpoint)
    config.ssl_ca_cert = ca_file.name
    config.api_key_prefix['authorization'] = 'Bearer'
    config.api_key['authorization'] = _get_bearer_token(cluster_name, region)

    client.Configuration.set_default(config)

    return client.ApiClient()


def create_node_class(api_client: client.ApiClient, node_security_group: str, node_role_arn: str):
    node_role = node_role_arn.split('/')[-1]
    custom_api = client.CustomObjectsApi(api_client)
    eks_resource = {
        "apiVersion": "eks.amazonaws.com/v1",
        "kind": "NodeClass",
        "metadata": {"name": "gpu-inference-node-class"},
        "spec": {
            "role": node_role,
            "subnetSelectorTerms": [{"tags": {"subnetType": "private"}}],
            "securityGroupSelectorTerms": [{"id": node_security_group}],
            "ephemeralStorage": {"size": "200Gi", "iops": 3000, "throughput": 125}
        }
    }

    try:
        response = custom_api.create_cluster_custom_object(
            group="eks.amazonaws.com",
            version="v1",
            plural="nodeclasses",
            body=eks_resource
        )

        logging.info("node class success: {}".format(json.dumps(response)))
    except ApiException as e:
        if e.status == 409:
            logging.info(f"node class is exist, response: {e.body}")
        else:
            raise e

    return True


def create_node_pool(api_client: client.ApiClient):
    custom_api = client.CustomObjectsApi(api_client)
    eks_resource = {
        "apiVersion": "karpenter.sh/v1",
        "kind": "NodePool",
        "metadata": {"name": "gpu-node-pool"},
        "spec": {
            "template": {
                "metadata": {"labels": {"poolName": "gpu-nodes"}},
                "spec": {
                    "nodeClassRef": {
                        "group": "eks.amazonaws.com",
                        "kind": "NodeClass",
                        "name": "gpu-inference-node-class"
                    },
                    "requirements": [
                        {
                            "key": "node.kubernetes.io/instance-type",
                            "operator": "In",
                            "values": ["g6e.xlarge"]
                        },
                        {
                            "key": "eks.amazonaws.com/instance-gpu-count",
                            "operator": "In",
                            "values": ["1"]
                        },
                        {
                            "key": "karpenter.sh/capacity-type",
                            "operator": "In",
                            "values": ["on-demand"]
                        }
                    ]
                }
            }
        }
    }

    try:
        response = custom_api.create_cluster_custom_object(
            group="karpenter.sh",
            version="v1",
            plural="nodepools",
            body=eks_resource
        )
        logging.info("node pool success: {}".format(json.dumps(response)))
    except ApiException as e:
        if e.status == 409:
            logging.info(f"node pool is exist, response: {e.body}")
        else:
            raise e

    return True


def create_ingress_class_params(c: client.ApiClient):
    customer_api = client.CustomObjectsApi(c)
    eks_resource = {
        "apiVersion": "eks.amazonaws.com/v1",
        "kind": "IngressClassParams",
        "metadata": {"name": "alb"},
        "spec": {
            "scheme": "internet-facing",
            "subnets": {"matchTags": [{"key": "subnetType", "values": ["public"]}]}
        }
    }

    try:
        response = customer_api.create_cluster_custom_object(
            group="eks.amazonaws.com",
            version="v1",
            plural="ingressclassparams",
            body=eks_resource
        )
        logging.info("ingress class params success: {}".format(
            json.dumps(response)))
    except ApiException as e:
        if e.status == 409:
            logging.info(f"ingress class params is exist, response: {e.body}")
        else:
            raise e

    return True


def create_ingress_class(c: client.ApiClient):
    customer_api = client.CustomObjectsApi(c)
    eks_resource = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "IngressClass",
        "metadata": {
            "name": "alb",
            "annotations": {"ingressclass.kubernetes.io/is-default-class": "true"}
        },
        "spec": {
            "controller": "eks.amazonaws.com/alb",
            "parameters": {
                "apiGroup": "eks.amazonaws.com",
                "kind": "IngressClassParams",
                "name": "alb"
            }
        }
    }

    try:
        response = customer_api.create_cluster_custom_object(
            group="networking.k8s.io",
            version="v1",
            plural="ingressclasses",
            body=eks_resource
        )
        logging.info("ingress class success: {}".format(json.dumps(response)))
    except ApiException as e:
        if e.status == 409:
            logging.info(f"ingress class is exist, response: {e.body}")
        else:
            raise e

    return True


def create_qwen3_model_deployment(c: client.ApiClient):
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
            "replicas": 1,
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
                                "Qwen/Qwen3-8B",
                                "--tensor-parallel-size",
                                "1"
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
                                    "nvidia.com/gpu": 1
                                },
                                "requests": {
                                    "nvidia.com/gpu": 1
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

    app_v1_api = client.AppsV1Api(c)
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


def create_qwen3_model_service(c: client.ApiClient):
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

    app_v1_api = client.CoreV1Api(c)
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


def create_qwen3_model_ingress(c: client.ApiClient, ingress_name):
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

    networking_v1_api = client.NetworkingV1Api(c)
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


def get_ingress_host(c: client.ApiClient, ingress_name: str, timeout=300):
    network_api = client.NetworkingV1Api(c)
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


def _get_bearer_token(cluster_name, region):
    STS_TOKEN_EXPIRES_IN = 60
    session = boto3.session.Session()

    client = session.client('sts', region_name=region)
    service_id = client.meta.service_model.service_id

    signer = RequestSigner(
        service_id,
        region,
        'sts',
        'v4',
        session.get_credentials(),
        session.events
    )

    params = {
        'method': 'GET',
        'url': 'https://sts.{}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15'.format(region),
        'body': {},
        'headers': {
            'x-k8s-aws-id': cluster_name
        },
        'context': {}
    }

    signed_url = signer.generate_presigned_url(
        params,
        region_name=region,
        expires_in=STS_TOKEN_EXPIRES_IN,
        operation_name=''
    )

    base64_url = base64.urlsafe_b64encode(
        signed_url.encode('utf-8')).decode('utf-8')

    # remove any base64 encoding padding:
    return 'k8s-aws-v1.' + re.sub(r'=*', '', base64_url)


if __name__ == '__main__':

    # # example output
    # cfn_output = {
    #     "ClusterArn": "arn:aws:eks:us-east-1:867533378352:cluster/infplat-eksNHwAP",
    #     "EKSClusterRole": "arn:aws:iam::867533378352:role/inference-platform-NHwAP-EKSClusterRole-9AS28ZKzVeOn",
    #     "ApplicationSecurityGroup": "sg-04ccbe56577b13b2e",
    #     "VpcId": "vpc-08aab5a0249482aed",
    #     "ClusterName": "infplat-eksNHwAP",
    #     "EKSClusterNodeRole": "arn:aws:iam::867533378352:role/inference-platform-NHwAP-EKSNodeRole-XJdRVRoHitRh",
    #     "KubeconfigCommand": "aws eks update-kubeconfig --region us-east-1 --name infplat-eksNHwAP",
    #     "ClusterEndpoint": "https://620FA7999A0DAC15B8BDDC8E259DF8D6.gr7.us-east-1.eks.amazonaws.com",
    #     "Region": "us-east-1"
    # }

    cfn_output = {
        'ClusterArn': 'arn:aws:eks:us-west-2:452145973879:cluster/infplat-eks2yjFk', 
        'EKSClusterRole': 'arn:aws:iam::452145973879:role/inference-platform-2yjFk-EKSClusterRole-k8UPB7CRv2F4', 
        'ApplicationSecurityGroup': 'sg-000c66aca1c27d3fd', 
        'VpcId': 'vpc-09bc06bc0f85b8f1c', 
        'ClusterName': 'infplat-eks2yjFk', 
        'EKSClusterNodeRole': 'arn:aws:iam::452145973879:role/inference-platform-2yjFk-EKSNodeRole-CXRwYEdNqDba', 
        'Region': 'us-west-2', 
        'KubeconfigCommand': 'aws eks update-kubeconfig --region us-west-2 --name infplat-eks2yjFk', 
        'ClusterEndpoint': 'https://40182EBBF41B37B20BD4FEE4A0F58FAB.gr7.us-west-2.eks.amazonaws.com'
    }

    api_client = get_eks_api_client(cluster_name=cfn_output['ClusterName'],
                                    region=cfn_output['Region'])
    create_node_class(
        api_client,
        cfn_output['ApplicationSecurityGroup'],
        cfn_output['EKSClusterNodeRole']
    )

    create_node_pool(api_client)
    create_ingress_class_params(api_client)
    create_ingress_class(api_client)
    create_qwen3_model_deployment(api_client)
    create_qwen3_model_service(api_client)
    create_qwen3_model_ingress(api_client, "ing-vllm")
    host = get_ingress_host(api_client, "ing-vllm")
    print(host)
