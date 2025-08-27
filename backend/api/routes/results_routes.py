"""Results API routes for visualization."""

import os
import json
import glob
from pathlib import Path
from flask import Blueprint, jsonify, request
from datetime import datetime
from ...utils import get_logger

logger = get_logger(__name__)

results_bp = Blueprint('results', __name__)

@results_bp.route('/api/results/structure', methods=['GET'])
def get_results_structure():
    """Get the hierarchical structure of all available benchmark results.
    
    Structure: model/instance/framework/dataset/input_tokens_output_tokens
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
                
                # Look for eval_config.json to get session metadata
                config_path = session_dir / 'eval_config.json'
                if not config_path.exists():
                    logger.debug(f"No eval_config.json found in {session_dir}")
                    continue
                
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # Check if we have benchmark data
                    benchmark_dirs = list(session_dir.glob('*/*/'))  # Look for timestamp/tag directories
                    has_benchmark_data = any(
                        (bd / 'benchmark_summary.json').exists() and 
                        (bd / 'benchmark_percentile.json').exists()
                        for bd in benchmark_dirs
                    )
                    
                    if not has_benchmark_data:
                        logger.debug(f"No benchmark data found in {session_dir}")
                        continue
                    
                    # Extract hierarchy information
                    deployment_config = config.get('deployment_config', {})
                    stress_config = config.get('stress_test_config', {})
                    
                    instance_type = deployment_config.get('instance_type', 'unknown')
                    framework = deployment_config.get('framework', 'unknown')
                    dataset = stress_config.get('dataset', 'unknown')
                    
                    # Create input/output tokens description
                    input_tokens = stress_config.get('input_tokens', {})
                    output_tokens = stress_config.get('output_tokens', {})
                    tokens_desc = f"input:{input_tokens.get('min', 0)}-{input_tokens.get('max', 0)}_output:{output_tokens.get('min', 0)}-{output_tokens.get('max', 0)}"
                    
                    # Build hierarchy: model -> instance -> framework -> dataset -> tokens
                    if model_name not in hierarchy:
                        hierarchy[model_name] = {}
                    if instance_type not in hierarchy[model_name]:
                        hierarchy[model_name][instance_type] = {}
                    if framework not in hierarchy[model_name][instance_type]:
                        hierarchy[model_name][instance_type][framework] = {}
                    if dataset not in hierarchy[model_name][instance_type][framework]:
                        hierarchy[model_name][instance_type][framework][dataset] = {}
                    if tokens_desc not in hierarchy[model_name][instance_type][framework][dataset]:
                        hierarchy[model_name][instance_type][framework][dataset][tokens_desc] = []
                    
                    # Add session to the deepest level
                    hierarchy[model_name][instance_type][framework][dataset][tokens_desc].append({
                        "key": f"{model_name}_{instance_type}_{framework}_{dataset}_{tokens_desc}_{session_id}",
                        "session_id": session_id,
                        "model": model_name,
                        "instance_type": instance_type,
                        "framework": framework,
                        "dataset": dataset,
                        "tokens_desc": tokens_desc,
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
        def build_tree(hierarchy_dict, level=0):
            tree = []
            for key, value in sorted(hierarchy_dict.items()):
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
                                    "key": f"{key}_{tokens_key}",
                                    "title": tokens_key,
                                    "level": level + 1,
                                    "sessions": sessions_list,
                                    "isLeaf": True
                                })
                        
                        if tokens_children:
                            tree.append({
                                "key": key,
                                "title": key,
                                "level": level,
                                "children": tokens_children,
                                "isLeaf": False
                            })
                    else:
                        # This is a parent node, recurse deeper
                        children = build_tree(value, level + 1)
                        if children:  # Only include if has valid children
                            tree.append({
                                "key": key,
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
            "hierarchy_levels": ["model", "instance", "framework", "dataset", "input_output_tokens"]
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
        
        # Find benchmark data directories
        benchmark_dirs = list(session_dir.glob('*/*/'))  # timestamp/tag directories
        
        summary_data = None
        percentile_data = None
        
        # Look for the first valid benchmark data
        for benchmark_dir in benchmark_dirs:
            summary_path = benchmark_dir / 'benchmark_summary.json'
            percentile_path = benchmark_dir / 'benchmark_percentile.json'
            
            if summary_path.exists() and percentile_path.exists():
                try:
                    # Read summary data
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                    
                    # Read percentile data
                    with open(percentile_path, 'r', encoding='utf-8') as f:
                        percentile_data = json.load(f)
                    
                    logger.info(f"Successfully loaded benchmark data from {benchmark_dir}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error reading benchmark data from {benchmark_dir}: {e}")
                    continue
        
        if not summary_data or not percentile_data:
            return jsonify({"error": "No valid benchmark data found"}), 404
        
        return jsonify({
            "summary": summary_data,
            "percentiles": percentile_data,
            "benchmark_dir": str(benchmark_dir) if 'benchmark_dir' in locals() else None
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
                    
                # Check if session has valid config
                config_path = session_dir / 'eval_config.json'
                if config_path.exists():
                    session_count += 1
                    
                    # Count benchmark results
                    benchmark_dirs = list(session_dir.glob('*/*/'))
                    for bd in benchmark_dirs:
                        if (bd / 'benchmark_summary.json').exists():
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