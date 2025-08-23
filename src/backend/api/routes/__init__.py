"""API routes for the inference platform."""

from flask import Flask
from .model_routes import model_bp

def register_blueprints(app: Flask) -> None:
    """Register all API blueprints with the Flask app.
    
    Args:
        app: Flask application instance
    """
    # Register model management routes
    app.register_blueprint(model_bp, url_prefix='/api')
    
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