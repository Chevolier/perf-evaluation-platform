# Model Performance Evaluation Platform

A comprehensive platform for model (LLMs, VLMs, etc.) deployment and performance evaluation. Supports 1-click deployment of various models on Amazon SageMaker Endpoint, SageMaker HyperPod, EKS, and EC2 using vLLM, SGLang, and other inference engines, plus comprehensive performance testing and visualization.

## ✨ Features

- **Model Hub**: Deploy and manage models with real-time status tracking
- **Interactive Playground**: Multi-model comparison with streaming inference
- **Performance Testing**: Stress testing and throughput benchmarking
- **Result Visualization**: Charts and analytics for performance metrics
- **Multimodal Support**: Text, image, and video processing capabilities
- **Enterprise Architecture**: Modular backend with service layer architecture

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

### Automated Setup

```bash
# Run the setup script (recommended)
./scripts/setup.sh
```

### Manual Setup

**1. Backend Environment**

```bash
# Create Python environment
conda create -n eval-platform python=3.10 -y
conda activate eval-platform
pip install -r requirements.txt

# Configure AWS credentials
aws configure
# OR set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_SESSION_TOKEN=your_token  # if using temporary credentials
```

**2. Frontend Environment**

```bash
# Install Node.js dependencies
cd frontend
npm install
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

## 📖 Platform Overview

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

**EMD Local Models** (require deployment):
- Qwen2-VL-7B-Instruct
- Qwen2.5-VL-32B-Instruct  
- Gemma-3-4B-IT
- UI-TARS-1.5-7B

**AWS Bedrock Models** (API-based):
- Claude 4
- Nova

### Media Processing

- **Images**: PNG, JPEG, GIF, WebP
- **Videos**: MP4, AVI, MOV (automatic frame extraction)
- **Text**: Full Unicode support with context handling

## 🔧 API Endpoints

### Model Management
- `GET /api/model-list` - Get all available models
- `GET /api/emd/current-models` - Get deployed EMD models
- `POST /api/deploy-models` - Deploy EMD models
- `POST /api/check-model-status` - Check deployment status
- `GET /api/emd/status` - EMD environment status
- `POST /api/emd/init` - Initialize EMD environment

### Inference Operations  
- `POST /api/multi-inference` - Multi-model batch inference (streaming)
- `POST /api/inference` - Single model inference

### Performance Testing
- `POST /api/stress-test/start` - Start stress test
- `GET /api/stress-test/status/<test_id>` - Check test status
- `GET /api/stress-test/results/<test_id>` - Get test results

### System Health
- `GET /health` - Health check endpoint
- `GET /` - API version and status

## 🛠️ Development

### Testing

```bash
# Test the modular system
python tests/test_new_system.py

# Test specific functionality
python tests/test_deploy_api.py
python tests/test_emd_response.py
python tests/test_evalscope_sdk.py

# Frontend tests
cd frontend && npm test
```

### Configuration

The platform uses environment-based configuration:

**Backend Configuration** (`backend/config/`):
- Development, production, and test environments
- Model registry with EMD and Bedrock definitions
- Logging configuration with file and console handlers
- Service endpoints and authentication settings

**Frontend Configuration**:
- Ant Design UI components
- Proxy configuration for API calls
- State management with localStorage persistence
- Responsive design with collapsible navigation

### Code Structure

**Backend Architecture**:
- **Service Layer**: Business logic isolation (`backend/services/`)
- **API Layer**: RESTful endpoints with blueprints (`backend/api/routes/`)
- **Core Layer**: Model registry and definitions (`backend/core/`)
- **Configuration**: Environment-specific settings (`backend/config/`)

**Frontend Architecture**:
- **Page Components**: Main application views (`frontend/src/pages/`)
- **Shared Components**: Reusable UI elements (`frontend/src/components/`)
- **State Management**: LocalStorage for persistence
- **Navigation**: Hash-based routing with browser history support

## 🐛 Troubleshooting

### Common Issues

**1. EMD Model Deployment Fails**
```bash
# Check EMD status and logs
emd status
python tests/test_deploy_api.py

# Verify AWS credentials
aws sts get-caller-identity
```

**2. Frontend Build Issues**
```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

**3. Backend Service Errors**
```bash
# Check system health
curl http://localhost:5000/health

# Test modular system
python tests/test_new_system.py
```

**4. Performance Test Issues**
```bash
# Verify model deployment status
curl -X POST http://localhost:5000/api/check-model-status \
  -H "Content-Type: application/json" \
  -d '{"models": ["qwen2-vl-7b"]}'
```

### Logging and Debug

**Backend Logs**: Located in `logs/` directory
```bash
# View backend logs
tail -f logs/development.log

# Enable debug logging endpoint
curl http://localhost:5000/debug/logging
```

**Frontend Debugging**: Use browser developer tools

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