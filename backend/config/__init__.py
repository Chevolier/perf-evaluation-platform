"""Configuration management for the inference platform."""

from .config_manager import ConfigManager, get_config, init_config
from .settings import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    DEFAULT_CONFIG, ENVIRONMENT_OVERRIDES,
    EMD_INSTANCE_TYPES, EMD_ENGINE_TYPES, BEDROCK_REGIONS,
    get_environment, is_development, is_production
)

__all__ = [
    'ConfigManager', 'get_config', 'init_config',
    'APP_NAME', 'APP_VERSION', 'APP_DESCRIPTION',
    'DEFAULT_CONFIG', 'ENVIRONMENT_OVERRIDES',
    'EMD_INSTANCE_TYPES', 'EMD_ENGINE_TYPES', 'BEDROCK_REGIONS',
    'get_environment', 'is_development', 'is_production'
]