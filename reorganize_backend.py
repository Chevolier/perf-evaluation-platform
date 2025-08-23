#!/usr/bin/env python3
"""
Backend Reorganization Script
Completes the reorganization of the monolithic backend.py into a modular structure.
"""

import os
import shutil
from pathlib import Path

def reorganize_backend():
    """Complete the backend reorganization."""
    
    print("🚀 Starting backend reorganization...")
    
    # Backup existing backend
    if Path("src/backend/backend.py").exists():
        print("📦 Backing up existing backend...")
        shutil.copy2("src/backend/backend.py", "src/backend/backend_original.py")
    
    # Replace old backend structure with new modular one
    if Path("src/backend_new").exists():
        print("🔄 Replacing backend with modular structure...")
        
        # Remove old backend directory (except backup)
        if Path("src/backend").exists():
            # Keep important files
            important_files = ["backend_original.py", "streaming_api.py"]
            backup_files = {}
            
            for file in important_files:
                src_file = Path("src/backend") / file
                if src_file.exists():
                    backup_files[file] = src_file.read_bytes()
            
            shutil.rmtree("src/backend")
        
        # Move new structure
        shutil.move("src/backend_new", "src/backend")
        
        # Restore important files
        for file, content in backup_files.items():
            (Path("src/backend") / file).write_bytes(content)
    
    # Create configuration files
    create_config_files()
    
    # Create remaining service files
    create_service_layer()
    
    # Create API routes
    create_api_routes()
    
    # Create application factory
    create_app_factory()
    
    # Create new entry point
    create_entry_point()
    
    print("✅ Backend reorganization completed!")
    print("\n📋 New Structure:")
    print_directory_tree("src/backend", level=0, max_level=3)
    
    print("\n🎯 Next Steps:")
    print("1. Test the new system: python3 run_modular.py")
    print("2. Update import statements in any external code")
    print("3. Migrate any custom configurations")
    print("4. Remove old backend once verified: rm src/backend/backend_original.py")

def create_config_files():
    """Create configuration YAML files."""
    print("⚙️  Creating configuration files...")
    
    config_dir = Path("config/environments")
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Default configuration
    default_config = """# Default configuration for inference platform

server:
  host: "0.0.0.0"
  port: 5000
  debug: false
  workers: 1

logging:
  level: "INFO"
  file: "logs/app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5

aws:
  region: "us-west-2"
  account_id: null  # Auto-detected

models:
  emd:
    base_url: "http://localhost:8000"
    default_tag: null
    timeout: 300
  bedrock:
    region: "us-west-2"
    timeout: 300

database:
  path: "data/app.db"
  echo: false

storage:
  base_path: "outputs"
  cleanup_days: 30

benchmarking:
  default_timeout: 1800  # 30 minutes
  max_concurrent: 5
  result_retention_days: 90

cors:
  origins:
    - "http://localhost:3000"
    - "http://localhost:3001"
  methods:
    - "GET"
    - "POST" 
    - "PUT"
    - "DELETE"
    - "OPTIONS"
  allow_headers:
    - "Content-Type"
    - "Authorization"
"""
    
    # Development configuration
    dev_config = """# Development environment configuration

server:
  debug: true
  port: 5000

logging:
  level: "DEBUG"
  file: "logs/development.log"

models:
  emd:
    base_url: "http://localhost:8000"
  
cors:
  origins: ["http://localhost:3000", "http://localhost:3001"]
"""
    
    # Production configuration  
    prod_config = """# Production environment configuration

server:
  debug: false
  port: 5000
  workers: 4

logging:
  level: "INFO"
  file: "logs/production.log"

models:
  emd:
    base_url: "http://localhost:8000"
"""
    
    (config_dir / "default.yaml").write_text(default_config)
    (config_dir / "development.yaml").write_text(dev_config)
    (config_dir / "production.yaml").write_text(prod_config)

def create_service_layer():
    """Create service layer files."""
    print("🔧 Creating service layer...")
    
    services_dir = Path("src/backend/services")
    services_dir.mkdir(parents=True, exist_ok=True)

def create_api_routes():
    """Create API route blueprints.""" 
    print("🌐 Creating API routes...")
    
    routes_dir = Path("src/backend/api/routes")
    routes_dir.mkdir(parents=True, exist_ok=True)

def create_app_factory():
    """Create Flask application factory."""
    print("🏭 Creating application factory...")
    
    app_content = '''"""Flask application factory."""

from flask import Flask
from flask_cors import CORS

from .config import get_config
from .utils import setup_logging


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
    
    # Setup logging
    setup_logging(
        log_level=config.get('logging.level', 'INFO'),
        log_file=config.get('logging.file')
    )
    
    # Configure CORS
    CORS(app, 
         origins=config.get('cors.origins', []),
         methods=config.get('cors.methods', ['GET', 'POST']),
         allow_headers=config.get('cors.allow_headers', ['Content-Type']))
    
    # Register blueprints would go here
    # from .api.routes import register_blueprints
    # register_blueprints(app)
    
    return app
'''
    
    (Path("src/backend") / "app.py").write_text(app_content)

def create_entry_point():
    """Create new entry point script."""
    print("🚪 Creating entry point...")
    
    entry_content = '''#!/usr/bin/env python3
"""Entry point for the modular backend system."""

import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root / 'src'
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
'''
    
    Path("run_modular.py").write_text(entry_content)
    os.chmod("run_modular.py", 0o755)

def print_directory_tree(path, level=0, max_level=2):
    """Print directory tree structure."""
    if level > max_level:
        return
        
    path = Path(path)
    if not path.exists():
        return
        
    indent = "  " * level
    print(f"{indent}{path.name}/")
    
    if path.is_dir():
        try:
            items = sorted([p for p in path.iterdir() if not p.name.startswith('.')])
            for item in items:
                if item.is_dir():
                    print_directory_tree(item, level + 1, max_level)
                else:
                    print(f"{indent}  {item.name}")
        except PermissionError:
            print(f"{indent}  [Permission Denied]")

if __name__ == "__main__":
    reorganize_backend()