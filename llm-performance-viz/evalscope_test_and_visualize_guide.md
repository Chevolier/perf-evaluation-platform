# Evalscope 性能测试与可视化指南

本指南介绍如何使用 evalscope 进行大语言模型性能测试，并通过前端可视化工具展示测试结果。

## 使用步骤

### 1. 运行测试

编辑 `evalscope.sh` 脚本，设置你的测试参数：

```bash
# 基本配置
framework="sglang"           # 推理框架名称
instancetype="g6e.2xlarge"   # 实例类型
model="Qwen3-4B"            # 模型名称

# 性能测试参数
evalscope perf \
--parallel 1 16 32 64 \                    # 并发数列表
--number 10 32 64 128 \                    # 每个并发的请求数
--model Qwen/Qwen3-4B \                    # 模型路径
--url http://127.0.0.1:8080/v1/completions \ # API 端点
--api openai \                             # API 类型
--dataset random \                         # 数据集类型
--max-tokens 400 \                         # 最大输出 token 数
--min-tokens 400 \                         # 最小输出 token 数
--prefix-length 0 \                        # 前缀长度
--min-prompt-length 1600 \                 # 最小输入长度
--max-prompt-length 1600 \                 # 最大输入长度
--tokenizer-path /opt/dlami/nvme/Qwen/Qwen3-4B \ # tokenizer 路径
--extra-args '{"ignore_eos": true}' \      # 额外参数
--outputs-dir evalscope_results/$framework--$instancetype--$model
```

### 2. 测试结果说明

测试完成后，会在 `evalscope_results/` 目录下生成结果文件：

```
evalscope_results/
└── sglang--g6e.2xlarge--Qwen3-4B/
    └── 20250813_101254/              # 时间戳目录
        └── Qwen3-4B/                 # 模型目录
            ├── parallel_1_number_10/  # 并发1，请求10
            ├── parallel_16_number_32/ # 并发16，请求32
            ├── parallel_32_number_64/ # 并发32，请求64
            └── parallel_64_number_128/# 并发64，请求128
```

每个测试目录包含：
- `benchmark_summary.json` - 汇总统计信息
- `benchmark_percentile.json` - 百分位数据
- `benchmark_args.json` - 测试参数

### 3. 自动转换和启动可视化

脚本会自动执行以下步骤：

```bash
# 转换结果格式
uv run convert_evalscope_to_archive.py --input evalscope_results/ --output evalscope_archive_results/

# 启动可视化服务器
uv run start_viz_server.py --results-dir evalscope_archive_results/
```

