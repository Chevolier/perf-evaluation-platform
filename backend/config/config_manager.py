"""Configuration management system with environment support."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from utils.helpers import deep_merge_dicts


class ConfigManager:
    """Centralized configuration manager with environment support."""
    
    def __init__(self, config_dir: str = "config/environments"):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self._config: Dict[str, Any] = {}
        self._environment: Optional[str] = None
    
    def load_config(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration for specified environment.
        
        Args:
            environment: Environment name (development, production, etc.)
                        If None, loads only default config
        
        Returns:
            Loaded configuration dictionary
        """
        self._environment = environment
        
        # Start with default configuration
        default_config = self._load_config_file("default")
        if not default_config:
            raise ValueError("Default configuration file not found")
        
        self._config = default_config.copy()
        
        # Overlay environment-specific configuration
        if environment:
            env_config = self._load_config_file(environment)
            if env_config:
                self._config = deep_merge_dicts(self._config, env_config)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        return self._config
    
    def _load_config_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file.
        
        Args:
            filename: Configuration filename (without extension)
            
        Returns:
            Configuration dictionary or None if file doesn't exist
        """
        config_path = self.config_dir / f"{filename}.yaml"
        
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing {config_path}: {e}")
        except IOError as e:
            raise ValueError(f"Error reading {config_path}: {e}")
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        # Define environment variable mappings
        env_mappings = {
            # Server configuration
            'SERVER_HOST': 'server.host',
            'SERVER_PORT': 'server.port',
            'SERVER_DEBUG': 'server.debug',
            
            # Logging configuration
            'LOG_LEVEL': 'logging.level',
            'LOG_FILE': 'logging.file',
            
            # AWS configuration
            'AWS_REGION': 'aws.region',
            'AWS_ACCOUNT_ID': 'aws.account_id',
            
            # EC2 configuration
            'EC2_DEFAULT_PORT': 'models.ec2.default_port',
            'EC2_TIMEOUT': 'models.ec2.timeout',
            
            # Database configuration
            'DATABASE_URL': 'database.url',
            'DATABASE_PATH': 'database.path',
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value is not None:
                self._set_nested_value(config_path, self._convert_env_value(env_value))
    
    def _set_nested_value(self, path: str, value: Any) -> None:
        """Set nested configuration value using dot notation.
        
        Args:
            path: Dot-separated path (e.g., 'server.host')
            value: Value to set
        """
        keys = path.split('.')
        current = self._config
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type.
        
        Args:
            value: Environment variable value
            
        Returns:
            Converted value
        """
        # Handle boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Handle integer values
        if value.isdigit():
            return int(value)
        
        # Handle float values
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'server.port')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        current = self._config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'server.port')
            value: Value to set
        """
        self._set_nested_value(key, value)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section.
        
        Args:
            section: Section name
            
        Returns:
            Configuration section dictionary
        """
        return self._config.get(section, {})
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration data.
        
        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()
    
    def get_environment(self) -> Optional[str]:
        """Get current environment name.
        
        Returns:
            Environment name or None
        """
        return self._environment
    
    def validate_required_keys(self, required_keys: list) -> Dict[str, Any]:
        """Validate that required configuration keys are present.
        
        Args:
            required_keys: List of required configuration keys
            
        Returns:
            Validation result dictionary
        """
        missing_keys = []
        
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)
        
        return {
            "valid": len(missing_keys) == 0,
            "missing_keys": missing_keys
        }


# Global configuration instance
_config_manager = None


def get_config() -> ConfigManager:
    """Get global configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def init_config(environment: str = None, config_dir: str = None) -> ConfigManager:
    """Initialize global configuration manager.
    
    Args:
        environment: Environment name
        config_dir: Configuration directory path
        
    Returns:
        Initialized ConfigManager instance
    """
    global _config_manager
    
    if config_dir:
        _config_manager = ConfigManager(config_dir)
    else:
        _config_manager = ConfigManager()
    
    _config_manager.load_config(environment)
    return _config_manager