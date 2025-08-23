#!/usr/bin/env python3
"""
转换 evalscope_results 格式的测试结果为 archive_results 格式
用于可视化工具使用
"""

import json
import os
import argparse
import shutil
from pathlib import Path
from typing import Dict, Any, List


def parse_evalscope_directory_name(dir_name: str) -> Dict[str, str]:
    """
    解析 evalscope 目录名，提取框架、实例类型和模型信息
    例如: sglang--g6e.2xlarge--Qwen3-4B
    """
    parts = dir_name.split('--')
    if len(parts) >= 3:
        return {
            'framework': parts[0],
            'instance_type': parts[1], 
            'model': parts[2]
        }
    return {'framework': 'unknown', 'instance_type': 'unknown', 'model': 'unknown'}


def parse_parallel_directory_name(dir_name: str) -> Dict[str, int]:
    """
    解析并发目录名，提取并发数和请求数
    例如: parallel_1_number_10
    """
    parts = dir_name.split('_')
    parallel = 1
    number = 10
    
    for i, part in enumerate(parts):
        if part == 'parallel' and i + 1 < len(parts):
            try:
                parallel = int(parts[i + 1])
            except ValueError:
                pass
        elif part == 'number' and i + 1 < len(parts):
            try:
                number = int(parts[i + 1])
            except ValueError:
                pass
    
    return {'parallel': parallel, 'number': number}


