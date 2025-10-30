# Model Performance Evaluation Platform

A comprehensive platform for model (LLMs, VLMs, etc.) deployment and performance evaluation. Supports 1-click deployment of various models on Amazon SageMaker Endpoint, SageMaker HyperPod, EKS, and EC2 using vLLM, SGLang, and other inference engines, plus comprehensive performance testing and visualization.

## ✨ Features

- **Model Hub**: Deploy and manage models with real-time status tracking
- **Interactive Playground**: Multi-model comparison with streaming inference
- **Performance Testing**: Stress testing and throughput benchmarking
- **Result Visualization**: Charts and analytics for performance metrics
- **Multimodal Support**: Text, image, and video processing capabilities
- **Enterprise Architecture**: Modular backend with service layer architecture
- **InfraForge Automation**: Launch and tear down SageMaker HyperPod clusters via InfraForge tooling with dry-run safety modes

## 🏗️ Architecture

```
├── backend/                    # Modular Flask API server
│   ├── app.py                  # Flask application factory
│   ├── api/                    # API layer
│   │   └── routes/            # Route blueprints
│   │       ├── model_routes.py      # Model management
│   │       ├── inference_routes.py  # Inference operations
│   │       ├── stress_test_routes.py # Performance testing
│   │       └── results_routes.py    # Results management
│   ├── services/               # Business logic layer
│   │   ├── model_service.py         # Model deployment & status
│   │   ├── inference_service.py     # Multi-model inference
│   │   └── stress_test_service.py   # Performance testing
│   ├── core/                   # Core functionality
│   │   └── models/            # Model definitions & registry
│   ├── config/                 # Configuration management
│   └── utils/                  # Utilities & logging
├── frontend/                   # React web application
│   ├── src/
│   │   ├── pages/             # Main application pages
│   │   │   ├── ModelHubPage.jsx     # Model deployment interface
│   │   │   ├── PlaygroundPage.jsx   # Interactive inference
│   │   │   ├── StressTestPage.jsx   # Performance testing
│   │   │   └── VisualizationPage.jsx # Results visualization
│   │   ├── components/        # Reusable UI components
│   │   └── App.js             # Main application shell
│   └── package.json           # Node.js dependencies
├── scripts/                    # Setup and utility scripts
├── tests/                      # Test suites
└── requirements.txt            # Python dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ (Required)
- Node.js 16+ 
- AWS credentials configured
- EMD CLI for model deployment

Recommended instance g5.2xlarge.

### Automated Setup (Recommended)

```bash
# Run the setup script 
./scripts/start.sh
```

This will automatically install backend and frontend packages and start the service.

### Manual Setup

**1. Backend Environment**

```bash
# Create Python environment
conda create -n perf-eval python=3.10 -y
conda activate perf-eval
pip install -r requirements.txt

cd evalscope/
pip install -e .
cd ..

# Configure AWS credentials
aws configure
# OR set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_SESSION_TOKEN=your_token  # if using temporary credentials
```

**2. Frontend Environment**

First, please install node js using the following commands in Linux. In other systems, please follow https://nodejs.org/en/download/ to install.

```bash
# Download and install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# in lieu of restarting the shell
\. "$HOME/.nvm/nvm.sh"

# Download and install Node.js:
nvm install 22

# Verify the Node.js version:
node -v # Should print "v22.19.0".
nvm current # Should print "v22.19.0".

# Verify npm version:
npm -v # Should print "10.9.3".
```

```bash
# Install Node.js dependencies
cd frontend
npm install jszip
npm install
```

Configure easy-model-deployer (emd) for 1-click model deployment using emd.

```bash
emd bootstrap
```

**3. Start the Platform**

```bash
# Terminal 1: Start backend (from project root)
python run_backend.py

# Terminal 2: Start frontend (from project root)
cd frontend && npm start
```

**4. Access the Application**

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **Health Check**: http://localhost:5000/health

### HyperPod InfraForge Integration

1. **Review configuration** – Update `config/environments/<env>.yaml` to point `hyperpod.infraforge_root` at your cloned InfraForge repository. By default the backend assumes `../InfraForge` relative to this project.
2. **Fetch tooling** – Run `scripts/fetch_infraforge.sh` (optionally pass a target directory) to clone/update InfraForge at the pinned ref so the backend can execute the CLI.
3. **Dry-run behaviour** – Development keeps `hyperpod.dry_run=true` so InfraForge commands log without touching AWS. Set `dry_run: false` in production to execute real deployments.
4. **Launch via API/UI** – Use `POST /api/hyperpod/deploy` or the HyperPod card in Model Hub (preset + overrides). Monitor progress with `GET /api/hyperpod/jobs` and retrieve logs from `GET /api/hyperpod/jobs/{job_id}/logs`.
5. **Teardown** – Invoke `POST /api/hyperpod/destroy` with the target preset (and region override if needed) to call InfraForge destroy scripts.

All HyperPod job logs are written to `logs/hyperpod*` and surfaced through the API for frontend consumption.

## Model Deployment
Currently, this platform supports 1-click model deployment using emd. But the vllm version may not be the latest. To evaluate the model's best performance, it is sugggested to deploy a model on a local EC2 instance using the latest vllm or sglang, then manually input api_url and model_name on the 在线体验 or 性能评测 pages. 

### Local EC2 model deployment
To use vllm to start a server on an g5.2xlarge instance:

```bash
# enable-prompt-tokens-details would help to show token usage info in response
vllm serve Qwen/Qwen3-8B \
	--gpu-memory-utilization 0.9 \
	--max-model-len 2048 \
  --enable-prompt-tokens-details

