# LLM Test Tool

一个用于测试 LLM API 性能的综合工具，支持自动化部署和广泛的测试矩阵。

![Web Interface Screenshot](./assets/web_screenshot.webp)

## 快速开始指南

### 0. 安装

```bash
git clone https://github.com/yytdfc/llm-performance-viz.git
cd llm-performance-viz/

uv sync  # optional
```

### 1. 前置条件（可选）

此步骤是可选的，但建议进行以便更好地准备部署。确保您的模型权重可通过 Hugging Face Hub 获取或已在本地预下载。该工具支持 `Qwen/Qwen3-235B-A22B-FP8`、`deepseek-ai/DeepSeek-R1-0528` 等模型。

#### 预下载模型权重
```bash
# Using Hugging Face CLI
uv run hf download Qwen/Qwen3-235B-A22B-FP8 --local-dir /opt/dlami/nvme/Qwen/Qwen3-235B-A22B-FP8
```

#### 预拉取 Docker 镜像
```bash
# vLLM images
docker pull vllm/vllm-openai:v0.9.2

# SGLang images
docker pull lmsysorg/sglang:v0.4.9.post4-cu126
```

具体的模型路径和 Docker 镜像应在您的模型配置文件中配置（参见 `model_configs/` 目录）。

### 2. 创建配置文件

配置文件存储在 `model_configs/` 中，按框架版本和实例类型组织：

```
model_configs/
└── [runtime_framework]/      # Runtime framework version (e.g., vllm-v0.9.2, sglang-v0.4.9.post4)
    └── [instance_type]/      # AWS instance type (e.g., p5.48xlarge, g6e.4xlarge)
        └── [model_config]/   # Model configuration YAML files
```

#### 配置文件结构

配置文件包含三个主要部分：

##### 1. 部署部分

部署参数直接映射到 Docker 命令：

```yaml
deployment:
  docker_image: "vllm/vllm-openai:v0.9.2"
  container_name: "vllm"
  port: 8080
  command: "python3 -m sglang.launch_server"  # Optional custom startup command
  
  # docker_params maps to docker run parameters
  docker_params:
    gpus: "all"                    # --gpus all
    shm-size: "1000g"              # --shm-size 1000g
    ipc: "host"                    # --ipc host
    network: "host"                # --network host
    volume:                        # -v /host:/container
      - "/opt/dlami/nvme/:/vllm-workspace/"
    environment:                   # -e KEY=VALUE
      CUDA_VISIBLE_DEVICES: "0,1,2,3"
  
  # app_args maps to application startup parameters
  app_args:
    model: "Qwen/Qwen3-235B-A22B-FP8"
    trust-remote-code: true
    max-model-len: 32768
    gpu-memory-utilization: 0.90
    tensor-parallel-size: 4
```

**Corresponding Docker command:**
```bash
docker run --gpus all --shm-size 1000g --ipc host --network host \
  -v /opt/dlami/nvme/:/vllm-workspace/ \
  -e CUDA_VISIBLE_DEVICES=0,1,2,3 \
  -p 8080:8080 --name vllm \
  vllm/vllm-openai:v0.9.2 \
  --port 8080 \
  --model Qwen/Qwen3-235B-A22B-FP8 \
  --trust-remote-code \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --tensor-parallel-size 4
```

##### 2. 测试矩阵部分

```yaml
test_matrix:
  input_tokens: [1600, 6400, 12800]     # Input token lengths
  output_tokens: [100, 400, 1000]       # Output token lengths
  processing_num: [1, 16, 32, 64, 128]  # Concurrent request counts
  random_tokens: [100, 1600, 6400]      # Random token counts (for cache testing)
```

##### 3. 测试配置部分

```yaml
test_config:
  requests_per_process: 5    # Number of requests each process sends
  warmup_requests: 1         # Number of warmup requests
  cooldown_seconds: 5        # Wait time between tests
```

#### 配置示例

**vLLM 配置示例：**

```yaml
deployment:
  docker_image: "vllm/vllm-openai:v0.9.2"
  container_name: "vllm"
  port: 8080
  # Universal Docker parameters
  docker_params:
    gpus: "all"
    shm-size: "1000g"
    ipc: "host"
    network: "host"
    volume:
      - "/opt/dlami/nvme/:/vllm-workspace/"
  # Universal application arguments
  app_args:
    model: "deepseek-ai/DeepSeek-R1-0528"
    trust-remote-code: true
    max-model-len: 32768
    gpu-memory-utilization: 0.90
    tensor-parallel-size: 8
    enable-reasoning: true
    reasoning-parser: "deepseek_r1"
    tool-call-parser: "deepseek_v3" 
    enable-auto-tool-choice: true

test_matrix:
  input_tokens: [1600, 6400, 12800]
  output_tokens: [100, 400, 1000]
  processing_num: [1, 16, 32, 64, 128]
  random_tokens: [100, 1600, 6400]

test_config:
  requests_per_process: 5
  warmup_requests: 1
  cooldown_seconds: 5
```

**SGLang 配置示例：**

