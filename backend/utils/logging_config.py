"""Logging configuration and utilities."""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


class FlushingRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Custom rotating file handler that flushes after every log message."""
    
    def emit(self, record):
        """Emit a record and flush immediately."""
        try:
            super().emit(record)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        log_format: Custom log format (optional)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
    """
    # Default log format
    if log_format is None:
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Check if we already have a file handler for this specific log file to avoid duplicates
    if log_file:
        abs_log_file = os.path.abspath(log_file)
        existing_file_handlers = [h for h in logger.handlers 
                                if isinstance(h, (logging.FileHandler, logging.handlers.RotatingFileHandler))
                                and hasattr(h, 'baseFilename') 
                                and h.baseFilename == abs_log_file]
        
        # If we already have a handler for this exact file, don't add another
        if existing_file_handlers:
            print(f"📋 File handler already exists for: {log_file}")
            return
    
    # Clear existing handlers only if we're setting up fresh logging
    if not logger.handlers:
        pass  # No handlers to remove
    else:
        # Only remove if we don't have the right file handler
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Print debug info to help troubleshoot
        print(f"📝 Setting up file logging: {log_file}")
        print(f"📝 Log level: {log_level}")
        print(f"📝 Log directory exists: {log_path.parent.exists()}")
        
        try:
            # Use custom flushing file handler to ensure immediate writes
            class ImmediateFlushFileHandler(logging.FileHandler):
                def emit(self, record):
                    super().emit(record)
                    self.flush()
            
            file_handler = ImmediateFlushFileHandler(
                log_file,
                mode='a',
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Test the file logging immediately with forced flush
            test_logger = logging.getLogger('setup_logging_test')
            test_logger.info("✅ File logging setup complete and tested")
            
            # Force flush all handlers
            for handler in logger.handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()
            
            print(f"✅ File handler added successfully to: {log_file}")
            
        except Exception as e:
            print(f"❌ Failed to setup file logging: {e}")
            import traceback
            traceback.print_exc()
            raise


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class RequestLogger:
    """Logger for HTTP requests and responses."""
    
    def __init__(self, logger_name: str = "inference_platform.requests"):
        """Initialize request logger.
        
        Args:
            logger_name: Name for the request logger
        """
        self.logger = get_logger(logger_name)
    
    def log_request(self, method: str, path: str, headers: dict = None, 
                   body: dict = None, client_ip: str = None) -> None:
        """Log incoming HTTP request.
        
        Args:
            method: HTTP method
            path: Request path
            headers: Request headers (optional)
            body: Request body (optional, will be truncated if large)
            client_ip: Client IP address (optional)
        """
        log_data = {
            "type": "request",
            "method": method,
            "path": path,
            "client_ip": client_ip
        }
        
        if headers:
            # Log only important headers, exclude sensitive ones
            safe_headers = {k: v for k, v in headers.items() 
                          if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
            log_data["headers"] = safe_headers
        
        if body and isinstance(body, dict):
            # Truncate large bodies and exclude sensitive fields
            safe_body = {k: v for k, v in body.items() 
                        if k.lower() not in ['password', 'token', 'secret']}
            
            # Truncate long text fields
            for key, value in safe_body.items():
                if isinstance(value, str) and len(value) > 1000:
                    safe_body[key] = value[:1000] + "... (truncated)"
            
            log_data["body"] = safe_body
        
        self.logger.info(f"Incoming request: {log_data}")
    
    def log_response(self, status_code: int, path: str, duration_ms: float, 
                    response_size: int = None, error: str = None) -> None:
        """Log HTTP response.
        
        Args:
            status_code: HTTP status code
            path: Request path
            duration_ms: Request duration in milliseconds
            response_size: Response size in bytes (optional)
            error: Error message if request failed (optional)
        """
        log_data = {
            "type": "response",
            "status_code": status_code,
            "path": path,
            "duration_ms": round(duration_ms, 2),
            "response_size": response_size
        }
        
        if error:
            log_data["error"] = error
        
        if status_code >= 400:
            self.logger.warning(f"Request failed: {log_data}")
        else:
            self.logger.info(f"Request completed: {log_data}")


class ModelLogger:
    """Logger for model operations and inference."""
    
    def __init__(self, logger_name: str = "inference_platform.models"):
        """Initialize model logger.
        
        Args:
            logger_name: Name for the model logger
        """
        self.logger = get_logger(logger_name)
    
    def log_inference_start(self, model_key: str, model_type: str, 
                          request_id: str = None, input_tokens: int = None) -> None:
        """Log start of model inference.
        
        Args:
            model_key: Model identifier
            model_type: Type of model (emd, bedrock)
            request_id: Unique request identifier (optional)
            input_tokens: Number of input tokens (optional)
        """
        log_data = {
            "event": "inference_start",
            "model_key": model_key,
            "model_type": model_type,
            "request_id": request_id,
            "input_tokens": input_tokens
        }
        
        self.logger.info(f"Starting inference: {log_data}")
    
    def log_inference_complete(self, model_key: str, request_id: str = None,
                             duration_ms: float = None, output_tokens: int = None,
                             success: bool = True, error: str = None) -> None:
        """Log completion of model inference.
        
        Args:
            model_key: Model identifier
            request_id: Unique request identifier (optional)
            duration_ms: Inference duration in milliseconds (optional)
            output_tokens: Number of output tokens (optional)
            success: Whether inference succeeded
            error: Error message if failed (optional)
        """
        log_data = {
            "event": "inference_complete",
            "model_key": model_key,
            "request_id": request_id,
            "duration_ms": round(duration_ms, 2) if duration_ms else None,
            "output_tokens": output_tokens,
            "success": success
        }
        
        if error:
            log_data["error"] = error
        
        if success:
            self.logger.info(f"Inference completed: {log_data}")
        else:
            self.logger.error(f"Inference failed: {log_data}")
    
    def log_deployment_event(self, model_key: str, event: str, 
                           details: dict = None) -> None:
        """Log model deployment events.
        
        Args:
            model_key: Model identifier
            event: Event type (start, progress, complete, failed)
            details: Additional event details (optional)
        """
        log_data = {
            "event": f"deployment_{event}",
            "model_key": model_key
        }
        
        if details:
            log_data.update(details)
        
        if event == "failed":
            self.logger.error(f"Deployment event: {log_data}")
        else:
            self.logger.info(f"Deployment event: {log_data}")