"""Model registry containing all supported model definitions."""

from typing import Dict, Any


# EMD (Elastic Model Deployment) Models Configuration
EMD_MODELS = {
    "qwen2-vl-7b": {
        "name": "Qwen2-VL-7B-Instruct",
        "description": "通义千问视觉语言模型，7B参数",
        "model_path": "Qwen2-VL-7B-Instruct",  # Use EMD supported model ID
        "supports_multimodal": True,
        "supports_streaming": True
    },
    "qwen2.5-vl-32b": {
        "name": "Qwen2.5-VL-32B-Instruct",
        "description": "通义千问视觉语言模型，32B参数",
        "model_path": "Qwen2.5-VL-32B-Instruct",  # Use EMD supported model ID
        "supports_multimodal": True,
        "supports_streaming": True
    },
    "qwen2.5-0.5b": {
        "name": "Qwen2.5-0.5B-Instruct",
        "description": "轻量级文本模型，适合快速推理",
        "model_path": "Qwen2.5-0.5B-Instruct",  # Use EMD supported model ID
        "supports_multimodal": False,
        "supports_streaming": True
    },
    "gemma-3-4b": {
        "name": "Gemma-3-4B-IT",
        "description": "Google开源语言模型",
        "model_path": "gemma-3-4b-it",  # Use EMD supported model ID
        "supports_multimodal": False,
        "supports_streaming": True
    },
    "ui-tars-1.5-7b": {
        "name": "UI-TARS-1.5-7B",
        "description": "用户界面理解专用模型",
        "model_path": "UI-TARS-1.5-7B",  # Use EMD supported model ID
        "supports_multimodal": True,
        "supports_streaming": False
    },
    "qwen3-0.6b": {
        "name": "Qwen3-0.6B",
        "description": "最新Qwen3模型，0.6B参数，高效轻量",
        "model_path": "Qwen3-0.6B",  # Already correct
        "supports_multimodal": False,
        "supports_streaming": True
    },
    "qwen3-8b": {
        "name": "Qwen3-8B",
        "description": "最新Qwen3模型，8B参数，强大性能",
        "model_path": "Qwen3-8B",  # Already correct
        "supports_multimodal": False,
        "supports_streaming": True
    }
}


# Bedrock Models Configuration
BEDROCK_MODELS = {
    "claude4": {
        "name": "Claude 4",
        "description": "Anthropic Claude 4",
        "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "claude35": {
        "name": "Claude 3.5 Sonnet",
        "description": "Anthropic Claude 3.5 Sonnet",
        "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "supports_multimodal": True,
        "supports_streaming": True,
        "max_tokens": 8192
    },
    "nova": {
        "name": "Nova Pro",
        "description": "Amazon Nova Pro",
        "model_id": "amazon.nova-pro-v1:0",
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
        self._bedrock_models = BEDROCK_MODELS.copy()
    
    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all available models organized by type.
        
        Returns:
            Dictionary containing all models organized by type
        """
        return {
            "bedrock": self._bedrock_models,
            "emd": self._emd_models
        }
    
    def get_emd_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all EMD models.
        
        Returns:
            Dictionary of EMD models
        """
        return self._emd_models.copy()
    
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
            model_type: Type of model ('emd' or 'bedrock'). If None, searches both.
            
        Returns:
            Model information dictionary or empty dict if not found
        """
        if model_type == "emd" or model_type is None:
            if model_key in self._emd_models:
                return self._emd_models[model_key].copy()
        
        if model_type == "bedrock" or model_type is None:
            if model_key in self._bedrock_models:
                return self._bedrock_models[model_key].copy()
        
        return {}
    
    def is_emd_model(self, model_key: str) -> bool:
        """Check if a model is an EMD model.
        
        Args:
            model_key: Model key to check
            
        Returns:
            True if model is an EMD model
        """
        return model_key in self._emd_models
    
    def is_bedrock_model(self, model_key: str) -> bool:
        """Check if a model is a Bedrock model.
        
        Args:
            model_key: Model key to check
            
        Returns:
            True if model is a Bedrock model
        """
        return model_key in self._bedrock_models
    
    def get_model_path(self, model_key: str) -> str:
        """Get the model path for EMD models or model ID for Bedrock models.
        
        Args:
            model_key: Model key
            
        Returns:
            Model path or ID, empty string if not found
        """
        if model_key in self._emd_models:
            return self._emd_models[model_key].get("model_path", "")
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