nohup vllm serve Qwen/Qwen2.5-VL-7B-Instruct \
     --host 0.0.0.0 --port 8000 \
     --dtype bfloat16\
    --gpu-memory-utilization 0.9 \
    --max-model-len 2048 \
    --limit-mm-per-prompt '{"images": 1, "videos": 1}' \
    --enable-prompt-tokens-details \
    >logs/serve_qwen2.5-vl-7bi.out 2>&1 &

nohup vllm serve /home/ec2-user/SageMaker/efs/Models/Qwen3-8B \
     --host 0.0.0.0 --port 8000 \
     --dtype bfloat16\
    --gpu-memory-utilization 0.9 \
    --max-model-len 2048 \
    --enable-prompt-tokens-details \
    >logs/serve_qwen3-8b.out 2>&1 &
    
```
You will obtain:
Api url: http://0.0.0.0:8000/v1/chat/completions
Model name: /home/ec2-user/SageMaker/efs/Models/Qwen3-8B

Then use the above api url and model name to do stress test.

## 📖 Platform Overview

### The frontend has 4 pages:
1. 模型部署: Supports 1-click model deployment on local EC2, supports selecting among different instances like g5.xlarge, g6e.xlarge, p4d.xlarge, etc., different inference frameworks like vllm, sglang.
2. 在线体验: Supports three ways to test the model: a. If you deployed the model using step 1, you'll find the model in the list, and you can choose the model to test. b. If you deployed a model manually, you can input your OpenAI-compatible api url and model name and test it directly. c. If you deploy using SageMaker Endpoint, you can input your Endpoint name and model name.  
3. 性能评测: Similarly, you can stress test on both the deployed model on this platform and manually-deployed model elsewhere by inputting your api url and model name. After stress test, you can click the button download to download the detailed evaluation results.
4. 结果展示: You can select your previous results and compare them together. You can also click the download button to download a html file of the comparison results.


### Core Modules

**1. Model Hub (模型部署)**
- Deploy EMD models to AWS infrastructure
- Real-time deployment status monitoring
- Support for multiple instance types and inference engines
- Batch deployment and management

**2. Interactive Playground (在线体验)**
- Multi-model inference comparison
- Streaming and batch processing modes
- Multimodal input support (text, images, video)
- Real-time response generation

**3. Performance Testing (性能评测)**
- Stress testing with configurable parameters
- Throughput and latency benchmarking
- Concurrent request simulation
- Performance metrics collection

**4. Result Visualization (结果展示)**
- Performance charts and analytics
- Model comparison dashboards
- Historical trend analysis
- Export capabilities

### Supported Models

**EC2 Local Models** :
- Qwen2-VL-7B-Instruct
- Qwen2.5-VL-32B-Instruct  
- Qwen-8B

**AWS Bedrock Models** (API-based):
- Claude 4
- Nova

### Media Processing

- **Images**: PNG, JPEG, GIF, WebP
- **Videos**: MP4, AVI, MOV (automatic frame extraction)
- **Text**: Full Unicode support with context handling


### System Requirements

- **Minimum**: 8GB RAM, 4 CPU cores
- **Recommended**: 16GB RAM, 8 CPU cores
- **Storage**: 50GB free space for model deployments
- **Network**: Stable internet for AWS API calls

## 🔒 Security Best Practices

- Store AWS credentials in environment variables or AWS credentials file
- Use IAM roles with minimum required permissions
- Enable VPC security groups for deployed models
- Implement rate limiting for production deployments
- Regular security updates for all dependencies

## 📈 Performance Optimization

- **Model Deployment**: Use appropriate instance types for workloads
- **Frontend**: Enable compression and caching for production
- **Backend**: Configure proper logging levels in production
- **Database**: Use connection pooling for high-traffic scenarios

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow the existing code style and architecture patterns
4. Add tests for new functionality
5. Ensure all tests pass (`python tests/test_new_system.py`)
6. Submit a pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

**For Technical Issues:**
- Check the troubleshooting section above
- Review logs in `logs/development.log`
- Test system health with provided test scripts

**For Feature Requests:**
- Open an issue with detailed requirements
- Include use cases and expected behavior

---

**🚀 Built for enterprise-scale model performance evaluation and deployment**