def convert_percentile_to_statistics(percentile_data: List[Dict], summary_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 evalscope 的百分位数据转换为 archive 格式的统计数据
    """
    if not percentile_data:
        return {}
    
    # 提取各个指标的值
    ttft_values = [item["TTFT (s)"] for item in percentile_data]
    latency_values = [item["Latency (s)"] for item in percentile_data]
    tpot_values = [item["TPOT (s)"] for item in percentile_data]  # Time Per Output Token
    # 计算 Output Tokens Per Second = 1 / TPOT
    output_tps_values = [1.0 / tpot for tpot in tpot_values]
    
    # 获取输入输出token数（假设所有请求相同）
    input_tokens = percentile_data[0]["Input tokens"]
    output_tokens = percentile_data[0]["Output tokens"]
    total_tokens = input_tokens + output_tokens
    
    # 从 summary 数据中获取平均值
    avg_ttft = summary_data.get("Average time to first token (s)", sum(ttft_values) / len(ttft_values))
    avg_latency = summary_data.get("Average latency (s)", sum(latency_values) / len(latency_values))
    # 计算平均 Output Tokens Per Second = 1 / Average time per output token
    avg_tpot = summary_data.get("Average time per output token (s)", sum(tpot_values) / len(tpot_values))
    avg_output_tps = 1.0 / avg_tpot if avg_tpot > 0 else 0
    avg_input_tokens = summary_data.get("Average input tokens per request", input_tokens)
    avg_output_tokens = summary_data.get("Average output tokens per request", output_tokens)
    avg_total_tokens = avg_input_tokens + avg_output_tokens
    # 构建统计数据
    statistics = {
        "first_token_latency": {
            "min": min(ttft_values),
            "max": max(ttft_values),
            "mean": avg_ttft,
            "p25": next((item["TTFT (s)"] for item in percentile_data if item["Percentiles"] == "25%"), ttft_values[0]),
            "p50": next((item["TTFT (s)"] for item in percentile_data if item["Percentiles"] == "50%"), ttft_values[0]),
            "p75": next((item["TTFT (s)"] for item in percentile_data if item["Percentiles"] == "75%"), ttft_values[0]),
            "p90": next((item["TTFT (s)"] for item in percentile_data if item["Percentiles"] == "90%"), ttft_values[0])
        },
        "end_to_end_latency": {
            "min": min(latency_values),
            "max": max(latency_values),
            "mean": avg_latency,
            "p25": next((item["Latency (s)"] for item in percentile_data if item["Percentiles"] == "25%"), latency_values[0]),
            "p50": next((item["Latency (s)"] for item in percentile_data if item["Percentiles"] == "50%"), latency_values[0]),
            "p75": next((item["Latency (s)"] for item in percentile_data if item["Percentiles"] == "75%"), latency_values[0]),
            "p90": next((item["Latency (s)"] for item in percentile_data if item["Percentiles"] == "90%"), latency_values[0])
        },
        "token_usage": {
            "prompt_tokens": {
                "min": input_tokens,
                "max": input_tokens,
                "mean": avg_input_tokens,
                "p25": float(input_tokens),
                "p50": float(input_tokens),
                "p75": float(input_tokens),
                "p90": float(input_tokens)
            },
            "completion_tokens": {
                "min": output_tokens,
                "max": output_tokens,
                "mean": avg_output_tokens,
                "p25": float(output_tokens),
                "p50": float(output_tokens),
                "p75": float(output_tokens),
                "p90": float(output_tokens)
            },
            "total_tokens": {
                "min": total_tokens,
                "max": total_tokens,
                "mean": avg_total_tokens,
                "p25": float(total_tokens),
                "p50": float(total_tokens),
                "p75": float(total_tokens),
                "p90": float(total_tokens)
            }
        },
        "output_tokens_per_second": {
            "min": min(output_tps_values),
            "max": max(output_tps_values),
            "mean": avg_output_tps,
            "p25": next((1.0 / item["TPOT (s)"] for item in percentile_data if item["Percentiles"] == "25%"), output_tps_values[0]),
            "p50": next((1.0 / item["TPOT (s)"] for item in percentile_data if item["Percentiles"] == "50%"), output_tps_values[0]),
            "p75": next((1.0 / item["TPOT (s)"] for item in percentile_data if item["Percentiles"] == "75%"), output_tps_values[0]),
            "p90": next((1.0 / item["TPOT (s)"] for item in percentile_data if item["Percentiles"] == "90%"), output_tps_values[0])
        },
        "error_messages": []
    }
    
    return statistics


def convert_single_test(evalscope_test_dir: Path, output_dir: Path, framework_info: Dict[str, str]) -> bool:
    """
    转换单个测试结果
    """
    try:
        # 读取必要的文件
        percentile_file = evalscope_test_dir / "benchmark_percentile.json"
        summary_file = evalscope_test_dir / "benchmark_summary.json"
        args_file = evalscope_test_dir / "benchmark_args.json"
        
        if not all(f.exists() for f in [percentile_file, summary_file, args_file]):
            print(f"缺少必要文件: {evalscope_test_dir}")
            return False
        
        # 读取数据
        with open(percentile_file, 'r') as f:
            percentile_data = json.load(f)
        
        with open(summary_file, 'r') as f:
            summary_data = json.load(f)
        
        with open(args_file, 'r') as f:
            args_data = json.load(f)
        
        # 从 args 文件中读取参数
        input_tokens = args_data.get("max_prompt_length", 1600)
        output_tokens = args_data.get("max_tokens", 400)
        prefix_length = args_data.get("prefix_length", 0)
        processes = args_data.get("parallel", 1)
        total_requests = args_data.get("number", 10)
        
        # 计算随机token数
        random_tokens = input_tokens - prefix_length
        
        # 构建输出文件名
        output_filename = f"test_in:{input_tokens}_out:{output_tokens}_proc:{processes}_rand:{random_tokens}.json"
        
        # 转换数据格式
        converted_data = {
            "metadata": {
                "processes": processes,
                "requests_per_process": total_requests // processes if processes > 0 else total_requests,
                "total_requests": total_requests,
                "model_id": framework_info['model'],
                "input_tokens": input_tokens,
                "random_tokens": random_tokens,
                "output_tokens": output_tokens,
                "url": args_data.get("url", "http://localhost:8080/v1/chat/completions"),
                "output_file": str(output_dir / output_filename),
                "total_test_duration": summary_data.get("Time taken for tests (s)", 0),
                "requests_per_second": summary_data.get("Request throughput (req/s)", 0)
            },
            "statistics": {
                "total_requests": total_requests,
                "successful_requests": summary_data.get("Succeed requests", total_requests),
                "failed_requests": summary_data.get("Failed requests", 0),
                "success_rate": summary_data.get("Succeed requests", total_requests) / total_requests if total_requests > 0 else 1.0,
                **convert_percentile_to_statistics(percentile_data, summary_data)
            }
        }
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 写入转换后的文件
        output_file = output_dir / output_filename
        with open(output_file, 'w') as f:
            json.dump(converted_data, f, indent=2)
        
        print(f"转换完成: {output_file}")
        return True
        
    except Exception as e:
        print(f"转换失败 {evalscope_test_dir}: {e}")
        return False


def convert_evalscope_results(input_dir: str, output_dir: str):
    """
    转换整个 evalscope_results 目录
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        print(f"输入目录不存在: {input_dir}")
        return
    
    # 遍历所有测试结果目录
    for test_dir in input_path.iterdir():
        if not test_dir.is_dir():
            continue
        
        print(f"处理测试目录: {test_dir.name}")
        
        # 解析目录名获取框架信息
        framework_info = parse_evalscope_directory_name(test_dir.name)
        
        # 构建输出目录名（模仿 archive_results 的命名格式）
        output_subdir_name = f"{framework_info['framework']}--{framework_info['instance_type']}--{framework_info['model']}"
        output_subdir = output_path / output_subdir_name
        
        # 遍历时间戳目录
        for timestamp_dir in test_dir.iterdir():
            if not timestamp_dir.is_dir():
                continue
            
            # 遍历模型目录
            for model_dir in timestamp_dir.iterdir():
                if not model_dir.is_dir():
                    continue
                
                # 遍历并发测试目录
                for parallel_dir in model_dir.iterdir():
                    if not parallel_dir.is_dir():
                        continue
                    
                    print(f"  转换: {parallel_dir}")
                    convert_single_test(parallel_dir, output_subdir, framework_info)


def main():
    parser = argparse.ArgumentParser(description="转换 evalscope_results 格式为 archive_results 格式")
    parser.add_argument("--input", "-i", required=True, help="输入目录 (evalscope_results)")
    parser.add_argument("--output", "-o", required=True, help="输出目录 (archive_results)")
    
    args = parser.parse_args()
    
    print(f"开始转换...")
    print(f"输入目录: {args.input}")
    print(f"输出目录: {args.output}")
    
    convert_evalscope_results(args.input, args.output)
    
    print("转换完成!")


if __name__ == "__main__":
    main()