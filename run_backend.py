#!/usr/bin/env python3
"""Entry point for the modular backend system."""

import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root
sys.path.insert(0, str(src_path))

from backend.app import create_app
from backend.config import get_environment

def main():
    """Main entry point."""
    environment = get_environment()
    app = create_app(environment)
    
    # Get configuration
    from backend.config import get_config
    config = get_config()
    
    host = config.get('server.host', '0.0.0.0')
    port = config.get('server.port', 5000)
    debug = config.get('server.debug', False)
    
    print(f"🚀 Starting Inference Platform ({environment} mode)")
    print(f"📡 Server: http://{host}:{port}")
    
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main()
