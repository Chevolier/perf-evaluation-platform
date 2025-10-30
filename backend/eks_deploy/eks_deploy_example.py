from eks_environment import EKSEnvironment
from infrastructure import Infrastructure, InfrastructureOutput
from vllm_model_deployer import VllmModelDeployer

stack = Infrastructure(cfn_tpl_file="./infrastructure.yaml")
output = stack.create_stack_and_wait_for_complete()
EKSEnvironment.prepare(
    eks_cluster_name=output.cluster_name,
    eks_node_role_arn=output.eks_cluster_node_role,
    eks_node_sg_id=output.application_security_group,
    eks_node_instance_type="g5.12xlarge",
    region=output.region
)

host = VllmModelDeployer.deploy(
    eks_cluster_name=output.cluster_name,
    replicas=1,
    region=output.region,
    vllm_model="Qwen/Qwen3-Coder-30B-A3B-Instruct",
    tp_size=4,
    gpu_request=4,
    ingress_name="Qwen3-Coder-30B-A3B-Instruct"
)

print(host)
