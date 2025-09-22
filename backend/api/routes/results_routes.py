"""Results API routes for visualization."""

import os
import json
import glob
import csv
from pathlib import Path
from flask import Blueprint, jsonify, request
from datetime import datetime
from ...utils import get_logger

logger = get_logger(__name__)

results_bp = Blueprint('results', __name__)

@results_bp.route('/api/results/structure', methods=['GET'])
def get_results_structure():
    """Get the hierarchical structure of all available benchmark results.

    Structure: model/deployment_method_instance_framework_tp_size_dataset/prefix_input_tokens_output_tokens
    """
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        outputs_dir = project_root / 'outputs'
        
        logger.info(f"Scanning outputs directory: {outputs_dir}")
        
        if not outputs_dir.exists():
            logger.warning(f"Outputs directory does not exist: {outputs_dir}")
            return jsonify({"structure": []})
        
        # Build hierarchical structure
        hierarchy = {}
        total_sessions = 0
        
        # Scan each model directory
        for model_dir in outputs_dir.iterdir():
            if not model_dir.is_dir():
                continue
                
            model_name = model_dir.name
            
            # Scan each session directory within the model
            for session_dir in model_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                    
                session_id = session_dir.name
                
                # Look for config files to get session metadata (prefer new format)
                config_path = session_dir / 'config.json'
                if not config_path.exists():
                    config_path = session_dir / 'eval_config.json'
                    if not config_path.exists():
                        logger.debug(f"No config files found in {session_dir}")
                        continue
                
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # Check if we have performance metrics CSV file
                    performance_csv = session_dir / 'performance_metrics.csv'
                    if not performance_csv.exists():
                        logger.debug(f"No performance_metrics.csv found in {session_dir}")
                        continue
                    
                    # Extract hierarchy information
                    deployment_config = config.get('deployment_config', {})
                    stress_config = config.get('stress_test_config', {})
                    
                    deployment_method = deployment_config.get('deployment_method', 'emd').lower()
                    instance_type = deployment_config.get('instance_type', 'unknown')
                    framework = deployment_config.get('framework', 'unknown')
                    tp_size = deployment_config.get('tp_size', 1)
                    dataset = stress_config.get('dataset', 'unknown')
                    
                    # Create prefix/input/output tokens description
                    input_tokens = stress_config.get('input_tokens', {})
                    output_tokens = stress_config.get('output_tokens', {})
                    prefix_length = stress_config.get('prefix_length', 0)

                    # Include prefix in the tokens description
                    tokens_desc = f"prefix:{prefix_length}_input:{input_tokens.get('min', 0)}-{input_tokens.get('max', 0)}_output:{output_tokens.get('min', 0)}-{output_tokens.get('max', 0)}"
                    
                    # Build flatter hierarchy: model -> deployment_method_instance_framework_tp_size_dataset -> tokens
                    instance_framework_dataset = f"{deployment_method}_{instance_type}_{framework}_tp{tp_size}_{dataset}"
                    
                    if model_name not in hierarchy:
                        hierarchy[model_name] = {}
                    if instance_framework_dataset not in hierarchy[model_name]:
                        hierarchy[model_name][instance_framework_dataset] = {}
                    if tokens_desc not in hierarchy[model_name][instance_framework_dataset]:
                        hierarchy[model_name][instance_framework_dataset][tokens_desc] = []
                    
                    # Add session to the deepest level
                    hierarchy[model_name][instance_framework_dataset][tokens_desc].append({
                        "key": f"{model_name}_{deployment_method}_{instance_type}_{framework}_tp{tp_size}_{dataset}_{tokens_desc}_{session_id}",
                        "session_id": session_id,
                        "model": model_name,
                        "deployment_method": deployment_method,
                        "instance_type": instance_type,
                        "framework": framework,
                        "tp_size": tp_size,
                        "dataset": dataset,
                        "tokens_desc": tokens_desc,
                        "prefix_length": prefix_length,
                        "timestamp": config.get('timestamp', ''),
                        "config": config,
                        "path": str(session_dir),
                        "concurrency": stress_config.get('concurrency', 'N/A'),
                        "total_requests": stress_config.get('total_requests', 'N/A')
                    })
                    total_sessions += 1
                    
                except Exception as e:
                    logger.error(f"Error reading config from {config_path}: {e}")
                    continue
        
        # Convert hierarchy to tree structure for frontend
        def build_tree(hierarchy_dict, level=0, path_prefix=""):
            tree = []
            for key, value in sorted(hierarchy_dict.items()):
                # Create unique key by including the full path
                unique_key = f"{path_prefix}/{key}" if path_prefix else key
                
                if isinstance(value, dict):
                    # Check if this contains sessions directly (deepest level)
                    has_direct_sessions = any(isinstance(v, list) for v in value.values())
                    
                    if has_direct_sessions:
                        # This is the dataset level, need to add tokens level below it
                        tokens_children = []
                        for tokens_key, sessions_list in value.items():
                            if isinstance(sessions_list, list) and sessions_list:
                                # Sort sessions by timestamp (newest first)
                                sessions_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                                tokens_children.append({
                                    "key": f"{unique_key}_{tokens_key}",
                                    "title": tokens_key,
                                    "level": level + 1,
                                    "sessions": sessions_list,
                                    "isLeaf": True
                                })
                        
                        if tokens_children:
                            tree.append({
                                "key": unique_key,
                                "title": key,
                                "level": level,
                                "children": tokens_children,
                                "isLeaf": False
                            })
                    else:
                        # This is a parent node, recurse deeper
                        children = build_tree(value, level + 1, unique_key)
                        if children:  # Only include if has valid children
                            tree.append({
                                "key": unique_key,
                                "title": key,
                                "level": level,
                                "children": children,
                                "isLeaf": False
                            })
            return tree
        
        structure = build_tree(hierarchy)
        
        logger.info(f"Found hierarchical structure with {len(structure)} top-level items and {total_sessions} total sessions")
        
        return jsonify({
            "structure": structure,
            "total_models": len(hierarchy),
            "total_sessions": total_sessions,
            "hierarchy_levels": ["model", "deployment_method_instance_framework_tp_size_dataset", "prefix_input_output_tokens"]
        })
        
    except Exception as e:
        logger.error(f"Error fetching results structure: {e}")
        return jsonify({"error": f"Failed to fetch results structure: {str(e)}"}), 500


