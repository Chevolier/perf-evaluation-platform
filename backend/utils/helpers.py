"""General helper utilities and functions."""

import hashlib
import uuid
import boto3
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any


def generate_session_id() -> str:
    """Generate a unique session ID.
    
    Returns:
        Unique session identifier
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_suffix}"


def generate_short_tag(model_name: str) -> str:
    """Generate a short deployment tag for a model.
    
    Args:
        model_name: Name of the model
        
    Returns:
        Short deployment tag
    """
    timestamp = datetime.now().strftime("%m%d%H%M")
    # Create a short hash from model name
    model_hash = hashlib.md5(model_name.encode()).hexdigest()[:4]
    return f"{timestamp}{model_hash}"


def get_account_id() -> Optional[str]:
    """Get AWS account ID from STS.
    
    Returns:
        AWS account ID or None if error
    """
    try:
        sts_client = boto3.client('sts')
        response = sts_client.get_caller_identity()
        return response.get('Account')
    except Exception as e:
        print(f"Error getting AWS account ID: {e}")
        return None


def run_command(command: list, timeout: int = 30, capture_output: bool = True) -> Dict[str, Any]:
    """Run a system command with error handling.
    
    Args:
        command: Command and arguments as list
        timeout: Command timeout in seconds
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Dictionary with command results
    """
    try:
        result = subprocess.run(
            command,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=False
        )
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout if capture_output else None,
            "stderr": result.stderr if capture_output else None,
            "command": " ".join(command)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out",
            "timeout": timeout,
            "command": " ".join(command)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": " ".join(command)
        }


def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to maximum length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing/replacing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscores
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty
    if not filename:
        filename = "unnamed_file"
    
    return filename


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    size_index = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and size_index < len(size_names) - 1:
        size /= 1024.0
        size_index += 1
    
    return f"{size:.1f} {size_names[size_index]}"


def calculate_duration_ms(start_time: datetime, end_time: datetime = None) -> float:
    """Calculate duration in milliseconds between two timestamps.
    
    Args:
        start_time: Start timestamp
        end_time: End timestamp (defaults to now)
        
    Returns:
        Duration in milliseconds
    """
    if end_time is None:
        end_time = datetime.now()
    
    duration = end_time - start_time
    return duration.total_seconds() * 1000


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary (base)
        dict2: Second dictionary (overlay)
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if (key in result and 
            isinstance(result[key], dict) and 
            isinstance(value, dict)):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_config_keys(config: Dict[str, Any], required_keys: list, 
                        optional_keys: list = None) -> Dict[str, Any]:
    """Validate configuration dictionary has required keys.
    
    Args:
        config: Configuration dictionary
        required_keys: List of required keys
        optional_keys: List of optional keys (for validation)
        
    Returns:
        Validation result dictionary
    """
    missing_keys = []
    invalid_keys = []
    
    # Check required keys
    for key in required_keys:
        if key not in config:
            missing_keys.append(key)
    
    # Check for invalid keys (if optional_keys provided)
    if optional_keys is not None:
        allowed_keys = set(required_keys + optional_keys)
        for key in config.keys():
            if key not in allowed_keys:
                invalid_keys.append(key)
    
    return {
        "valid": len(missing_keys) == 0 and len(invalid_keys) == 0,
        "missing_keys": missing_keys,
        "invalid_keys": invalid_keys
    }


class Timer:
    """Simple timer utility for measuring execution time."""
    
    def __init__(self):
        """Initialize timer."""
        self.start_time = None
        self.end_time = None
    
    def start(self) -> None:
        """Start the timer."""
        self.start_time = datetime.now()
        self.end_time = None
    
    def stop(self) -> float:
        """Stop the timer and return duration.
        
        Returns:
            Duration in milliseconds
        """
        self.end_time = datetime.now()
        if self.start_time is None:
            return 0.0
        return calculate_duration_ms(self.start_time, self.end_time)
    
    def elapsed(self) -> float:
        """Get elapsed time without stopping timer.
        
        Returns:
            Elapsed time in milliseconds
        """
        if self.start_time is None:
            return 0.0
        return calculate_duration_ms(self.start_time)
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()