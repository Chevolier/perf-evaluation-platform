"""Flask application factory."""

import os
from flask import Flask
from flask_cors import CORS

from .config import get_config
from .utils import setup_logging
from .api import register_blueprints


def create_app(environment=None):
    """Create and configure Flask application.
    
    Args:
        environment: Environment name (development, production, etc.)
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    config.load_config(environment)
    
    # Setup logging - ensure it's configured properly for Flask
    import logging
    
    # Always ensure logging is properly configured, even if handlers exist
    # This handles cases where Flask might have modified the logging configuration
    root_logger = logging.getLogger()
    log_file = config.get('logging.file')
    
    # Check if we have the correct file handler
    has_correct_file_handler = False
    if log_file:
        abs_log_file = os.path.abspath(log_file)
        for handler in root_logger.handlers:
            if (isinstance(handler, logging.FileHandler) and 
                hasattr(handler, 'baseFilename') and 
                handler.baseFilename == abs_log_file):
                has_correct_file_handler = True
                break
    
    # If we don't have the correct file handler, set up logging
    if not has_correct_file_handler:
        setup_logging(
            log_level=config.get('logging.level', 'INFO'),
            log_file=log_file
        )
    
    # Disable Flask's default request logging to prevent duplicates
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.INFO)  # Keep at INFO level to capture request logs
    
    # Test logging immediately after Flask app creation
    app_logger = logging.getLogger('backend.app')
    app_logger.info(f"🚀 Flask application created in {environment or 'default'} mode")
    app_logger.debug(f"🔧 Debug logging is {'enabled' if config.get('logging.level') == 'DEBUG' else 'disabled'}")
    
    # Configure CORS
    CORS(app, 
         origins=config.get('cors.origins', []),
         methods=config.get('cors.methods', ['GET', 'POST']),
         allow_headers=config.get('cors.allow_headers', ['Content-Type']))
    
    # Register API blueprints
    register_blueprints(app)
    
    # Start launch reconciler if enabled
    try:
        from .services.launch_reconciler import LaunchReconciler
        from .services.launch_service import LaunchService
        
        reconciler_enabled = config.get('launch.reconciler.enabled', True)
        if reconciler_enabled:
            launch_service = LaunchService()
            reconciler = LaunchReconciler(
                launch_service=launch_service,
                interval_seconds=config.get('launch.reconciler.interval_seconds', 30)
            )
            reconciler.start_background_thread()
            
            # Store reconciler reference for cleanup
            app.config['launch_reconciler'] = reconciler
            
            app_logger.info("✅ Launch reconciler started")
        else:
            app_logger.info("⏸️ Launch reconciler disabled")
            
    except Exception as e:
        app_logger.warning(f"Failed to start launch reconciler: {e}")
    
    return app