@results_bp.route('/api/results/data', methods=['POST'])
def get_result_data():
    """Get detailed data for a specific result."""
    try:
        data = request.get_json()
        result_path = data.get('result_path')
        
        if not result_path:
            return jsonify({"error": "result_path is required"}), 400
        
        session_dir = Path(result_path)
        if not session_dir.exists():
            return jsonify({"error": f"Result path does not exist: {result_path}"}), 404
        
        logger.info(f"Fetching data for result: {result_path}")
        
        # Check for performance metrics CSV
        performance_csv = session_dir / 'performance_metrics.csv'
        config_file = session_dir / 'config.json'
        
        if not performance_csv.exists():
            return jsonify({"error": "No performance_metrics.csv found"}), 404
            
        if not config_file.exists():
            return jsonify({"error": "No config.json found"}), 404
        
        try:
            # Read config file
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Read CSV performance data
            performance_data = []
            with open(performance_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert string values to floats where applicable
                    processed_row = {}
                    for key, value in row.items():
                        try:
                            processed_row[key] = float(value)
                        except (ValueError, TypeError):
                            processed_row[key] = value
                    performance_data.append(processed_row)
            
            # Load benchmark summary data for each concurrency level to get inter-token latency
            benchmark_summaries = {}

            # Look for benchmark_summary.json files in parallel_*_number_* subdirectories
            # The structure can be:
            # session_dir/parallel_*/benchmark_summary.json
            # session_dir/model/parallel_*/benchmark_summary.json
            # session_dir/timestamp/model/parallel_*/benchmark_summary.json

            def find_parallel_dirs(directory):
                """Recursively find parallel_* directories containing benchmark_summary.json"""
                parallel_dirs = []
                try:
                    for item in directory.iterdir():
                        if item.is_dir():
                            if item.name.startswith('parallel_'):
                                benchmark_file = item / 'benchmark_summary.json'
                                if benchmark_file.exists():
                                    parallel_dirs.append(benchmark_file)
                            else:
                                # Recursively search subdirectories (max 3 levels deep to avoid infinite loops)
                                parallel_dirs.extend(find_parallel_dirs(item))
                except Exception as e:
                    logger.debug(f"Could not search directory {directory}: {e}")
                return parallel_dirs

            # Find all benchmark_summary.json files
            benchmark_files = find_parallel_dirs(session_dir)
            logger.info(f"Found {len(benchmark_files)} benchmark_summary.json files")

            for benchmark_summary_file in benchmark_files:
                try:
                    with open(benchmark_summary_file, 'r', encoding='utf-8') as f:
                        benchmark_data = json.load(f)
                        concurrency = benchmark_data.get('Number of concurrency', 0)
                        benchmark_summaries[concurrency] = benchmark_data
                        logger.info(f"Loaded benchmark summary for concurrency {concurrency} from {benchmark_summary_file}")
                except Exception as e:
                    logger.warning(f"Failed to load benchmark summary from {benchmark_summary_file}: {e}")

            # Enrich performance data with inter-token latency from benchmark summaries
            logger.info(f"Found {len(benchmark_summaries)} benchmark summaries: {list(benchmark_summaries.keys())}")
            for row in performance_data:
                concurrency = int(row.get('Concurrency', 0))
                if concurrency in benchmark_summaries:
                    # Add inter-token latency from benchmark summary
                    itl_value = benchmark_summaries[concurrency].get('Average inter-token latency (s)', row.get('Avg_TPOT_s', 0))
                    tpot_value = row.get('Avg_TPOT_s', 0)
                    row['Avg_ITL_s'] = itl_value
                    logger.info(f"Enhanced concurrency {concurrency}: TPOT={tpot_value}, ITL={itl_value}")
                else:
                    # Fallback to TPOT if no benchmark summary available
                    fallback_value = row.get('Avg_TPOT_s', 0)
                    row['Avg_ITL_s'] = fallback_value
                    logger.info(f"Fallback for concurrency {concurrency}: using TPOT={fallback_value} as ITL")

            # Prepare summary data in the format expected by frontend
            summary_data = {}
            percentile_data = []

            for row in performance_data:
                concurrency = row.get('Concurrency', 0)

                # Add each row as a summary point
                summary_data[f"concurrency_{int(concurrency)}"] = {
                    'Request throughput (req/s)': row.get('RPS_req_s', 0),
                    'Output token throughput (tok/s)': row.get('Gen_Throughput_tok_s', 0),
                    'Total token throughput (tok/s)': row.get('Total_Throughput_tok_s', 0),
                    'Average latency (s)': row.get('Avg_Latency_s', 0),
                    'Average time to first token (s)': row.get('Avg_TTFT_s', 0),
                    'Average time per output token (s)': row.get('Avg_TPOT_s', 0),
                    'Average inter-token latency (s)': row.get('Avg_ITL_s', row.get('Avg_TPOT_s', 0)),
                    'concurrency': concurrency
                }
                
                # Create percentile data (using P99 values as example percentiles)
                percentile_data.append({
                    'Percentiles': 99,
                    'Latency (s)': row.get('P99_Latency_s', 0),
                    'TTFT (s)': row.get('P99_TTFT_s', 0),
                    'TPOT (s)': row.get('P99_TPOT_s', 0),
                    'concurrency': concurrency
                })
            
            logger.info(f"Successfully processed performance data with {len(performance_data)} rows")
            
        except Exception as e:
            logger.error(f"Error reading performance data: {e}")
            return jsonify({"error": f"Failed to read performance data: {str(e)}"}), 500
        
        return jsonify({
            "summary": summary_data,
            "percentiles": percentile_data,
            "config": config,
            "performance_data": performance_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching result data: {e}")
        return jsonify({"error": f"Failed to fetch result data: {str(e)}"}), 500


@results_bp.route('/api/results/stats', methods=['GET'])
def get_results_stats():
    """Get overall statistics about available results."""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        outputs_dir = project_root / 'outputs'
        
        if not outputs_dir.exists():
            return jsonify({
                "total_models": 0,
                "total_sessions": 0,
                "total_results": 0,
                "models": []
            })
        
        stats = {
            "total_models": 0,
            "total_sessions": 0,
            "total_results": 0,
            "models": []
        }
        
        for model_dir in outputs_dir.iterdir():
            if not model_dir.is_dir():
                continue
                
            model_name = model_dir.name
            session_count = 0
            result_count = 0
            
            for session_dir in model_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                    
                # Check if session has valid config (prefer new format)
                config_path = session_dir / 'config.json'
                if not config_path.exists():
                    config_path = session_dir / 'eval_config.json'
                
                if config_path.exists():
                    session_count += 1
                    
                    # Check if has performance metrics CSV
                    if (session_dir / 'performance_metrics.csv').exists():
                        result_count += 1
            
            if session_count > 0:
                stats["models"].append({
                    "name": model_name,
                    "sessions": session_count,
                    "results": result_count
                })
                stats["total_sessions"] += session_count
                stats["total_results"] += result_count
        
        stats["total_models"] = len(stats["models"])
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error fetching results stats: {e}")
        return jsonify({"error": f"Failed to fetch results stats: {str(e)}"}), 500