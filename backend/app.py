"""Flask application factory."""

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
    
    # Setup logging (skip if already configured)
    import logging
    if not logging.getLogger().handlers:
        setup_logging(
            log_level=config.get('logging.level', 'INFO'),
            log_file=config.get('logging.file')
        )
    
    # Configure CORS
    CORS(app, 
         origins=config.get('cors.origins', []),
         methods=config.get('cors.methods', ['GET', 'POST']),
         allow_headers=config.get('cors.allow_headers', ['Content-Type']))
    
    # Register API blueprints
    register_blueprints(app)
    
    return app
