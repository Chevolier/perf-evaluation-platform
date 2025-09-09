import base64
import json
import logging
import re
import tempfile
import time
from dataclasses import dataclass

import boto3
from botocore.signers import RequestSigner
from eks_api_client import EksApiClient
from kubernetes import client
from kubernetes.client.exceptions import ApiException

log_format = '%(asctime)s [%(process)d] [%(threadName)s] %(levelname)s %(filename)s:%(funcName)s:%(lineno)d - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)


class EKSEnvironment:

    def __init__(self, eks_cluster_name: str,  region: str = "us-east-1"):
        self.eks_cluster_name = eks_cluster_name
        self.region = region

        self.k8s_api_client = EksApiClient(
            eks_cluster_name, region).eks_api_client()

    def create_node_class(self, eks_node_role_arn, eks_node_sg_id):
        node_role = eks_node_role_arn.split('/')[-1]
        custom_api = client.CustomObjectsApi(self.k8s_api_client)
        eks_resource = {
            "apiVersion": "eks.amazonaws.com/v1",
            "kind": "NodeClass",
            "metadata": {"name": "gpu-inference-node-class"},
            "spec": {
                    "role": node_role,
                    "subnetSelectorTerms": [{"tags": {"subnetType": "private"}}],
                    "securityGroupSelectorTerms": [{"id": eks_node_sg_id}],
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

    def create_node_pool(self, node_instance_type: str = "g6e.xlarge"):
        custom_api = client.CustomObjectsApi(self.k8s_api_client)
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
                                "values": [node_instance_type]
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

    def create_ingress_class_params(self):
        customer_api = client.CustomObjectsApi(self.k8s_api_client)
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
                logging.info(
                    f"ingress class params is exist, response: {e.body}")
            else:
                raise e

        return True

    def create_ingress_class(self):
        customer_api = client.CustomObjectsApi(self.k8s_api_client)
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
            logging.info("ingress class success: {}".format(
                json.dumps(response)))
        except ApiException as e:
            if e.status == 409:
                logging.info(f"ingress class is exist, response: {e.body}")
            else:
                raise e

        return True

    @staticmethod
    def prepare(eks_cluster_name: str, eks_node_role_arn: str, eks_node_sg_id: str, eks_node_instance_type: str = "g6e.xlarge", region: str = 'us-east-1'):

        eks_environment = EKSEnvironment(eks_cluster_name, region)
        eks_environment.create_node_class(eks_node_role_arn, eks_node_sg_id)
        eks_environment.create_node_pool(eks_node_instance_type)
        eks_environment.create_ingress_class_params()
        eks_environment.create_ingress_class()

        return True
