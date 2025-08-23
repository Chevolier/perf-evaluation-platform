"""
Standalone deployment module for vLLM/SGLang servers without benchmarking.
"""

import argparse
import sys
import os
from pathlib import Path

from .deployment import VllmDeployment


def parse_arguments():
    """Parse command line arguments for deployment only"""
    parser = argparse.ArgumentParser(
        description="Deploy vLLM/SGLang servers without running benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy a server
  python -m llm_test_tool deploy --config model_configs/vllm-v0.9.2/g6e.4xlarge/Qwen3-30B-A3B-FP8.yaml
  
  # Deploy and show the generated Docker command
  python -m llm_test_tool deploy --config config.yaml --show-command
  
  # Deploy without waiting for health check
  python -m llm_test_tool deploy --config config.yaml --no-health-check
  
  # Stop a running deployment
  python -m llm_test_tool deploy --config config.yaml --stop
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML or JSON configuration file"
    )
    
    parser.add_argument(
        "--show-command",
        action="store_true",
        help="Show the generated Docker command without executing it"
    )
    
    parser.add_argument(
        "--no-health-check",
        action="store_true",
        help="Skip health check after deployment"
    )
    
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop and remove the deployment instead of starting it"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check the status of the deployment"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser.parse_args()


def show_docker_command(deployment: VllmDeployment):
    """Show the Docker command that would be executed"""
    cmd = deployment.build_docker_command()
    
    print("Generated Docker command:")
    print("=" * 50)
    
    # Format command for better readability
    formatted_cmd = []
    for i, part in enumerate(cmd):
        if i == 0:
            formatted_cmd.append(part)
        elif part.startswith('-'):
            formatted_cmd.append(f" \\\n  {part}")
        else:
            formatted_cmd.append(f" {part}")
    
    print(''.join(formatted_cmd))
    print("\n" + "=" * 50)


def check_deployment_status(deployment: VllmDeployment):
    """Check and display deployment status"""
    print(f"Checking status for container: {deployment.container_name}")
    
    if deployment.is_container_running():
        print("✓ Container is running")
        
        # Try to check health endpoint
        try:
            import requests
            health_url = deployment.get_api_url().replace('/v1/chat/completions', '/health')
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                print("✓ Server is healthy and responding")
                print(f"  API endpoint: {deployment.get_api_url()}")
                print(f"  Model: {deployment.get_model_id()}")
            else:
                print(f"⚠ Server is not healthy (HTTP {response.status_code})")
        except Exception as e:
            print(f"⚠ Could not check server health: {e}")
    else:
        print("✗ Container is not running")


def main():
    """Main entry point for deployment-only command"""
    args = parse_arguments()
    
    # Validate config file exists
    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found: {args.config}")
        sys.exit(1)
    
    try:
        deployment = VllmDeployment(args.config)
        
        if args.verbose:
            print(f"Configuration file: {args.config}")
            print(f"Docker image: {deployment.deployment_config['docker_image']}")
            print(f"Container name: {deployment.container_name}")
            print(f"Port: {deployment.port}")
            print(f"Model: {deployment.get_model_id()}")
            print("-" * 50)
        
        if args.show_command:
            show_docker_command(deployment)
            return
        
        if args.status:
            check_deployment_status(deployment)
            return
        
        if args.stop:
            print(f"Stopping deployment: {deployment.container_name}")
            if deployment.cleanup():
                print("✓ Deployment stopped successfully")
            else:
                print("✗ Failed to stop deployment")
                sys.exit(1)
            return
        
        # Default action: deploy
        print(f"Deploying server: {deployment.container_name}")
        print(f"Model: {deployment.get_model_id()}")
        print(f"Port: {deployment.port}")
        
        if not deployment.start_container():
            print("✗ Failed to start container")
            sys.exit(1)
        
        if not args.no_health_check:
            print("\nWaiting for server to become healthy...")
            if deployment.wait_for_health():
                print("✓ Deployment successful!")
                print(f"  API endpoint: {deployment.get_api_url()}")
                print(f"  Container name: {deployment.container_name}")
                print("\nTo stop the deployment, run:")
                print(f"  python -m llm_test_tool deploy --config {args.config} --stop")
            else:
                print("✗ Server failed to become healthy")
                print("Container is running but not responding to health checks")
                sys.exit(1)
        else:
            print("✓ Container started successfully!")
            print("  (Skipped health check)")
            print(f"  API endpoint: {deployment.get_api_url()}")
    
    except KeyboardInterrupt:
        print("\nDeployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during deployment: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()