# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend Setup and Running
```bash
# Setup environment (Python 3.10 required)
conda create -n eval-platform python=3.10 -y
conda activate eval-platform
pip install -r requirements.txt

# Start the backend server
python run_backend.py

# Alternative: using the setup script
./scripts/setup.sh
```

### Frontend Setup and Running  
```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

### Testing
```bash
# Test the new modular system
python tests/test_new_system.py

# Test specific functionality
python tests/test_deploy_api.py
python tests/test_emd_response.py
python tests/test_evalscope_sdk.py

# Test all fixes
python test_all_fixes.py
```

### EMD Model Deployment
```bash
# Deploy EMD models (required before using local models)
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

## Architecture Overview

This is a multimodal AI inference platform with a Flask backend and React frontend.

### Core Components

**Backend Architecture (`backend/`):**
- Modular Flask application using application factory pattern
- Service layer with dependency injection (`backend/services/`)
- API routes organized by functionality (`backend/api/routes/`)
- Configuration management with environment-specific settings
- Dual client system for EMD models (OpenAI API + SageMaker)

**Frontend Architecture (`frontend/src/`):**
- React application with Ant Design UI components
- Component structure:
  - `ModelSelector.jsx` - Model selection with API/EMD categorization
  - `MediaUploader.jsx` - File upload with video frame extraction
  - `ResultsDisplay.jsx` - Response visualization and comparison
- Proxy configuration for backend API calls

### Model Support

**EMD Local Models** (require deployment):
- Qwen2-VL-7B-Instruct (`qwen2-vl-7b`)
- Qwen2.5-VL-32B-Instruct (`qwen2.5-vl-32b`) 
- Gemma-3-4B-IT (`gemma-3-4b`)
- UI-TARS-1.5-7B (`ui-tars-1.5-7b`)

**AWS Bedrock Models** (API-based):
- Claude 4 (`claude4`)
- Nova (`nova`)

### Key Features
- **Dual Inference Modes**: Streaming (real-time) and batch (evaluation)
- **Mixed Model Selection**: Compare responses across different model types
- **Multimodal Processing**: Text, images, and video frame analysis
- **EMD Integration**: Automatic client detection (OpenAI API vs SageMaker)

## Key Configuration

### EMD Model Mapping
Located in `backend.py`:
```python
EMD_MODELS = {
    'qwen2-vl-7b': 'Qwen2-VL-7B-Instruct',
    'qwen2.5-vl-32b': 'Qwen2.5-VL-32B-Instruct',
    'gemma-3-4b': 'gemma-3-4b-it',
    'ui-tars-1.5-7b': 'UI-TARS-1.5-7B'
}
```

### API Endpoints
- EMD models: `/api/emd/<model_key>`
- Bedrock models: `/api/claude4`, `/api/nova`
- Multi-model batch: `/api/multi-inference`
- Streaming: `/api/stream/<model_name>`
- Status endpoints: `/api/emd/status`, `/api/emd/models`

## Development Notes

### AWS Configuration Required
AWS credentials must be configured for Bedrock models:
```bash
aws configure
# OR set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_SESSION_TOKEN=your_token  # if using temporary credentials
```

### EMD Prerequisites
EMD CLI must be installed and models deployed before use:
```bash
pip install easy-model-deployer
emd bootstrap  # Initialize EMD
```

### Error Handling
The platform includes comprehensive error handling:
- EMD deployment status checking
- Graceful fallbacks between client types
- Detailed logging with emoji indicators
- User-friendly error messages with deployment instructions

### Media Processing
- Automatic video frame extraction using ffmpeg
- Base64 encoding for API compatibility
- Support for PNG, JPEG, GIF, WebP images
- Support for MP4, AVI, MOV videos

### Logging
Comprehensive logging system with emoji indicators for tracking:
- 🚀 Process start
- 🔍 Client availability checks  
- 🖼️ Media processing
- 🔥 API calls
- ✅ Success operations
- ❌ Error conditions