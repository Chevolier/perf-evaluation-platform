"""Model definitions and management for the inference platform."""

from .model_registry import ModelRegistry, EC2_MODELS, BEDROCK_MODELS, model_registry
from .bedrock_models import BedrockModel
from .emd_models import EMDModel

__all__ = [
    'ModelRegistry', 'EC2_MODELS', 'BEDROCK_MODELS', 'model_registry',
    'BedrockModel', 'EMDModel'
]