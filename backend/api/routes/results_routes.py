"""Results API routes for visualization."""

import json
import csv
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils import get_logger

logger = get_logger(__name__)

results_router = APIRouter(tags=["results"])


class ResultDataRequest(BaseModel):
    result_path: str


@results_router.get("/api/results/structure")
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
            return {"structure": []}

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

                    # Build flatter hierarchy
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
                unique_key = f"{path_prefix}/{key}" if path_prefix else key

                if isinstance(value, dict):
                    has_direct_sessions = any(isinstance(v, list) for v in value.values())

                    if has_direct_sessions:
                        tokens_children = []
                        for tokens_key, sessions_list in value.items():
                            if isinstance(sessions_list, list) and sessions_list:
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
                        children = build_tree(value, level + 1, unique_key)
                        if children:
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

        return {
            "structure": structure,
            "total_models": len(hierarchy),
            "total_sessions": total_sessions,
            "hierarchy_levels": ["model", "deployment_method_instance_framework_tp_size_dataset", "prefix_input_output_tokens"]
        }

    except Exception as e:
        logger.error(f"Error fetching results structure: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch results structure: {str(e)}")


@results_router.post("/api/results/data")
def get_result_data(data: ResultDataRequest):
    """Get detailed data for a specific result."""
    try:
        result_path = data.result_path

        if not result_path:
            raise HTTPException(status_code=400, detail="result_path is required")

        session_dir = Path(result_path)
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail=f"Result path does not exist: {result_path}")

        logger.info(f"Fetching data for result: {result_path}")

        # Check for performance metrics CSV
        performance_csv = session_dir / 'performance_metrics.csv'
        config_file = session_dir / 'config.json'

        if not performance_csv.exists():
            raise HTTPException(status_code=404, detail="No performance_metrics.csv found")

        if not config_file.exists():
            raise HTTPException(status_code=404, detail="No config.json found")

        try:
            # Read config file
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Read CSV performance data
            performance_data = []
            with open(performance_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    processed_row = {}
                    for key, value in row.items():
                        try:
                            processed_row[key] = float(value)
                        except (ValueError, TypeError):
                            processed_row[key] = value
                    performance_data.append(processed_row)

            # Load benchmark summary data for each concurrency level
            benchmark_summaries = {}

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
                                parallel_dirs.extend(find_parallel_dirs(item))
                except Exception as e:
                    logger.debug(f"Could not search directory {directory}: {e}")
                return parallel_dirs

            benchmark_files = find_parallel_dirs(session_dir)
            logger.info(f"Found {len(benchmark_files)} benchmark_summary.json files")

            for benchmark_summary_file in benchmark_files:
                try:
                    with open(benchmark_summary_file, 'r', encoding='utf-8') as f:
                        benchmark_data = json.load(f)
                        concurrency = benchmark_data.get('Number of concurrency', 0)
                        benchmark_summaries[concurrency] = benchmark_data
                        logger.info(f"Loaded benchmark summary for concurrency {concurrency}")
                except Exception as e:
                    logger.warning(f"Failed to load benchmark summary from {benchmark_summary_file}: {e}")

            # Enrich performance data with inter-token latency
            logger.info(f"Found {len(benchmark_summaries)} benchmark summaries: {list(benchmark_summaries.keys())}")
            for row in performance_data:
                concurrency = int(row.get('Concurrency', 0))
                if concurrency in benchmark_summaries:
                    itl_value = benchmark_summaries[concurrency].get('Average inter-token latency (s)', row.get('Avg_TPOT_s', 0))
                    tpot_value = row.get('Avg_TPOT_s', 0)
                    row['Avg_ITL_s'] = itl_value
                    logger.info(f"Enhanced concurrency {concurrency}: TPOT={tpot_value}, ITL={itl_value}")
                else:
                    fallback_value = row.get('Avg_TPOT_s', 0)
                    row['Avg_ITL_s'] = fallback_value
                    logger.info(f"Fallback for concurrency {concurrency}: using TPOT={fallback_value} as ITL")

            # Prepare summary data
            summary_data = {}
            percentile_data = []

            for row in performance_data:
                concurrency = row.get('Concurrency', 0)

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
            raise HTTPException(status_code=500, detail=f"Failed to read performance data: {str(e)}")

        return {
            "summary": summary_data,
            "percentiles": percentile_data,
            "config": config,
            "performance_data": performance_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch result data: {str(e)}")


@results_router.get("/api/results/stats")
def get_results_stats():
    """Get overall statistics about available results."""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        outputs_dir = project_root / 'outputs'

        if not outputs_dir.exists():
            return {
                "total_models": 0,
                "total_sessions": 0,
                "total_results": 0,
                "models": []
            }

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

                config_path = session_dir / 'config.json'
                if not config_path.exists():
                    config_path = session_dir / 'eval_config.json'

                if config_path.exists():
                    session_count += 1

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

        return stats

    except Exception as e:
        logger.error(f"Error fetching results stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch results stats: {str(e)}")
