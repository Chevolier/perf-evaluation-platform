"""Model registry containing all supported model definitions."""

from typing import Dict, Any, List


# EMD (Elastic Model Deployment) Models Configuration
# Used for SageMaker/HyperPod managed deployments
EMD_MODELS = {
    "qwen2.5-7b-instruct": {
        "name": "Qwen2.5-7B-Instruct",
        "description": "Qwen2.5模型",
        "model_path": "Qwen2.5-7B-Instruct",
        "supports_multimodal": False,
        "supports_streaming": True,
        "supported_methods": ["SAGEMAKER_ENDPOINT", "HYPERPOD", "EKS", "EC2"],
        "supported_engines": ["vllm", "sglang"],
        "constraints": {
            "min_gpus": 1,
            "recommended_instance_types": ["ml.g5.2xlarge", "ml.g5.4xlarge"]
        }
    },
    "qwen3-0.6b": {
        "name": "Qwen3-0.6B",
        "description": "最新Qwen3模型，0.6B参数，高效轻量",
        "model_path": "Qwen3-0.6B",
        "supports_multimodal": False,
        "supports_streaming": True,
        "supported_methods": ["SAGEMAKER_ENDPOINT", "HYPERPOD", "EKS", "EC2"],
        "supported_engines": ["vllm", "sglang"],
        "constraints": {
            "min_gpus": 1,
            "recommended_instance_types": ["ml.g5.xlarge", "ml.g5.2xlarge"]
        }
    },
    "qwen3-8b": {
        "name": "Qwen3-8B",
        "description": "最新Qwen3模型，8B参数，强大性能",
        "model_path": "Qwen3-8B",
        "supports_multimodal": False,
        "supports_streaming": True,
        "supported_methods": ["SAGEMAKER_ENDPOINT", "HYPERPOD", "EKS", "EC2"],
        "supported_engines": ["vllm", "sglang"],
        "constraints": {
            "min_gpus": 1,
            "recommended_instance_types": ["ml.g5.2xlarge", "ml.g5.4xlarge"]
        }
    },
    "qwen2-vl-7b": {
        "name": "Qwen2-VL-7B-Instruct",
        "description": "通义千问视觉语言模型，7B参数",
        "model_path": "Qwen2-VL-7B-Instruct",
        "supports_multimodal": True,
        "supports_streaming": True,
        "supported_methods": ["SAGEMAKER_ENDPOINT", "HYPERPOD", "EKS", "EC2"],
        "supported_engines": ["vllm", "sglang"],
        "constraints": {
            "min_gpus": 1,
            "recommended_instance_types": ["ml.g5.2xlarge", "ml.g5.4xlarge"]
        }
    },
    "qwen2.5-vl-32b": {
        "name": "Qwen2.5-VL-32B-Instruct",
        "description": "通义千问视觉语言模型，32B参数",
        "model_path": "Qwen2.5-VL-32B-Instruct",
        "supports_multimodal": True,
        "supports_streaming": True,
        "supported_methods": ["SAGEMAKER_ENDPOINT", "HYPERPOD", "EKS", "EC2"],
        "supported_engines": ["vllm", "sglang"],
        "constraints": {
            "min_gpus": 2,
            "recommended_instance_types": ["ml.g5.4xlarge", "ml.g5.8xlarge", "ml.p4d.24xlarge"]
        }
    },
}


# EC2 Models Configuration (Manual HuggingFace deployments)
# Order: Qwen3 series → Qwen3-VL series → Qwen2.5 series → Llama series → DeepSeek series
EC2_MODELS = {
    # Qwen3 series
    "qwen3-0.6b": {
        "name": "Qwen3-0.6B",
        "huggingface_repo": "Qwen/Qwen3-0.6B",
        "description": "最新Qwen3模型，0.6B参数，高效轻量",
        "model_path": "Qwen/Qwen3-0.6B",
        "supports_multimodal": False,
        "supports_streaming": True
    },
    "qwen3-8b": {
        "name": "Qwen3-8B",
        "huggingface_repo": "Qwen/Qwen3-8B",
        "description": "最新Qwen3模型，8B参数，强大性能",
        "model_path": "Qwen/Qwen3-8B",
        "supports_multimodal": False,
        "supports_streaming": True
    },
    "qwen3-32b": {
        "name": "Qwen3-32B",
        "huggingface_repo": "Qwen/Qwen3-32B",
        "description": "最新Qwen3模型，32B参数，顶级性能",
        "model_path": "Qwen/Qwen3-32B",
        "supports_multimodal": False,
        "supports_streaming": True
    },
    # Qwen3-VL series
    "qwen3-vl-8b-thinking": {
        "name": "Qwen3-VL-8B-Thinking",
        "huggingface_repo": "Qwen/Qwen3-VL-8B-Thinking",
        "description": "Qwen3视觉语言模型，8B参数，具备思维链推理能力",
        "model_path": "Qwen/Qwen3-VL-8B-Thinking",
        "supports_multimodal": True,
        "supports_streaming": True
    },
    "qwen3-vl-30b-a3b-instruct": {
        "name": "Qwen3-VL-30B-A3B-Instruct",
        "huggingface_repo": "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "description": "Qwen3视觉语言模型，30B参数，指令优化版本",
        "model_path": "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "supports_multimodal": True,
        "supports_streaming": True
    },
    # Qwen2.5 series
    "qwen2.5-7b-instruct": {
        "name": "Qwen2.5-7B-Instruct",
        "huggingface_repo": "Qwen/Qwen2.5-7B-Instruct",
        "description": "Qwen2.5语言模型，7B参数，均衡性能",
        "model_path": "Qwen/Qwen2.5-7B-Instruct",
        "supports_multimodal": False,
        "supports_streaming": True
    },
    "qwen2.5-vl-7b-instruct": {
        "name": "Qwen2.5-VL-7B-Instruct",
        "huggingface_repo": "Qwen/Qwen2.5-VL-7B-Instruct",
        "description": "Qwen2.5视觉语言模型，7B参数",
        "model_path": "Qwen/Qwen2.5-VL-7B-Instruct",
        "supports_multimodal": True,
        "supports_streaming": True
    },
    # Llama series
    "llama-3.1-8b-instruct": {
        "name": "Llama-3.1-8B-Instruct",
        "huggingface_repo": "meta-llama/Llama-3.1-8B-Instruct",
        "description": "Meta Llama 3.1模型，8B参数，指令优化版本",
        "model_path": "meta-llama/Llama-3.1-8B-Instruct",
        "supports_multimodal": False,
        "supports_streaming": True
    },
    # DeepSeek series
    "deepseek-r1-distill-qwen-7b": {
        "name": "DeepSeek-R1-Distill-Qwen-7B",
        "huggingface_repo": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "description": "DeepSeek R1蒸馏模型，基于Qwen，7B参数",
        "model_path": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "supports_multimodal": False,
        "supports_streaming": True
    }
}


