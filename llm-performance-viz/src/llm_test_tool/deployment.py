"""
Docker deployment module for vLLM servers.
"""

import json
import yaml
import subprocess
import time
import requests
from typing import Dict, Any
from pathlib import Path


class VllmDeployment:
    """Manages vLLM Docker container deployment and lifecycle"""
    
    def __init__(self, config_path: str):
        """Initialize with deployment configuration"""
        self.config_path = Path(config_path)
        
        # Load config file (support both YAML and JSON)
        with open(self.config_path, 'r') as f:
            if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                self.config = yaml.safe_load(f)
            else:
                self.config = json.load(f)
        
        self.deployment_config = self.config['deployment']
        self.container_name = self.deployment_config['container_name']
        self.port = self.deployment_config['port']
    
    def build_docker_command(self) -> list:
        """Build the docker run command from configuration"""
        cmd = ['docker', 'run']
        
        # Add Docker run parameters
        docker_params = self.deployment_config.get('docker_params', {})
        
        # Handle basic parameters
        if 'gpus' in docker_params:
            cmd.extend(['--gpus', str(docker_params['gpus'])])
        
        # Add port mapping
        cmd.extend(['-p', f"{self.port}:{self.port}"])
        
        # Add container name
        cmd.extend(['--name', self.container_name])
        
        # Add detached mode
        cmd.append('-d')
        
        # Add any additional Docker parameters
        for param, value in docker_params.items():
            if param == 'gpus':
                continue  # Already handled above
            elif param == 'environment':
                # Handle environment variables
                if isinstance(value, dict):
                    for env_key, env_value in value.items():
                        cmd.extend(['-e', f"{env_key}={env_value}"])
                elif isinstance(value, list):
                    for env_var in value:
                        cmd.extend(['-e', env_var])
            elif param == 'ports':
                # Handle additional port mappings
                if isinstance(value, list):
                    for port_mapping in value:
                        cmd.extend(['-p', port_mapping])
                else:
                    cmd.extend(['-p', str(value)])
            else:
                # Handle any other Docker parameter (including volumes)
                param_name = f"--{param}"
                if isinstance(value, bool):
                    if value:
                        cmd.append(param_name)
                elif isinstance(value, list):
                    for item in value:
                        cmd.extend([param_name, str(item)])
                else:
                    cmd.extend([param_name, str(value)])
        
        # Add legacy volume support for backward compatibility
        if 'volumes' in self.deployment_config and 'volumes' not in docker_params:
            for volume in self.deployment_config['volumes']:
                cmd.extend(['-v', volume])
        
        # Add the Docker image
        cmd.append(self.deployment_config['docker_image'])
        
        # Add custom command if specified (e.g., for SGLang)
        custom_command = self.deployment_config.get('command')
        if custom_command:
            if isinstance(custom_command, list):
                cmd.extend(custom_command)
            else:
                # Split command string into parts, handling quoted arguments
                import shlex
                cmd.extend(shlex.split(custom_command))
        
        # Add application arguments
        app_args = self.deployment_config.get('app_args', {})
        
        # Add port argument (only if no custom command or if port not in custom command)
        if not custom_command or '--port' not in str(custom_command):
            cmd.extend(['--port', str(self.port)])
        
        # Add model configuration arguments
        model_config = self.deployment_config.get('model_config', {})
        if 'model' in model_config and (not custom_command or '--model' not in str(custom_command)):
            cmd.extend(['--model', model_config['model']])
        
        # Add any other application arguments
        for arg, value in app_args.items():
            arg_name = f"--{arg}"
            if isinstance(value, bool):
                if value:
                    cmd.append(arg_name)
            elif isinstance(value, list):
                for item in value:
                    cmd.extend([arg_name, str(item)])
            else:
                cmd.extend([arg_name, str(value)])
        
        # Add legacy model config support for backward compatibility
        for key, value in model_config.items():
            if key == 'model':
                continue  # Already handled above
            
            arg_name = f"--{key}"
            if isinstance(value, bool):
                if value:
                    cmd.append(arg_name)
            elif isinstance(value, list):
                for item in value:
                    cmd.extend([arg_name, str(item)])
            else:
                cmd.extend([arg_name, str(value)])
        
        return cmd
    
    def is_container_running(self) -> bool:
        """Check if the container is already running"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', f'name={self.container_name}', '--format', '{{.Names}}'],
                capture_output=True, text=True, check=True
            )
            return self.container_name in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def container_exists(self) -> bool:
        """Check if the container exists (running or stopped)"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '-a', '--filter', f'name={self.container_name}', '--format', '{{.Names}}'],
                capture_output=True, text=True, check=True
            )
            return self.container_name in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def stop_container(self) -> bool:
        """Stop and remove existing container"""
        try:
            # Stop the container
            subprocess.run(['docker', 'stop', self.container_name], 
                         capture_output=True, check=True)
            # Remove the container
            subprocess.run(['docker', 'rm', self.container_name], 
                         capture_output=True, check=True)
            print(f"Stopped and removed container: {self.container_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error stopping container: {e}")
            return False
    
    def start_container(self) -> bool:
        """Start the vLLM container"""
        # Check if container is already running
        if self.is_container_running():
            print(f"Container {self.container_name} is already running. Stopping it first...")
            if not self.stop_container():
                return False
        # Check if container exists but is not running
        elif self.container_exists():
            print(f"Container {self.container_name} exists but is not running. Removing it first...")
            try:
                subprocess.run(['docker', 'rm', self.container_name], 
                             capture_output=True, check=True)
                print(f"Removed stopped container: {self.container_name}")
            except subprocess.CalledProcessError as e:
                print(f"Error removing stopped container: {e}")
                return False
        
        # Build and run the docker command
        cmd = self.build_docker_command()
        print(f"Starting container with command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"Container started successfully: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error starting container: {e}")
            print(f"stderr: {e.stderr}")
            return False
    
    def wait_for_health(self, timeout: int = 1200) -> bool:
        """Wait for the server to become healthy"""
        health_url = f"http://localhost:{self.port}/health"
        print(f"Waiting for server to become healthy at {health_url}...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    print("Server is healthy!")
                    return True
            except requests.RequestException:
                pass
            
            print(".", end="", flush=True)
            time.sleep(5)
        
        print(f"\nServer failed to become healthy within {timeout} seconds")
        return False
    
    def deploy(self) -> bool:
        """Deploy the vLLM server and wait for it to be ready"""
        if not self.start_container():
            return False
        
        return self.wait_for_health()
    
    def cleanup(self) -> bool:
        """Clean up the deployment"""
        return self.stop_container()
    
    def get_api_url(self) -> str:
        """Get the API endpoint URL"""
        return f"http://localhost:{self.port}/v1/chat/completions"
    
    def get_model_id(self) -> str:
        """Get the model ID from configuration"""
        # Try new universal format first
        app_args = self.deployment_config.get('app_args', {})
        if 'model' in app_args:
            return app_args['model']
        elif 'model_path' in app_args:
            return app_args['model_path']
        
        # Fall back to legacy format
        model_config = self.deployment_config.get('model_config', {})
        if 'model' in model_config:
            return model_config['model']
        
        # If no model found, return a default
        return "unknown-model"