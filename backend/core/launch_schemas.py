"""Launch method schemas and parameter definitions."""

from typing import Dict, Any

# Launch method schemas with parameter definitions
LAUNCH_METHODS = {
    'SAGEMAKER_ENDPOINT': {
        'name': 'SageMaker Endpoint (EMD)',
        'description': 'Deploy via Elastic Model Deployment',
        'supported_engines': ['vllm', 'sglang', 'tgi', 'transformers'],
        'parameters': {
            'instance_type': {
                'type': 'select',
                'label': 'Instance Type',
                'required': True,
                'default': 'ml.g5.2xlarge',
                'options': [
                    'ml.g5.xlarge', 
                    'ml.g5.2xlarge', 
                    'ml.g5.4xlarge', 
                    'ml.g5.8xlarge',
                    'ml.g5.12xlarge',
                    'ml.g5.16xlarge',
                    'ml.g5.24xlarge',
                    'ml.g5.48xlarge',
                    'ml.p4d.24xlarge', 
                    'ml.p5.4xlarge',
                    'ml.p5.48xlarge'
                ]
            },
            'service_type': {
                'type': 'select',
                'label': 'Service Type',
                'default': 'sagemaker_realtime',
                'options': ['sagemaker_realtime', 'sagemaker_async', 'ecs', 'local']
            }
        }
    },
    'HYPERPOD': {
        'name': 'SageMaker HyperPod',
        'description': 'Deploy via HyperPod cluster',
        'supported_engines': ['vllm', 'sglang'],
        'parameters': {
            'preset': {
                'type': 'select',
                'label': 'Cluster Size',
                'required': True,
                'default': 'small',
                'options': ['small', 'medium', 'large']
            },
            'instance_type': {
                'type': 'select',
                'label': 'GPU Instance Type',
                'default': 'ml.p4d.24xlarge',
                'options': [
                    'ml.p4d.24xlarge', 
                    'ml.p5.48xlarge', 
                    'ml.g5.48xlarge'
                ]
            },
            'instance_count': {
                'type': 'number',
                'label': 'Number of Nodes',
                'default': 2,
                'min': 1,
                'max': 100
            },
            'gpus_per_pod': {
                'type': 'select',
                'label': 'GPUs per Pod',
                'default': 8,
                'options': [1, 2, 4, 8]
            },
            'replicas': {
                'type': 'number',
                'label': 'Number of Pods',
                'default': 1,
                'min': 1
            },
            'region': {
                'type': 'select',
                'label': 'AWS Region',
                'default': 'us-east-1',
                'options': ['us-east-1', 'us-west-2', 'eu-west-1']
            }
        }
    },
    'EKS': {
        'name': 'EKS Deployment',
        'description': 'Deploy to existing EKS cluster',
        'supported_engines': ['vllm', 'sglang'],
        'parameters': {
            'cluster_name': {
                'type': 'text',
                'label': 'EKS Cluster Name',
                'required': True,
                'placeholder': 'my-eks-cluster'
            },
            'namespace': {
                'type': 'text',
                'label': 'Kubernetes Namespace',
                'default': 'default'
            },
            'replicas': {
                'type': 'number',
                'label': 'Replica Count',
                'default': 1,
                'min': 1
            },
            'gpus_per_pod': {
                'type': 'select',
                'label': 'GPUs per Pod',
                'default': 1,
                'options': [1, 2, 4, 8]
            },
            'container_image': {
                'type': 'text',
                'label': 'Container Image (optional)',
                'placeholder': 'Leave empty for default engine image'
            },
            'region': {
                'type': 'select',
                'label': 'AWS Region',
                'default': 'us-east-1',
                'options': ['us-east-1', 'us-west-2', 'eu-west-1']
            }
        }
    },
    'EC2': {
        'name': 'EC2 Instance',
        'description': 'Launch on EC2 with IAM role-based access',
        'supported_engines': ['vllm', 'sglang'],
        'parameters': {
            'instance_type': {
                'type': 'select',
                'label': 'Instance Type',
                'required': True,
                'default': 'g5.2xlarge',
                'options': [
                    'g5.xlarge', 
                    'g5.2xlarge', 
                    'g5.4xlarge', 
                    'g5.8xlarge',
                    'g5.12xlarge', 
                    'g5.16xlarge',
                    'g5.24xlarge',
                    'g5.48xlarge',
                    'p4d.24xlarge',
                    'p5.4xlarge',
                    'p5.48xlarge'
                ]
            },
            'ami_id': {
                'type': 'text',
                'label': 'AMI ID (optional)',
                'placeholder': 'Leave empty for default Deep Learning AMI'
            },
            'iam_instance_profile': {
                'type': 'text',
                'label': 'IAM Instance Profile ARN',
                'required': True,
                'placeholder': 'arn:aws:iam::ACCOUNT:instance-profile/NAME'
            },
            'security_group_ids': {
                'type': 'text',
                'label': 'Security Group IDs (comma-separated)',
                'required': True,
                'placeholder': 'sg-12345678,sg-87654321'
            },
            'subnet_id': {
                'type': 'text',
                'label': 'Subnet ID',
                'required': True,
                'placeholder': 'subnet-12345678'
            },
            'region': {
                'type': 'select',
                'label': 'AWS Region',
                'default': 'us-east-1',
                'options': ['us-east-1', 'us-west-2', 'eu-west-1']
            }
        }
    }
}


