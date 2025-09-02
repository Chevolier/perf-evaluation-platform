# Model Performance Evaluation Platform

A platform for model performance evaluation. Supports 1-click deployment of various LLMs and VLMs on Amazon SageMaker Endpoint, Amazon SageMaker HyperPod, Amazon EKS, EC2 using vllm, sglang, etc., and 1-click performance evaluation. 

## ✨ Features

- **Multiple Model Support**: AWS Bedrock (Claude 4, Nova) and EMD local models (Qwen2-VL, Gemma, UI-TARS)
- **Multimodal Processing**: Text, images, and video frame analysis
- **Dual Inference Modes**: Real-time streaming and batch processing
- **Mixed Model Selection**: Compare responses across different model types
- **Comprehensive Logging**: Detailed process tracking with emoji indicators
- **Error Handling**: Graceful failures with helpful deployment instructions

## 🏗️ Architecture

```
├── backend/           # Flask API server
│   ├── backend.py     # Main backend with EMD integration
│   ├── streaming_api.py # Real-time streaming endpoints
│   └── requirements.txt # Python dependencies
├── frontend/          # React web interface
│   ├── src/
│   │   ├── components/
│   │   │   ├── ModelSelector.jsx    # Model selection UI
│   │   │   ├── MediaUploader.jsx    # File upload component
│   │   │   └── ResultsDisplay.jsx   # Results visualization
│   │   └── App.js     # Main application
│   └── package.json   # Node.js dependencies
└── docs/             # Documentation
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- AWS credentials configured
- EMD CLI installed (for local models)

1. **Install dependencies:**

Please ensure to use python=3.10

```bash
conda create -n eval-platform python=3.10 -y
conda activate eval-platform
pip install -r requirements.txt
```

2. **Configure AWS credentials:**

```bash
aws configure
# or set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_SESSION_TOKEN=your_token  # if using temporary credentials
```

3. **Start the backend:**

```bash
python run_backend.py
```

### Frontend Setup

#### Node.js install
Go to https://nodejs.org/zh-cn/download to use the codes based on your system, or use the following commands in Linux.

```bash
# Download and install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# in lieu of restarting the shell
\. "$HOME/.nvm/nvm.sh"

# Download and install Node.js:
nvm install 22

# Verify the Node.js version:
node -v # Should print "v22.18.0".
nvm current # Should print "v22.18.0".

# Verify npm version:
npm -v # Should print "10.9.3".
```

### Backend Setup

1. **Install dependencies:**

```bash
cd frontend
npm install
```

2. **Start the development server:**

```bash
npm start
```

3. **Access the application:**

- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

## 📖 Usage Guide

### Model Selection

The platform supports two types of models:

**API Models (AWS Bedrock):**
- Claude 4 (`claude4`)
- Nova (`nova`)

**EMD Local Models:**
- Qwen2-VL-7B (`qwen2-vl-7b`)
- Qwen2.5-VL-32B (`qwen2.5-vl-32b`)
- Gemma-3-4B (`gemma-3-4b`)
- UI-TARS-1.5-7B (`ui-tars-1.5-7b`)

### Deploying EMD Models

Before using EMD models, you need to deploy them:

```bash
# Deploy a model
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.12xlarge \
           --engine-type vllm \
           --service-type sagemaker_realtime \
           --model-tag dev

# Check deployment status
emd status

