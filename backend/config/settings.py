"""Application settings and constants."""

import os
from pathlib import Path

# Application information
APP_NAME = "Inference Platform"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Large Model Inference and Benchmarking Platform"

# Directory paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config" / "environments"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Default configuration
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
        "workers": 1
    },
    "logging": {
        "level": "INFO",
        "file": str(LOGS_DIR / "app.log"),
        "max_bytes": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5
    },
    "aws": {
        "region": "us-east-1",
        "account_id": None,  # Will be detected automatically
        "profile": None,
        "access_key_id": None,
        "secret_access_key": None,
        "session_token": None
    },
    "models": {
        "emd": {
            "base_url": "http://localhost:8000",
            "default_tag": None,
            "timeout": 300
        },
        "bedrock": {
            "region": "us-west-2",
            "timeout": 300
        }
    },
    "database": {
        "path": str(DATA_DIR / "app.db"),
        "echo": False
    },
    "storage": {
        "base_path": str(OUTPUTS_DIR),
        "cleanup_days": 30
    },
    "hyperpod": {
        "state_machine_arn": None,
        "prepare_config_lambda_arn": None,
        "post_deploy_validation_lambda_arn": None,
        "persist_outputs_lambda_arn": None,
        "cleanup_lambda_arn": None,
        "record_failure_lambda_arn": None,
        "default_timeout_seconds": 3600,
        "default_region": "us-west-2",
        "config_s3_bucket": None,
        "outputs_parameter_prefix": "/perf-eval/hyperpod",
        "infraforge_root": "../InfraForge",
        "deploy_script": "scripts/deploy_hyperpod.sh",
        "destroy_script": "scripts/deploy_hyperpod.sh",
        "presets": {
            "small": "configs/hyperpod/config_hyperpod_small.yaml",
            "medium": "configs/hyperpod/config_hyperpod_medium.yaml",
            "large": "configs/hyperpod/config_hyperpod_large.yaml"
        },
        "dry_run": False,
        "log_directory": "logs/hyperpod",
        "supported_overrides": [
            "region",
            "cluster_tag",
            "gpu_instance_type",
            "gpu_instance_count",
            "availability_zone",
            "stack_name"
        ]
    },
    "benchmarking": {
        "default_timeout": 1800,  # 30 minutes
        "max_concurrent": 5,
        "result_retention_days": 90
    },
    "cors": {
        "origins": ["http://localhost:3000", "http://localhost:3001"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
}

# Environment-specific overrides
ENVIRONMENT_OVERRIDES = {
    "development": {
        "server": {
            "debug": True,
            "port": 5000
        },
        "logging": {
            "level": "DEBUG"
        }
    },
    "production": {
        "server": {
            "debug": False,
            "workers": 4
        },
        "logging": {
            "level": "INFO"
        }
    }
}

# Model configuration constants
EMD_INSTANCE_TYPES = [
    "ml.g5.xlarge", "ml.g5.2xlarge", "ml.g5.4xlarge", "ml.g5.8xlarge",
    "ml.g5.12xlarge", "ml.g5.16xlarge", "ml.g5.24xlarge", "ml.g5.48xlarge",
    "ml.p4d.24xlarge", "ml.p4de.24xlarge", "ml.p5.48xlarge"
]

EMD_ENGINE_TYPES = ["vllm", "tgi", "sagemaker"]

BEDROCK_REGIONS = [
    "us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ap-northeast-1"
]

# API configuration
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Rate limiting
RATE_LIMITS = {
    "inference": "100/minute",
    "deployment": "10/minute",
    "benchmark": "5/minute"
}

# File upload limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}

# Benchmark configuration
BENCHMARK_CONFIG = {
    "stress_test": {
        "min_processes": 1,
        "max_processes": 128,
        "min_input_tokens": 100,
        "max_input_tokens": 12800,
        "min_output_tokens": 100,
        "max_output_tokens": 1000,
        "default_temperature": 0.1,
        "default_top_p": 0.9
    },
    "evaluation": {
        "supported_datasets": ["mmlu", "hellaswag", "truthfulqa"],
        "batch_sizes": [1, 4, 8, 16, 32],
        "max_samples": 1000
    }
}

# Security configuration
SECURITY_CONFIG = {
    "secret_key": os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production"),
    "session_timeout": 3600,  # 1 hour
    "max_login_attempts": 5,
    "lockout_duration": 300,  # 5 minutes
    "password_min_length": 8
}

# Monitoring and health check
HEALTH_CHECK_CONFIG = {
    "check_database": True,
    "check_emd_connection": True,
    "check_aws_credentials": True,
    "timeout": 10
}

# Feature flags
FEATURE_FLAGS = {
    "enable_video_processing": True,
    "enable_batch_inference": True,
    "enable_model_comparison": True,
    "enable_custom_prompts": True,
    "enable_export_results": True,
    "enable_user_auth": False  # Disabled by default
}

def get_environment() -> str:
    """Get current environment from environment variable.
    
    Returns:
        Environment name (development, production, etc.)
    """
    return os.environ.get("ENVIRONMENT", "development")


def is_development() -> bool:
    """Check if running in development environment.
    
    Returns:
        True if development environment
    """
    return get_environment() == "development"


def is_production() -> bool:
    """Check if running in production environment.
    
    Returns:
        True if production environment
    """
    return get_environment() == "production"