def get_launch_method_schema(method: str) -> Dict[str, Any]:
    """Get schema for a specific launch method.
    
    Args:
        method: Launch method identifier
        
    Returns:
        Method schema dictionary or empty dict if not found
    """
    return LAUNCH_METHODS.get(method, {})


def get_all_launch_methods() -> Dict[str, Any]:
    """Get all available launch method schemas.
    
    Returns:
        Dictionary of all launch method schemas
    """
    return LAUNCH_METHODS.copy()


def validate_launch_params(method: str, params: Dict[str, Any]) -> tuple[bool, str]:
    """Validate launch parameters against method schema.
    
    Args:
        method: Launch method identifier
        params: Parameters to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    schema = get_launch_method_schema(method)
    if not schema:
        return False, f"Unknown launch method: {method}"
    
    method_params = schema.get('parameters', {})
    
    # Check required parameters
    for param_name, param_def in method_params.items():
        if param_def.get('required', False):
            if param_name not in params or params[param_name] is None:
                return False, f"Required parameter '{param_name}' is missing"
    
    # Validate parameter values
    for param_name, param_value in params.items():
        if param_name not in method_params:
            continue  # Allow extra parameters
        
        param_def = method_params[param_name]
        
        # Validate select options
        if param_def.get('type') == 'select' and 'options' in param_def:
            if param_value not in param_def['options']:
                return False, f"Invalid value '{param_value}' for parameter '{param_name}'. Must be one of: {param_def['options']}"
        
        # Validate number ranges
        if param_def.get('type') == 'number':
            if not isinstance(param_value, (int, float)):
                return False, f"Parameter '{param_name}' must be a number"
            
            if 'min' in param_def and param_value < param_def['min']:
                return False, f"Parameter '{param_name}' must be >= {param_def['min']}"
            
            if 'max' in param_def and param_value > param_def['max']:
                return False, f"Parameter '{param_name}' must be <= {param_def['max']}"
    
    return True, ""


def get_default_params(method: str) -> Dict[str, Any]:
    """Get default parameters for a launch method.
    
    Args:
        method: Launch method identifier
        
    Returns:
        Dictionary of default parameters
    """
    schema = get_launch_method_schema(method)
    if not schema:
        return {}
    
    defaults = {}
    for param_name, param_def in schema.get('parameters', {}).items():
        if 'default' in param_def:
            defaults[param_name] = param_def['default']
    
    return defaults
