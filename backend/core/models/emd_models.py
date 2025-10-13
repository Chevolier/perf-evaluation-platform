"""EMD model abstractions and utilities."""

import hashlib
from typing import Dict, Any, Tuple
from datetime import datetime


class EMDModel:
    """Abstraction for EMD (Elastic Model Deployment) models."""
    
    def __init__(self, model_key: str, model_config: Dict[str, Any]):
        """Initialize EMD model.
        
        Args:
            model_key: Unique identifier for the model
            model_config: Model configuration dictionary
        """
        self.key = model_key
        self.config = model_config
        self.name = model_config.get("name", model_key)
        self.description = model_config.get("description", "")
        self.model_path = model_config.get("model_path", model_key)
        self.supports_multimodal = model_config.get("supports_multimodal", False)
        self.supports_streaming = model_config.get("supports_streaming", True)
    
    def generate_tag(self) -> str:
        """Generate a unique deployment tag for this model.
        
        Returns:
            Unique deployment tag
        """
        timestamp = datetime.now().strftime("%m%d%H%M")
        content = f"{self.model_path}-{timestamp}"
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:4]
        return f"{timestamp}{hash_suffix}"
    
    def validate_deployment_config(self, instance_type: str, engine_type: str) -> Tuple[bool, str]:
        """Validate deployment configuration.

        Args:
            instance_type: AWS instance type (with or without ml. prefix)
            engine_type: Inference engine type

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Valid instance types for EMD deployment (bare names)
        valid_instances = [
            "g5.xlarge", "g5.2xlarge", "g5.4xlarge", "g5.8xlarge",
            "g5.12xlarge", "g5.16xlarge", "g5.24xlarge", "g5.48xlarge",
            "p4d.24xlarge", "p4de.24xlarge", "p5.48xlarge"
        ]

        # Valid engine types
        valid_engines = ["vllm", "tgi", "sagemaker"]

        # Normalize instance type by removing ml. prefix if present
        normalized_instance = instance_type.replace("ml.", "", 1) if instance_type.startswith("ml.") else instance_type

        if normalized_instance not in valid_instances:
            return False, f"Invalid instance type: {instance_type}"

        if engine_type not in valid_engines:
            return False, f"Invalid engine type: {engine_type}"

        # Special validations for multimodal models
        if self.supports_multimodal and engine_type == "tgi":
            return False, "Multimodal models are not supported with TGI engine"

        return True, "Configuration is valid"
    
    def get_deployment_config(self, instance_type: str = "g5.2xlarge", 
                            engine_type: str = "vllm") -> Dict[str, Any]:
        """Get deployment configuration for this model.
        
        Args:
            instance_type: AWS instance type
            engine_type: Inference engine type
            
        Returns:
            Deployment configuration dictionary
        """
        return {
            "model_key": self.key,
            "model_path": self.model_path,
            "model_name": self.name,
            "instance_type": instance_type,
            "engine_type": engine_type,
            "supports_multimodal": self.supports_multimodal,
            "supports_streaming": self.supports_streaming,
            "deployment_tag": self.generate_tag()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary representation.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "model_path": self.model_path,
            "supports_multimodal": self.supports_multimodal,
            "supports_streaming": self.supports_streaming
        }