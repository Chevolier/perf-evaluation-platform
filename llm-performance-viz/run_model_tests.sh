#!/bin/bash

# Simple batch testing script for vLLM model configurations
# Runs tests for each model config with organized output directories

set -e

ec2_instance_type=`ec2metadata --instance-type`
echo Current instance type: $ec2_instance_type

# Function to run test using the extracted single test runner
run_test() {
    local config_path="$1"
    local additional_args="$2"
    
    # Skip if no config path provided
    if [ -z "$config_path" ]; then
        return 0
    fi
    
    # Remove "model_configs/" prefix if present for parsing
    local clean_path="${config_path#model_configs/}"
    
    # Extract instance type from path
    local instance_type=$(echo "$clean_path" | cut -d'/' -f2)
    local model_name=$(echo "$clean_path" | cut -d'/' -f3)
    
    # Check if instance type matches current EC2 instance
    if [ "$instance_type" != "$ec2_instance_type" ]; then
        echo "⏭️  Skipping: $model_name (requires $instance_type, current: $ec2_instance_type)"
        return 0
    fi
    
    # Use the extracted single test runner
    ./run_single_test.sh "$config_path" "$additional_args"
}

# Create output directory
mkdir -p archive_results

# Run tests for each model configuration
echo "Starting batch tests for vLLM model configurations..."
echo ""

#==================================================================================
# g6e.2xlarge
run_test "model_configs/vllm-v0.9.2/g6e.2xlarge/Qwen3-14B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.2xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.2xlarge/Qwen3-4B-tp1.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.2xlarge/Qwen3-14B-tp1.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.2xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.2xlarge/Qwen3-4B-tp1.yaml"

#==================================================================================
# g6e.4xlarge
run_test "model_configs/vllm-v0.9.2/g6e.4xlarge/Qwen3-30B-A3B-FP8.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.4xlarge/Qwen3-30B-A3B-FP8.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.4xlarge/Qwen3-8B-FP8.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.4xlarge/Qwen3-14B-FP8.yaml"

#==================================================================================
# g5.2xlarge
run_test "model_configs/vllm-v0.9.2/g5.2xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/g5.2xlarge/Qwen3-4B-tp1.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g5.2xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g5.2xlarge/Qwen3-4B-tp1.yaml"



#==================================================================================
# g5.48xlarge
run_test "model_configs/vllm-v0.9.2/g5.48xlarge/Qwen3-8B-tp1dp8.yaml"
run_test "model_configs/vllm-v0.9.2/g5.48xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g5.48xlarge/Qwen3-32B-tp8.yaml"
run_test "model_configs/vllm-v0.9.2/g5.48xlarge/Qwen3-32B-tp8.yaml"

#==================================================================================
# g6e.12xlarge
run_test "model_configs/vllm-v0.9.2/g6e.12xlarge/Qwen3-32B-tp4.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.12xlarge/Qwen3-32B-tp4.yaml"
#==================================================================================
# g6e.48xlarge
run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-8B-tp1dp8.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-14B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-14B-tp1dp8.yaml"
run_test "model_configs/sglang-v0.4.9.post4/g6e.48xlarge/Qwen3-32B-tp8.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-32B-tp8.yaml"



# run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-235B-A22B-FP8-tp8ep.yaml"
run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-32B-tp8.yaml"
# run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-32B-tp4dp2.yaml"
# run_test "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-32B-tp4dp2.yaml"

# run_test "model_configs/sglang-v0.4.9.post4/g6e.48xlarge/Qwen3-32B-FP8-tp4dp2.yaml"
# run_test "model_configs/sglang-v0.4.9.post4/g6e.48xlarge/Qwen3-32B-AWQ-tp4dp2.yaml"
#==================================================================================
# p4d.24xlarge
# run_test "model_configs/sglang-v0.4.9.post4/p4d.24xlarge/Qwen3-32B-tp8.yaml"
# run_test "model_configs/sglang:v0.4.7.post1/p4d.24xlarge/Qwen3-32B-tp8.yaml"
# run_test "model_configs/sglang:v0.4.7.post1/p4d.24xlarge/Qwen3-30B-A3B-tp8.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-14B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-14B-tp1dp8.yaml"

