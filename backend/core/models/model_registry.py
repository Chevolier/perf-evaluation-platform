"""Model registry containing all supported model definitions."""

from typing import Dict, Any


# EC2 Models Configuration (formerly EMD models)
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
# Model IDs use inference profile IDs with "us." prefix for on-demand throughput
# Verified from: aws bedrock list-inference-profiles --region us-west-2
BEDROCK_MODELS = {
    # Anthropic Claude Models (ordered by capability: Opus > Sonnet > Haiku)
    "claude-opus-4.5": {
        "name": "Claude Opus 4.5",
        "description": "Anthropic Claude Opus 4.5 - Most capable model",
        "model_id": "us.anthropic.claude-opus-4-5-20251101-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },
    "claude-opus-4.1": {
        "name": "Claude Opus 4.1",
        "description": "Anthropic Claude Opus 4.1 - High capability model",
        "model_id": "us.anthropic.claude-opus-4-1-20250805-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },
    "claude-sonnet-4.5": {
        "name": "Claude Sonnet 4.5",
        "description": "Anthropic Claude Sonnet 4.5 - Balanced performance and speed",
        "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },
    "claude-sonnet-4": {
        "name": "Claude Sonnet 4",
        "description": "Anthropic Claude Sonnet 4 - Balanced performance",
        "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },
    "claude-haiku-4.5": {
        "name": "Claude Haiku 4.5",
        "description": "Anthropic Claude Haiku 4.5 - Fast and efficient",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },

    # Amazon Nova Models
    "nova-pro": {
        "name": "Nova Pro",
        "description": "Amazon Nova Pro - Supports text, image, and video",
        "model_id": "us.amazon.nova-pro-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },
    "nova-lite": {
        "name": "Nova Lite",
        "description": "Amazon Nova Lite - Fast and efficient",
        "model_id": "us.amazon.nova-lite-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    },
    "nova-2-lite": {
        "name": "Nova 2 Lite",
        "description": "Amazon Nova 2 Lite - Supports text, image, and video",
        "model_id": "us.amazon.nova-2-lite-v1:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 16384
    }
}


class ModelRegistry:
    """Registry for managing all available models."""
    
    def __init__(self):
        """Initialize the model registry."""
        self._ec2_models = EC2_MODELS.copy()
        self._bedrock_models = BEDROCK_MODELS.copy()
    
    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all available models organized by type.
        
        Returns:
            Dictionary containing all models organized by type
        """
        return {
            "bedrock": self._bedrock_models,
            "ec2": self._ec2_models
        }
    
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
    
    def get_model_info(self, model_key: str, model_type: str = None) -> Dict[str, Any]:
        """Get information about a specific model.

        Args:
            model_key: Key identifying the model
            model_type: Type of model ('ec2' or 'bedrock'). If None, searches both.

        Returns:
            Model information dictionary or empty dict if not found
        """
        if model_type == "ec2" or model_type is None:
            if model_key in self._ec2_models:
                return self._ec2_models[model_key].copy()

        if model_type == "bedrock" or model_type is None:
            if model_key in self._bedrock_models:
                return self._bedrock_models[model_key].copy()

        return {}
    
    def is_ec2_model(self, model_key: str) -> bool:
        """Check if a model is an EC2 model.

        Args:
            model_key: Model key to check

        Returns:
            True if model is an EC2 model
        """
        return model_key in self._ec2_models
    
    def is_bedrock_model(self, model_key: str) -> bool:
        """Check if a model is a Bedrock model.
        
        Args:
            model_key: Model key to check
            
        Returns:
            True if model is a Bedrock model
        """
        return model_key in self._bedrock_models
    
    def get_model_path(self, model_key: str) -> str:
        """Get the model path for EC2 models or model ID for Bedrock models.

        Args:
            model_key: Model key

        Returns:
            Model path or ID, empty string if not found
        """
        if model_key in self._ec2_models:
            return self._ec2_models[model_key].get("model_path", "")
        elif model_key in self._bedrock_models:
            return self._bedrock_models[model_key].get("model_id", "")
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


# Global model registry instance
model_registry = ModelRegistry()