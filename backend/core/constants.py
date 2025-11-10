"""Constants and enums for the unified launch system."""

from enum import Enum


class LaunchMethod(Enum):
    """Supported launch methods."""
    SAGEMAKER_ENDPOINT = "SAGEMAKER_ENDPOINT"
    HYPERPOD = "HYPERPOD"
    EKS = "EKS"
    EC2 = "EC2"


class LaunchStatus(Enum):
    """Launch job status values."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InferenceEngine(Enum):
    """Supported inference engines."""
    VLLM = "vllm"
    SGLANG = "sglang"
    TGI = "tgi"
    TRANSFORMERS = "transformers"


# Launch method display names
LAUNCH_METHOD_NAMES = {
    LaunchMethod.SAGEMAKER_ENDPOINT.value: "SageMaker Endpoint (EMD)",
    LaunchMethod.HYPERPOD.value: "SageMaker HyperPod",
    LaunchMethod.EKS.value: "EKS Deployment",
    LaunchMethod.EC2.value: "EC2 Instance"
}

# Inference engine display names
INFERENCE_ENGINE_NAMES = {
    InferenceEngine.VLLM.value: "vLLM",
    InferenceEngine.SGLANG.value: "SGLang",
    InferenceEngine.TGI.value: "Text Generation Inference",
    InferenceEngine.TRANSFORMERS.value: "Transformers"
}

# Status display names and colors for UI
STATUS_DISPLAY = {
    LaunchStatus.QUEUED.value: {"name": "Queued", "color": "blue"},
    LaunchStatus.RUNNING.value: {"name": "Running", "color": "orange"},
    LaunchStatus.COMPLETED.value: {"name": "Completed", "color": "green"},
    LaunchStatus.FAILED.value: {"name": "Failed", "color": "red"},
    LaunchStatus.CANCELLED.value: {"name": "Cancelled", "color": "gray"}
}