```yaml
deployment:
  docker_image: "lmsysorg/sglang:v0.4.9.post4-cu126"
  container_name: "sglang"
  port: 8080
  
  # Universal Docker parameters
  docker_params:
    gpus: "all"
    shm-size: "1000g"
    ipc: "host"
    network: "host"
    volume:
      - "/opt/dlami/nvme/:/sgl-workspace/sglang/model"
  command: "python3 -m sglang.launch_server"
  # Universal application arguments
  app_args:
    host: "0.0.0.0"
    model-path: "model/deepseek-ai/DeepSeek-R1-0528"
    trust-remote-code: true
    tp-size: 8
    mem-fraction-static: 0.90
    tool-call-parser: "deepseekv3"
    reasoning-parser: "deepseek-r1"

test_matrix:
  input_tokens: [1600, 6400, 12800]
  output_tokens: [100, 400, 1000]
  processing_num: [1, 16, 32, 64, 128]
  random_tokens: [100, 1600, 6400]

test_config:
  requests_per_process: 5
  warmup_requests: 1
  cooldown_seconds: 5
```

### 3. 运行测试

#### 仅部署（不测试）
```bash
uv run deploy_server.py --config your_config.yaml
```

您可以添加 `--show-command` 参数来干运行并显示 Docker 部署命令以验证其正确性。

#### 使用现有服务器测试
```bash
uv run run_auto_test.py --config your_config.yaml --skip-deployment
```

#### 自动化测试与部署
```bash
uv run run_auto_test.py --config model_configs/vllm-v0.9.2/p5.48xlarge/Qwen3-235B-A22B-FP8-tp8ep.yaml
```

#### 单次测试

这运行单个测试配置并以结构化格式保存结果，可供 web 可视化服务器使用。您也可以添加 `--skip-deployment` 参数来在不部署的情况下测试。

```bash
# Run single test
./run_single_test.sh "model_configs/vllm-v0.9.2/g6e.48xlarge/Qwen3-235B-A22B-FP8-tp8ep.yaml"
```

#### 批量测试

这执行 `./run_model_tests.sh` 中找到的所有测试配置。结果自动按框架版本、实例类型和模型配置组织，维护一致的目录结构，使 web 服务器能够提供跨不同设置的全面性能比较和可视化。

```bash
# Run all configured tests
./run_model_tests.sh
```

### 4. 可视化结果

```bash
# Start visualization server
uv run start_viz_server.py

# Access web interface at: http://localhost:8000
```

## 手动测试用法

```bash
uv run llm-test --processes 4 --requests 10 --model_id "Qwen/Qwen3-30B-A3B-FP8" --input_tokens 1000 --random_tokens 500 --output_tokens 100 --url "http://localhost:8080/v1/chat/completions"
```

### 参数

- `--processes`: 并行进程数（默认：4）
- `--requests`: 每个进程的请求数（默认：5）
- `--model_id`: 要测试的模型 ID（默认："gpt-3.5-turbo"）
- `--input_tokens`: 总近似输入 token 长度（默认：1000）
- `--random_tokens`: 要添加到提示中的随机 token 数量（默认：500）
- `--output_tokens`: 要生成的最大输出 token 数（默认：100）
- `--url`: API 端点 URL（默认："http://localhost:8080/v1/chat/completions"）
- `--output`: 结果输出文件（默认："test_results.json"）

## 示例输出

```
Starting LLM API test:
- Processes: 4
- Requests per process: 10
- Total requests: 40
- Model ID: Qwen/Qwen3-30B-A3B-FP8
- Total input tokens: 1000
- Random tokens: 500
- Output tokens: 100
- API endpoint: http://localhost:8080/v1/chat/completions
--------------------------------------------------

Test completed!
Total duration: 12.45 seconds
Success rate: 100.00%
Throughput: 3.21 requests/second

First Token Latency (seconds):
- Min: 0.4521
- Max: 0.8976
- Mean: 0.6234

Percentiles:
- p25: 0.5123
- p50: 0.5987
- p75: 0.7234
- p90: 0.8456

End-to-End Latency (seconds):
- Min: 1.2345
- Max: 2.3456
- Mean: 1.7890

Percentiles:
- p25: 1.4567
- p50: 1.6789
- p75: 2.0123
- p90: 2.2345

Token Usage Statistics:

Prompt Tokens:
- Min: 998
- Max: 1002
- Mean: 1000.15

Percentiles:
- p25: 999
- p50: 1000
- p75: 1001
- p90: 1002

Completion Tokens:
- Min: 95
- Max: 105
- Mean: 99.8

Percentiles:
- p25: 97
- p50: 100
- p75: 102
- p90: 104

Output Tokens Per Second:
- Min: 45.23
- Max: 78.91
- Mean: 62.45

Percentiles:
- p25: 55.67
- p50: 61.23
- p75: 68.89
- p90: 74.56

Detailed results saved to: test_results.json
```

## 致谢

本项目主要由 [Kiro](https://kiro.dev/) 生成。

## 许可证

本项目采用 [MIT-0 许可证](./MIT-0)。
