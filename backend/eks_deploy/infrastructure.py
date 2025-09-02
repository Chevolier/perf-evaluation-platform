import logging
import random
import string
import time

import boto3

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")


def random_string():
    return ''.join(random.sample(string.ascii_letters + string.digits, 5))


def create_infrastructure_stack():

    caller_identity = boto3.client('sts').get_caller_identity()
    template = open('./infrastructure.yaml', 'r').read().replace(
        '${{__CLIENT_CALLER_ARN__}}', caller_identity['Arn'])

    c = boto3.client('cloudformation')

    rs = random_string()
    stack_name = "inference-platform-" + rs
    stack = c.create_stack(
        StackName=stack_name, TemplateBody=template,
        Parameters=[
            {'ParameterKey': 'ClusterName', 'ParameterValue': 'infplat-eks' + rs}
        ],
        Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
    )

    while (True):
        resp = c.describe_stacks(StackName=stack_name)
        status = resp['Stacks'][0]['StackStatus']
        if status == 'CREATE_COMPLETE':
            result = {}
            outputs = resp['Stacks'][0]['Outputs']
            for item in outputs:
                result[item['OutputKey']] = item['OutputValue']
            return result
        elif status == 'CREATE_IN_PROGRESS':
            logging.info("waiting for cloudformation complete...")
            time.sleep(30)
        else:
            raise ValueError(
                "Stack {} in status {}".format(stack_name, status))


if __name__ == '__main__':
    outputs = create_infrastructure_stack()

    # example result:
    #
    # {'ClusterArn': 'arn:aws:eks:us-east-1:867533378352:cluster/infplat-eksNHwAP', 'EKSClusterRole': 'arn:aws:iam::867533378352:role/inference-platform-NHwAP-EKSClusterRole-9AS28ZKzVeOn', 'ApplicationSecurityGroup': 'sg-04ccbe56577b13b2e', 'VpcId': 'vpc-08aab5a0249482aed', 'ClusterName': 'infplat-eksNHwAP', 'EKSClusterNodeRole': 'arn:aws:iam::867533378352:role/inference-platform-NHwAP-EKSNodeRole-XJdRVRoHitRh', 'KubeconfigCommand': 'aws eks update-kubeconfig --region us-east-1 --name infplat-eksNHwAP', 'ClusterEndpoint': 'https://620FA7999A0DAC15B8BDDC8E259DF8D6.gr7.us-east-1.eks.amazonaws.com', 'Region': 'us-east-1'}
    print(outputs)
