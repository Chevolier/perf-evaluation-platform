"""Bedrock model abstractions and utilities."""

from typing import Dict, Any, List, Optional


class BedrockModel:
    """Abstraction for AWS Bedrock models."""
    
    def __init__(self, model_key: str, model_config: Dict[str, Any]):
        """Initialize Bedrock model.
        
        Args:
            model_key: Unique identifier for the model
            model_config: Model configuration dictionary
        """
        self.key = model_key
        self.config = model_config
        self.name = model_config.get("name", model_key)
        self.description = model_config.get("description", "")
        self.model_id = model_config.get("model_id", "")
        self.supports_multimodal = model_config.get("supports_multimodal", False)
        self.supports_streaming = model_config.get("supports_streaming", True)
        self.max_tokens = model_config.get("max_tokens", 4096)
    
    def build_inference_profile_arn(self, account_id: str, region: str = 'us-west-2') -> str:
        """Build inference profile ARN for cross-region inference.
        
        Args:
            account_id: AWS account ID
            region: AWS region
            
        Returns:
            Inference profile ARN
        """
        model_mapping = {
            'claude4': 'claude-3-5-sonnet-20241022-v2:0',
            'claude35': 'claude-3-5-sonnet-20241022-v2:0',
            'nova': 'nova-pro-v1:0'
        }
        
        model_suffix = model_mapping.get(self.key, self.model_id.split('.')[-1])
        return f"arn:aws:bedrock:{region}:{account_id}:inference-profile/{model_suffix}"
    
    def format_messages_for_bedrock(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format messages for Bedrock API.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Formatted messages for Bedrock
        """
        formatted_messages = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            # Handle different content types
            if isinstance(content, str):
                formatted_messages.append({
                    "role": role,
                    "content": [{"type": "text", "text": content}]
                })
            elif isinstance(content, list):
                # Already in the correct format or mixed content
                formatted_content = []
                for item in content:
                    if isinstance(item, str):
                        formatted_content.append({"type": "text", "text": item})
                    elif isinstance(item, dict):
                        formatted_content.append(item)
                
                formatted_messages.append({
                    "role": role,
                    "content": formatted_content
                })
        
        return formatted_messages
    
    def get_inference_params(self, **kwargs) -> Dict[str, Any]:
        """Get inference parameters for this model.
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            Inference parameters dictionary
        """
        params = {
            "modelId": self.model_id,
            "contentType": "application/json",
            "accept": "application/json"
        }
        
        # Add model-specific parameters
        inference_config = {}
        
        if "max_tokens" in kwargs:
            inference_config["maxTokens"] = min(kwargs["max_tokens"], self.max_tokens)
        else:
            inference_config["maxTokens"] = self.max_tokens
        
        if "temperature" in kwargs:
            inference_config["temperature"] = kwargs["temperature"]
        
        if "top_p" in kwargs:
            inference_config["topP"] = kwargs["top_p"]
        
        if inference_config:
            params["inferenceConfig"] = inference_config
        
        return params
    
    def supports_feature(self, feature: str) -> bool:
        """Check if model supports a specific feature.
        
        Args:
            feature: Feature name ('multimodal', 'streaming', etc.)
            
        Returns:
            True if feature is supported
        """
        feature_map = {
            "multimodal": self.supports_multimodal,
            "streaming": self.supports_streaming,
            "text": True,  # All models support text
        }
        
        return feature_map.get(feature, False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary representation.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "model_id": self.model_id,
            "supports_multimodal": self.supports_multimodal,
            "supports_streaming": self.supports_streaming,
            "max_tokens": self.max_tokens
        }