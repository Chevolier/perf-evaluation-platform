"""FastAPI application."""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add backend directory to path for imports
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from config import get_config, get_environment
from utils import setup_logging, get_logger
from api.routes import register_routers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Application starting up...")
    yield
    # Shutdown
    logger.info("🛑 Application shutting down...")


def create_app(environment: str = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        environment: Environment name (development, production, etc.)

    Returns:
        Configured FastAPI application
    """
    # Load configuration
    config = get_config()
    config.load_config(environment)

    # Setup logging
    log_file = config.get('logging.file')
    setup_logging(
        log_level=config.get('logging.level', 'INFO'),
        log_file=log_file
    )

    app_logger = logging.getLogger('backend.app')
    app_logger.info(f"🚀 FastAPI application created in {environment or 'default'} mode")
    app_logger.debug(f"🔧 Debug logging is {'enabled' if config.get('logging.level') == 'DEBUG' else 'disabled'}")

    # Create FastAPI app
    app = FastAPI(
        title="Inference Platform API",
        version="2.0.0",
        description="Performance Evaluation Platform for LLM Inference",
        lifespan=lifespan
    )

    # Configure CORS
    cors_origins = config.get('cors.origins', ['*'])
    cors_methods = config.get('cors.methods', ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    cors_headers = config.get('cors.allow_headers', ['*'])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=cors_methods,
        allow_headers=cors_headers,
    )

    # Register API routers
    register_routers(app)

    # Health check endpoint
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "inference-platform"}

    # Debug logging endpoint
    @app.get("/debug/logging")
    def debug_logging():
        root_logger = logging.getLogger()

        root_logger.info("🧪 DIRECT ROOT LOGGER TEST FROM ENDPOINT")

        test_logger = get_logger("debug_endpoint")
        test_logger.warning("🧪 NAMED LOGGER TEST FROM ENDPOINT")

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
    @app.get("/")
    def root():
        return {
            "message": "Inference Platform API",
            "version": "2.0.0",
            "status": "running"
        }

    return app


# Get environment and create app for uvicorn
environment = get_environment()
app = create_app(environment)


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    host = config.get('server.host', '0.0.0.0')
    port = config.get('server.port', 5000)
    debug = config.get('server.debug', False)

    print(f"🚀 Starting Inference Platform ({environment} mode)")
    print(f"📡 Server: http://{host}:{port}")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
