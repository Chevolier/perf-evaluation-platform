"""
Results analysis module for LLM Test Tool.
"""

import json
import statistics
from typing import Dict, List, Any

from .config import TestConfig


class ResultAnalyzer:
    """Analyzes test results and generates statistics"""
    
    @staticmethod
    def analyze(results: List[Dict[str, Any]], test_duration: float, config: TestConfig) -> Dict[str, Any]:
        """Analyze test results and generate statistics"""
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        if not successful_requests:
            return {
                "total_requests": len(results),
                "successful_requests": 0,
                "failed_requests": len(failed_requests),
                "success_rate": 0,
                "error_messages": [r["error"] for r in failed_requests if "error" in r]
            }
        
        first_token_latencies = [r["first_token_latency"] for r in successful_requests 
                                if r["first_token_latency"] is not None]
        end_to_end_latencies = [r["end_to_end_latency"] for r in successful_requests 
                               if r["end_to_end_latency"] is not None]
        
        # Collect token usage statistics
        prompt_tokens = [r["prompt_tokens"] for r in successful_requests if "prompt_tokens" in r]
        completion_tokens = [r["completion_tokens"] for r in successful_requests if "completion_tokens" in r]
        total_tokens = [r["total_tokens"] for r in successful_requests if "total_tokens" in r]
        
        # Calculate output tokens per second (completion_tokens / (end_to_end_latency - first_token_latency))
        output_tokens_per_second = []
        for r in successful_requests:
            if (r.get("completion_tokens", 0) > 0 and 
                r.get("end_to_end_latency") is not None and 
                r.get("first_token_latency") is not None):
                generation_time = r["end_to_end_latency"] - r["first_token_latency"]
                if generation_time > 0:
                    tokens_per_sec = r["completion_tokens"] / generation_time
                    output_tokens_per_second.append(tokens_per_sec)
        
        # Calculate statistics
        stats = {
            "total_requests": len(results),
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / len(results) if results else 0,
            
            # First token latency stats
            "first_token_latency": ResultAnalyzer._calculate_metrics(first_token_latencies),
            
            # End-to-end latency stats
            "end_to_end_latency": ResultAnalyzer._calculate_metrics(end_to_end_latencies),
            
            # Token usage stats
            "token_usage": {
                "prompt_tokens": ResultAnalyzer._calculate_metrics(prompt_tokens),
                "completion_tokens": ResultAnalyzer._calculate_metrics(completion_tokens),
                "total_tokens": ResultAnalyzer._calculate_metrics(total_tokens)
            },
            
            # Output tokens per second stats
            "output_tokens_per_second": ResultAnalyzer._calculate_metrics(output_tokens_per_second),
            
            # Error messages
            "error_messages": [r["error"] for r in failed_requests if "error" in r]
        }
        
        # Add test metadata
        test_metadata = {
            "processes": config.processes,
            "requests_per_process": config.requests_per_process,
            "total_requests": config.processes * config.requests_per_process,
            "model_id": config.model_id,
            "input_tokens": config.input_tokens,
            "random_tokens": config.random_tokens,
            "output_tokens": config.output_tokens,
            "url": config.url,
            "output_file": config.output_file,
            "total_test_duration": test_duration,
            "requests_per_second": (config.processes * config.requests_per_process) / test_duration 
                                  if test_duration > 0 else 0
        }
        
        # Merge results
        return {
            "metadata": test_metadata,
            "statistics": stats
        }
    
    @staticmethod
    def _calculate_metrics(values: List[float]) -> Dict[str, float]:
        """Calculate statistical metrics for a list of values including percentiles"""
        if not values:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "p25": None,
                "p50": None,
                "p75": None,
                "p90": None
            }
        
        # Sort values for percentile calculations
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Calculate percentiles
        def percentile(p):
            """Calculate the p-th percentile of the values"""
            if n == 0:
                return None
            k = (n - 1) * p
            f = int(k)
            c = k - f
            if f + 1 < n:
                return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
            else:
                return sorted_values[f]
        
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "p25": percentile(0.25),  # 25th percentile
            "p50": percentile(0.50),  # 50th percentile (median)
            "p75": percentile(0.75),  # 75th percentile
            "p90": percentile(0.90)   # 90th percentile
        }
    
    @staticmethod
    def save_results(results: Dict[str, Any], filename: str) -> None:
        """Save results to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
    
    @staticmethod
    def print_summary(results: Dict[str, Any]) -> None:
        """Print a summary of the test results"""
        metadata = results["metadata"]
        stats = results["statistics"]
        
        print("\nTest completed!")
        print(f"Total duration: {metadata['total_test_duration']:.2f} seconds")
        print(f"Success rate: {stats['success_rate'] * 100:.2f}%")
        print(f"Throughput: {metadata['requests_per_second']:.2f} requests/second")
        
        print("\nFirst Token Latency (seconds):")
        metrics = stats["first_token_latency"]
        if metrics["min"] is not None:
            print(f"- Min: {metrics['min']:.4f}")
            print(f"- Max: {metrics['max']:.4f}")
            print(f"- Mean: {metrics['mean']:.4f}")
            print("\nPercentiles:")
            print(f"- p25: {metrics['p25']:.4f}")
            print(f"- p50: {metrics['p50']:.4f}")
            print(f"- p75: {metrics['p75']:.4f}")
            print(f"- p90: {metrics['p90']:.4f}")
        
        print("\nEnd-to-End Latency (seconds):")
        metrics = stats["end_to_end_latency"]
        if metrics["min"] is not None:
            print(f"- Min: {metrics['min']:.4f}")
            print(f"- Max: {metrics['max']:.4f}")
            print(f"- Mean: {metrics['mean']:.4f}")
            print("\nPercentiles:")
            print(f"- p25: {metrics['p25']:.4f}")
            print(f"- p50: {metrics['p50']:.4f}")
            print(f"- p75: {metrics['p75']:.4f}")
            print(f"- p90: {metrics['p90']:.4f}")
        
        if "token_usage" in stats:
            print("\nToken Usage Statistics:")
            for token_type, metrics in stats["token_usage"].items():
                print(f"\n{token_type.replace('_', ' ').title()}:")
                if metrics["min"] is not None:
                    print(f"- Min: {metrics['min']}")
                    print(f"- Max: {metrics['max']}")
                    print(f"- Mean: {metrics['mean']:.2f}")
                    print("\nPercentiles:")
                    print(f"- p25: {metrics['p25']}")
                    print(f"- p50: {metrics['p50']}")
                    print(f"- p75: {metrics['p75']}")
                    print(f"- p90: {metrics['p90']}")
        
        if "output_tokens_per_second" in stats:
            print("\nOutput Tokens Per Second:")
            metrics = stats["output_tokens_per_second"]
            if metrics["min"] is not None:
                print(f"- Min: {metrics['min']:.2f}")
                print(f"- Max: {metrics['max']:.2f}")
                print(f"- Mean: {metrics['mean']:.2f}")
                print("\nPercentiles:")
                print(f"- p25: {metrics['p25']:.2f}")
                print(f"- p50: {metrics['p50']:.2f}")
                print(f"- p75: {metrics['p75']:.2f}")
                print(f"- p90: {metrics['p90']:.2f}")
        
        # Add output_file to metadata in analyze method
        output_file = metadata.get("output_file", "results.json")
        print(f"\nDetailed results saved to: {output_file}")