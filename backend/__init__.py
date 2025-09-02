"""Inference Platform Backend - Modular Architecture."""

from .app import create_app
from .config import get_config, init_config

__version__ = "2.0.0"
__all__ = ['create_app', 'get_config', 'init_config']