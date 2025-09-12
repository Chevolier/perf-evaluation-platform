from eks_environment import EKSEnvironment
from infrastructure import Infrastructure, InfrastructureOutput
from vllm_model_deployer import VllmModelDeployer

stack = Infrastructure(cfn_tpl_file="./infrastructure.yaml")
output = stack.create_stack_and_wait_for_complete()
EKSEnvironment.prepare(
    eks_cluster_name=output.cluster_name,
    eks_node_role_arn=output.eks_cluster_node_role,
    eks_node_sg_id=output.application_security_group,
    eks_node_instance_type="g5.4xlarge",
    region=output.region
)

host = VllmModelDeployer.deploy(
    eks_cluster_name=output.cluster_name,
    replicas=1,
    region=output.region,
    vllm_model="Qwen/Qwen3-8B",
    tp_size=1,
    gpu_request=1,
    ingress_name="qwen3-8b"
)

print(host)
