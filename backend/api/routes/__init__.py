"""API routes for the inference platform."""

from flask import Flask
from .model_routes import model_bp
from .inference_routes import inference_bp
from .stress_test_routes import stress_test_bp
from .results_routes import results_bp

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
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {"status": "healthy", "service": "inference-platform"}
    
    # Root endpoint
    @app.route('/')
    def root():
        return {
            "message": "Inference Platform API",
            "version": "2.0.0",
            "status": "running"
        }

__all__ = ['register_blueprints']