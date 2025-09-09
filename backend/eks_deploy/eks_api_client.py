import base64
import re
import tempfile

import boto3
from botocore.signers import RequestSigner
from kubernetes import client

STS_TOKEN_EXPIRES_IN = 60


class EksApiClient:

    def __init__(self, eks_cluster_name: str, region: str = "us-east-1"):
        self.eks_cluster_name = eks_cluster_name
        self.region = region

        self.session = boto3.session.Session()
        self.sts_client = self.session.client('sts', region_name=region)
        self.eks_client = self.session.client('eks', region_name=region)

    def eks_api_client(self) -> client.ApiClient:
        info = self.eks_client.describe_cluster(name=self.eks_cluster_name)
        certificate = info['cluster']['certificateAuthority']['data']
        endpoint = info['cluster']['endpoint']

        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(base64.b64decode(certificate))
        ca_file.close

        config = client.Configuration(host=endpoint)
        config.ssl_ca_cert = ca_file.name
        config.api_key_prefix['authorization'] = 'Bearer'
        config.api_key['authorization'] = self.get_k8s_bearer_token()
        client.Configuration.set_default(config)

        return client.ApiClient()

    def get_k8s_bearer_token(self):
        service_id = self.sts_client.meta.service_model.service_id
        signer = RequestSigner(service_id, self.region, 'sts',
                               'v4', self.session.get_credentials(), self.session.events)
        params = {
            'method': 'GET',
            'url': 'https://sts.{}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15'.format(self.region),
            'body': {},
            'headers': {'x-k8s-aws-id': self.eks_cluster_name},
            'context': {}
        }

        signed_url = signer.generate_presigned_url(
            params,
            region_name=self.region,
            expires_in=STS_TOKEN_EXPIRES_IN,
            operation_name=''
        )

        base64_url = base64.urlsafe_b64encode(
            signed_url.encode('utf-8')).decode('utf-8')

        # remove any base64 encoding padding:
        return 'k8s-aws-v1.' + re.sub(r'=*', '', base64_url)
