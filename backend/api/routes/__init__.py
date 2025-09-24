"""API routes for the inference platform."""

from flask import Flask
from .model_routes import model_bp
from .inference_routes import inference_bp
from .stress_test_routes import stress_test_bp
from .results_routes import results_bp
from .hyperpod_routes import hyperpod_bp

def register_blueprints(app: Flask) -> None:
    """Register all API blueprints with the Flask app.
    
    Args:
        app: Flask application instance
    """
    # Register model management routes
    app.register_blueprint(model_bp, url_prefix='/api')
    
    # Register inference routes
    app.register_blueprint(inference_bp, url_prefix='/api')

    # Register stress test routes
    app.register_blueprint(stress_test_bp, url_prefix='/api')

    # Register results routes
    app.register_blueprint(results_bp)

    # Register HyperPod orchestration routes
    app.register_blueprint(hyperpod_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {"status": "healthy", "service": "inference-platform"}
    
    # Debug logging endpoint
    @app.route('/debug/logging')
    def debug_logging():
        import logging
        root_logger = logging.getLogger()
        
        # Test direct logging
        root_logger.info("🧪 DIRECT ROOT LOGGER TEST FROM ENDPOINT")
        
        # Test named logger
        from ...utils import get_logger
        test_logger = get_logger("debug_endpoint")
        test_logger.warning("🧪 NAMED LOGGER TEST FROM ENDPOINT")
        
        # Force flush all handlers
        for handler in root_logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        handlers_info = []
        for i, handler in enumerate(root_logger.handlers):
            handler_info = {
                "index": i,
                "type": type(handler).__name__,
                "level": handler.level,
                "formatter": str(handler.formatter) if handler.formatter else None
            }
            if hasattr(handler, 'baseFilename'):
                handler_info["file"] = handler.baseFilename
            handlers_info.append(handler_info)
        
        return {
            "root_logger_level": root_logger.level,
            "handlers_count": len(root_logger.handlers),
            "handlers": handlers_info,
            "test_message": "Check logs/development.log for test messages"
        }
    
    # Root endpoint
    @app.route('/')
    def root():
        return {
            "message": "Inference Platform API",
            "version": "2.0.0",
            "status": "running"
        }

__all__ = ['register_blueprints']
