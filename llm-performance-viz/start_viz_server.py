#!/usr/bin/env python3
"""
Startup script for the LLM Performance Visualization Server.

This script provides a convenient way to start the visualization server with
customizable configuration options including analytics data storage paths.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn

def main():
    parser = argparse.ArgumentParser(
        description="LLM Performance Visualization Server",
        epilog="""
Examples:
  %(prog)s                                    # Start with default settings
  %(prog)s -p 9000 -r ./results             # Custom port and results directory
  %(prog)s -a ./data/analytics.json         # Custom analytics data file
  %(prog)s --analytics-log ./logs/access.log # Custom analytics log file
  %(prog)s --root-path /viz                  # Deploy under subdomain
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", "-p", type=int, default=8000, 
                       help="Port to run the server on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                       help="Host to bind the server to (default: 0.0.0.0)")
    parser.add_argument("--root-path", type=str, default="",
                       help="Root path for deployment under a subdomain (e.g., /viz)")
    parser.add_argument("--results-dir", "-r", type=str, default="archive_results",
                       help="Directory containing test results (default: archive_results)")
    parser.add_argument("--analytics-file", "-a", type=str, default="user_analytics.json",
                       help="Path to analytics data file (default: user_analytics.json)")
    parser.add_argument("--analytics-log", type=str, default="viz_access.log",
                       help="Path to analytics log file (default: viz_access.log)")
    
    args = parser.parse_args()
    
    # Validate and create directories if needed
    results_path = Path(args.results_dir)
    if not results_path.exists():
        print(f"Warning: Results directory '{args.results_dir}' does not exist.")
        print("The server will start but no test data will be available until results are added.")
    
    # Create analytics file directory if it doesn't exist
    analytics_file_path = Path(args.analytics_file)
    analytics_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create analytics log directory if it doesn't exist
    analytics_log_path = Path(args.analytics_log)
    analytics_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables so the FastAPI app can use them
    if args.root_path:
        os.environ['ROOT_PATH'] = args.root_path.rstrip('/')
    
    os.environ['RESULTS_DIR'] = args.results_dir
    os.environ['ANALYTICS_FILE'] = str(analytics_file_path)
    os.environ['ANALYTICS_LOG'] = str(analytics_log_path)
    
    # Import app after setting environment variables
    from llm_test_tool.viz_server import app
    
    print(f"Starting LLM Performance Visualization Server...")
    print(f"Results directory: {args.results_dir}")
    print(f"Analytics data file: {args.analytics_file}")
    print(f"Analytics log file: {args.analytics_log}")
    if args.root_path:
        print(f"Root path: {args.root_path}")
        print(f"Access the visualization at: http://localhost:{args.port}{args.root_path}")
    else:
        print(f"Access the visualization at: http://localhost:{args.port}")
    print(f"Analytics dashboard: http://localhost:{args.port}{args.root_path}/analytics")
    
    uvicorn.run(app, host=args.host, port=args.port, root_path=args.root_path)

if __name__ == "__main__":
    main()