# Bedrock Models Configuration
BEDROCK_MODELS = {
    "claude4-sonnet": {
        "name": "Claude Sonnet 4",
        "description": "Latest Claude Sonnet 4 model (US inference profile)",
        "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude4-opus": {
        "name": "Claude Opus 4.1",
        "description": "Latest Claude Opus 4.1 model (US inference profile)",
        "model_id": "us.anthropic.claude-opus-4-1-20250805-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude37-sonnet": {
        "name": "Claude 3.7 Sonnet",
        "description": "Claude 3.7 Sonnet model (US inference profile)",
        "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude35-sonnet-v2": {
        "name": "Claude 3.5 Sonnet v2",
        "description": "Claude 3.5 Sonnet v2 (October 2024) - US inference profile",
        "model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude35-sonnet": {
        "name": "Claude 3.5 Sonnet",
        "description": "Claude 3.5 Sonnet original (June 2024) - US inference profile",
        "model_id": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude35-haiku": {
        "name": "Claude 3.5 Haiku",
        "description": "Claude 3.5 Haiku (October 2024) - US inference profile",
        "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude3-haiku": {
        "name": "Claude 3 Haiku",
        "description": "Claude 3 Haiku (March 2024) - US inference profile",
        "model_id": "us.anthropic.claude-3-haiku-20240307-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 4096
    },
    "claude3-opus": {
        "name": "Claude 3 Opus",
        "description": "Claude 3 Opus (February 2024) - US inference profile",
        "model_id": "us.anthropic.claude-3-opus-20240229-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 4096
    },
    "nova-pro": {
        "name": "Nova Pro",
        "description": "Amazon Nova Pro - US inference profile",
        "model_id": "us.amazon.nova-pro-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 5000
    },
    "nova-premier": {
        "name": "Nova Premier",
        "description": "Amazon Nova Premier - US inference profile",
        "model_id": "us.amazon.nova-premier-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 5000
    }
}


class ModelRegistry:
    """Registry for managing all available models."""

    def __init__(self):
        """Initialize the model registry."""
        self._emd_models = EMD_MODELS.copy()
        self._ec2_models = EC2_MODELS.copy()
        self._bedrock_models = BEDROCK_MODELS.copy()
        self._external_models: Dict[str, Dict[str, Any]] = {}

    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all available models organized by type.

        Returns:
            Dictionary containing all models organized by type
        """
        return {
            "bedrock": self._bedrock_models,
            "emd": self._emd_models,
            "ec2": self._ec2_models,
            "external": self._external_models
        }

    def get_emd_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all EMD models.

        Returns:
            Dictionary of EMD models
        """
        return self._emd_models.copy()

    def get_ec2_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all EC2 models.

        Returns:
            Dictionary of EC2 models
        """
        return self._ec2_models.copy()

    def get_bedrock_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all Bedrock models.

        Returns:
            Dictionary of Bedrock models
        """
        return self._bedrock_models.copy()

    def get_external_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all externally registered deployments."""
        return self._external_models.copy()

    def get_model_info(self, model_key: str, model_type: str = None) -> Dict[str, Any]:
        """Get information about a specific model.

        Args:
            model_key: Key identifying the model (or model_id/model_path)
            model_type: Type of model ('emd', 'ec2', or 'bedrock'). If None, searches all.

        Returns:
            Model information dictionary or empty dict if not found
        """
        # Resolve the key first in case it's a model_id or model_path
        resolved_key = self.resolve_model_key(model_key)

        if model_type == "emd" or model_type is None:
            if resolved_key in self._emd_models:
                return self._emd_models[resolved_key].copy()

        if model_type == "ec2" or model_type is None:
            if resolved_key in self._ec2_models:
                return self._ec2_models[resolved_key].copy()

        if model_type == "bedrock" or model_type is None:
            if resolved_key in self._bedrock_models:
                return self._bedrock_models[resolved_key].copy()

        if model_type == "external" or model_type is None:
            if resolved_key in self._external_models:
                return self._external_models[resolved_key].copy()

        return {}

    def is_emd_model(self, model_key: str) -> bool:
        """Check if a model is an EMD model.

        Args:
            model_key: Model key to check

        Returns:
            True if model is an EMD model
        """
        # Resolve the key first in case it's a model_path
        resolved_key = self.resolve_model_key(model_key)
        return resolved_key in self._emd_models

    def is_ec2_model(self, model_key: str) -> bool:
        """Check if a model is an EC2 model.

        Args:
            model_key: Model key to check

        Returns:
            True if model is an EC2 model
        """
        resolved_key = self.resolve_model_key(model_key)
        return resolved_key in self._ec2_models

    def resolve_model_key(self, model_identifier: str) -> str:
        """Resolve a model identifier to its registry key.

        Handles both model keys (e.g., 'claude35-sonnet-v2') and model_ids
        (e.g., 'us.anthropic.claude-3-5-sonnet-20241022-v2:0').

        Args:
            model_identifier: Model key or model_id

        Returns:
            Resolved model key, or original identifier if not found
        """
        # Check if it's already a valid key
        if (model_identifier in self._bedrock_models or
            model_identifier in self._emd_models or
            model_identifier in self._ec2_models or
            model_identifier in self._external_models):
            return model_identifier

        # Try to find by model_id in Bedrock models
        for key, info in self._bedrock_models.items():
            if info.get('model_id') == model_identifier:
                return key

        # Try to find by model_path in EMD models
        for key, info in self._emd_models.items():
            if info.get('model_path') == model_identifier:
                return key

        # Try to find by model_path in EC2 models
        for key, info in self._ec2_models.items():
            if info.get('model_path') == model_identifier:
                return key

        # Not found, return original
        return model_identifier

    def is_bedrock_model(self, model_key: str) -> bool:
        """Check if a model is a Bedrock model.

        Args:
            model_key: Model key to check

        Returns:
            True if model is a Bedrock model
        """
        # Resolve the key first in case it's a model_id
        resolved_key = self.resolve_model_key(model_key)
        return resolved_key in self._bedrock_models

    def is_external_model(self, model_key: str) -> bool:
        """Check if a model is an externally registered deployment."""
        return model_key in self._external_models

    def set_external_models(self, models: Dict[str, Dict[str, Any]]) -> None:
        """Replace the external deployment registry."""
        self._external_models = models.copy()

    def get_model_path(self, model_key: str) -> str:
        """Get the model path for EMD/EC2 models or model ID for Bedrock models.

        Args:
            model_key: Model key

        Returns:
            Model path or ID, empty string if not found
        """
        if model_key in self._emd_models:
            return self._emd_models[model_key].get("model_path", "")
        if model_key in self._ec2_models:
            return self._ec2_models[model_key].get("model_path", "")
        if model_key in self._bedrock_models:
            return self._bedrock_models[model_key].get("model_id", "")
        if model_key in self._external_models:
            model_info = self._external_models[model_key]
            return model_info.get("model_path") or model_info.get("model_name") or ""
        return ""

    def supports_multimodal(self, model_key: str) -> bool:
        """Check if a model supports multimodal input.

        Args:
            model_key: Model key to check

        Returns:
            True if model supports multimodal input
        """
        model_info = self.get_model_info(model_key)
        return model_info.get("supports_multimodal", False)

    def supports_streaming(self, model_key: str) -> bool:
        """Check if a model supports streaming output.

        Args:
            model_key: Model key to check

        Returns:
            True if model supports streaming
        """
        model_info = self.get_model_info(model_key)
        return model_info.get("supports_streaming", False)

    def get_supported_methods(self, model_key: str) -> List[str]:
        """Get supported launch methods for a model.

        Args:
            model_key: Model key to check

        Returns:
            List of supported launch methods
        """
        model_info = self.get_model_info(model_key)
        return model_info.get("supported_methods", [])

    def get_supported_engines(self, model_key: str) -> List[str]:
        """Get supported inference engines for a model.

        Args:
            model_key: Model key to check

        Returns:
            List of supported inference engines
        """
        model_info = self.get_model_info(model_key)
        return model_info.get("supported_engines", [])

    def get_constraints(self, model_key: str) -> Dict[str, Any]:
        """Get launch constraints for a model.

        Args:
            model_key: Model key to check

        Returns:
            Dictionary of launch constraints
        """
        model_info = self.get_model_info(model_key)
        return model_info.get("constraints", {})


# Global model registry instance
model_registry = ModelRegistry()
