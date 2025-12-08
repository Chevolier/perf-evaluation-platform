"""API routes for the inference platform."""

from fastapi import FastAPI
from .model_routes import model_router
from .inference_routes import inference_router
from .stress_test_routes import stress_test_router
from .results_routes import results_router
from .launch_routes import launch_router
from .hyperpod_routes import hyperpod_router


def register_routers(app: FastAPI) -> None:
    """Register all API routers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Register model management routes
    app.include_router(model_router)

    # Register inference routes
    app.include_router(inference_router)

    # Register stress test routes
    app.include_router(stress_test_router)

    # Register results routes
    app.include_router(results_router)

    # Register launch management routes
    app.include_router(launch_router)

    # Register HyperPod routes
    app.include_router(hyperpod_router)


__all__ = ['register_routers']
