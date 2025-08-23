"""Model definitions and management for the inference platform."""

from .model_registry import ModelRegistry, EMD_MODELS, BEDROCK_MODELS, model_registry
from .emd_models import EMDModel
from .bedrock_models import BedrockModel

__all__ = [
    'ModelRegistry', 'EMD_MODELS', 'BEDROCK_MODELS', 'model_registry',
    'EMDModel', 'BedrockModel'
]