# List available models
emd list-models
```

### Inference Modes

**1. Streaming Mode (Real-time)**
- Real-time response generation
- Live progress updates
- Single model inference

**2. Batch Mode (Evaluation)**
- Multiple model comparison
- Parallel processing
- Comprehensive result analysis

### Media Processing

**Supported formats:**
- Images: PNG, JPEG, GIF, WebP
- Videos: MP4, AVI, MOV (automatically extracts frames)

**Processing features:**
- Automatic frame extraction from videos
- Base64 encoding for API compatibility
- Multi-image batch processing

## 🔧 API Endpoints

### Bedrock Models
- `POST /api/claude4` - Claude 4 inference
- `POST /api/nova` - Nova inference

### EMD Models
- `POST /api/emd/<model_key>` - EMD model inference
- `GET /api/emd/status` - Check EMD deployment status
- `GET /api/emd/models` - List available EMD models

### Multi-Model
- `POST /api/multi-inference` - Batch inference across multiple models

### Streaming
- `POST /api/stream/<model_name>` - Real-time streaming inference

## 📊 Logging and Monitoring

The platform provides comprehensive logging with emoji indicators:

```
🚀 Starting EMD inference for model Qwen2-VL-7B-Instruct
🔍 Checking EMD OpenAI client availability...
🔍 Checking EMD SageMaker client availability...
🖼️ Processing 2 images for EMD model Qwen2-VL-7B-Instruct
🔥 Calling EMD OpenAI API for qwen2-vl-7b/dev...
✅ EMD OpenAI API call completed for qwen2-vl-7b
❌ No EMD client available for Qwen2-VL-7B-Instruct
```

## 🛠️ Configuration

### Backend Configuration

Key configuration options in `backend.py`:

```python
# EMD model mapping
EMD_MODELS = {
    'qwen2-vl-7b': 'Qwen2-VL-7B-Instruct',
    'qwen2.5-vl-32b': 'Qwen2.5-VL-32B-Instruct',
    'gemma-3-4b': 'gemma-3-4b-it',
    'ui-tars-1.5-7b': 'UI-TARS-1.5-7B'
}

# API endpoints
EMD_OPENAI_ENDPOINT = "https://api.emd.ai/v1/emd/openai"
EMD_SAGEMAKER_ENDPOINT = "https://api.emd.ai/v1/sagemaker"
```

### Frontend Configuration

Model options in `ModelSelector.jsx`:

```javascript
const apiModels = [
  { label: 'Claude 4', value: 'claude4' },
  { label: 'Nova', value: 'nova' }
];

const emdModels = [
  { label: 'Qwen2-VL-7B-Instruct', value: 'qwen2-vl-7b' },
  { label: 'Qwen2.5-VL-32B-Instruct', value: 'qwen2.5-vl-32b' },
  { label: 'Gemma-3-4B-IT', value: 'gemma-3-4b' },
  { label: 'UI-TARS-1.5-7B', value: 'ui-tars-1.5-7b' }
];
```

## 🐛 Troubleshooting

### Common Issues

**1. EMD Model Not Deployed**
```
Error: EMD model Qwen2-VL-7B-Instruct is not deployed yet
Solution: Deploy the model using emd deploy command
```

**2. AWS Token Expired**
```
Error: The security token included in the request is expired
Solution: Refresh your AWS credentials
```

**3. Mixed Model Selection Not Working**
```
Issue: Cannot select both API and EMD models
Solution: Fixed in ModelSelector.jsx - ensure latest version
```

**4. Batch Inference Fails**
```
Issue: "No EMD client available" error in batch mode
Solution: Check EMD deployment status with emd status
```

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Log Files

- Backend logs: `backend.log`
- Frontend logs: Browser console
- EMD logs: Check with `emd logs`

## 🔒 Security

- Never commit AWS credentials to version control
- Use environment variables for sensitive configuration
- Implement proper CORS settings for production
- Validate all user inputs before processing

## 🚦 Development

### Running Tests

```bash
# Test all fixes
python test_all_fixes.py

# Check specific functionality
curl -X POST http://localhost:5000/api/emd/qwen2-vl-7b \
  -H "Content-Type: application/json" \
  -d '{"text": "test", "frames": [], "mediaType": "image"}'
```

### Code Structure

**Backend (`backend.py`):**
- EMD client initialization
- Model inference functions
- Error handling and logging
- API endpoint definitions

**Frontend (`App.js`):**
- Model selection logic
- Media upload handling
- Results display
- Error management

## 📈 Performance

- **Concurrent Processing**: Multiple models can run in parallel
- **Streaming**: Real-time response generation
- **Caching**: Base64 encoding cached for repeated requests
- **Error Recovery**: Graceful fallback between client types

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 📞 Support

For issues and questions:
- Check the troubleshooting section
- Review log files for error details
- Ensure AWS credentials are valid
- Verify EMD model deployment status

---

**Built with ❤️ for multimodal AI inference**