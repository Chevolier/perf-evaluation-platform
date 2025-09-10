import logging
import random
import string
import time
from dataclasses import dataclass

import boto3

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")


def random_string():
    return ''.join(random.sample(string.ascii_letters + string.digits, 5))


@dataclass
class InfrastructureOutput:

    cluster_arn: str

    eks_cluster_role: str

    application_security_group: str

    vpc_id: str

    cluster_name: str

    eks_cluster_node_role: str

    kubeconfig_command: str

    cluster_endpoint: str

    region: str


class Infrastructure:

    def __init__(self, cfn_tpl_file):
        self.cfn_tpl_file = cfn_tpl_file
        self.stack_name = "perf-infplat-" + random_string()
        self.cfn_client = boto3.client('cloudformation')

    def _create_stack(self):
        tpl_body = open(self.cfn_tpl_file).read()
        return self.cfn_client.create_stack(
            StackName=self.stack_name,
            TemplateBody=tpl_body,
            Parameters=[
                {'ParameterKey': 'ClusterName',
                    'ParameterValue': self.stack_name + '-eks'}
            ],
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
        )

    def _wait_for_complete(self):
        while (True):
            resp = self.cfn_client.describe_stacks(StackName=self.stack_name)
            status = resp['Stacks'][0]['StackStatus']
            if status == 'CREATE_COMPLETE':
                return True
            elif status == 'CREATE_IN_PROGRESS':
                logging.info(
                    f"waiting for cloudformation complete, stack name: {self.stack_name}...")
                time.sleep(30)
            else:
                raise ValueError(
                    "Stack {} in status {}".format(self.stack_name, status))

    def _get_stack_output(self):
        resp = self.cfn_client.describe_stacks(StackName=self.stack_name)
        outputs = resp['Stacks'][0]['Outputs']
        result = {}
        for item in outputs:
            result[item['OutputKey']] = item['OutputValue']

        output = InfrastructureOutput(
            cluster_arn=result['ClusterArn'],
            eks_cluster_role=result['EKSClusterRole'],
            application_security_group=result['ApplicationSecurityGroup'],
            vpc_id=result['VpcId'],
            cluster_name=result['ClusterName'],
            eks_cluster_node_role=result['EKSClusterNodeRole'],
            kubeconfig_command=result['KubeconfigCommand'],
            cluster_endpoint=result['ClusterEndpoint'],
            region=result['Region']
        )

        return output

    def create_stack_and_wait_for_complete(self):
        self._create_stack()
        self._wait_for_complete()
        return self._get_stack_output()