run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-8B-tp1.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-8B-tp1dp8.yaml"

run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-32B-tp4dp2.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-32B-AWQ-tp4dp2.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-32B-AWQ-tp2dp4.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-32B-tp8.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-30B-A3B-tp4dp2.yaml"
run_test "model_configs/vllm-v0.9.2/p4d.24xlarge/Qwen3-30B-A3B-tp8.yaml"

#==================================================================================

# p4de.24xlarge
run_test "model_configs/vllm-v0.9.2/p4de.24xlarge/Qwen3-235B-A22B.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p4de.24xlarge/Qwen3-235B-A22B.yaml"

#==================================================================================

# p5.48xlarge
run_test "model_configs/vllm-v0.9.2/p5.48xlarge/Qwen3-235B-A22B.yaml"
run_test "model_configs/vllm-v0.9.2/p5.48xlarge/Qwen3-235B-A22B-FP8-tp8ep.yaml"

run_test "model_configs/sglang-v0.4.9.post4/p5.48xlarge/Qwen3-235B-A22B.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5.48xlarge/Qwen3-30B-A3B-FP8-tp1dp8.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5.48xlarge/Qwen3-30B-A3B-FP8-tp1dp1.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5.48xlarge/GLM-4.5-Air-FP8-tp2dp4-mtp.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5.48xlarge/GLM-4.5-Air-FP8-tp4dp2-mtp.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5.48xlarge/GLM-4.5-FP8-tp8-mtp.yaml"

#==================================================================================

# p5.48xlarge
run_test "model_configs/sglang-v0.4.9.post4/p5e.48xlarge/Qwen3-235B-A22B.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5e.48xlarge/DeepSeek-R1-0528.yaml"

#==================================================================================

# p5en.48xlarge

run_test "model_configs/vllm-v0.9.2/p5en.48xlarge/Qwen3-235B-A22B.yaml"
run_test "model_configs/vllm-v0.9.2/p5en.48xlarge/DeepSeek-R1-0528.yaml"
run_test "model_configs/vllm-v0.9.2/p5en.48xlarge/Qwen3-Coder-480B-A35B-Instruct-FP8.yaml"
run_test "model_configs/vllm-v0.9.2/p5en.48xlarge/Qwen3-235B-A22B-FP8-tp8ep.yaml"
run_test "model_configs/vllm-v0.9.2/p5en.48xlarge/Qwen3-Coder-480B-A35B-Instruct-FP8-deepgemm.yaml"

run_test "model_configs/sglang-v0.4.9.post4/p5en.48xlarge/DeepSeek-R1-0528.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5en.48xlarge/DeepSeek-R1-0528-mtp.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5en.48xlarge/Qwen3-235B-A22B-FP8-tp4dp2.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5en.48xlarge/Qwen3-235B-A22B.yaml"
run_test "model_configs/sglang-v0.4.9.post4/p5en.48xlarge/Qwen3-235B-A22B-FP8-tp8ep8.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5en.48xlarge/GLM-4.5-Air-FP8-dp8-mtp.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5en.48xlarge/GLM-4.5-Air-FP8-tp2dp4-mtp.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5en.48xlarge/GLM-4.5-FP8-tp8-mtp.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5en.48xlarge/GLM-4.5-FP8-tp8.yaml"
run_test "model_configs/sglang-v0.4.9.post6/p5en.48xlarge/GLM-4.5-FP8-tp4dp2-mtp.yaml"


# p6-b200.48xlarge


echo "=========================================="
echo "All tests completed!"
echo "Results saved in archive_results/"
echo "=========================================="