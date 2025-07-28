#!/bin/bash

echo "🚀 Setting up Multimodal Inference Platform"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✓ Python found: $python_version"
else
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check Node.js version
node_version=$(node --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✓ Node.js found: $node_version"
else
    echo "❌ Node.js not found. Please install Node.js 16+"
    exit 1
fi

# Setup backend
echo ""
echo "📦 Setting up backend..."
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install EMD CLI
echo "Installing EMD CLI..."
pip install emd-cli

echo "✓ Backend setup complete!"

# Setup frontend
echo ""
echo "🎨 Setting up frontend..."
cd ../frontend

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
npm install

echo "✓ Frontend setup complete!"

# Check AWS credentials
echo ""
echo "🔐 Checking AWS configuration..."
cd ..

if aws sts get-caller-identity >/dev/null 2>&1; then
    echo "✓ AWS credentials configured"
else
    echo "⚠️  AWS credentials not configured. Please run:"
    echo "   aws configure"
    echo "   or set environment variables:"
    echo "   export AWS_ACCESS_KEY_ID=your_key"
    echo "   export AWS_SECRET_ACCESS_KEY=your_secret"
fi

# EMD setup
echo ""
echo "🤖 EMD setup..."
if command -v emd >/dev/null 2>&1; then
    echo "✓ EMD CLI installed"
    echo "To initialize EMD, run: emd bootstrap"
else
    echo "⚠️  EMD CLI not found in PATH. Make sure to activate the virtual environment."
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the platform:"
echo "1. Backend:"
echo "   cd backend && source venv/bin/activate && python backend.py"
echo "2. Frontend (in another terminal):"
echo "   cd frontend && npm start"
echo "3. Access: http://localhost:3000"
echo ""
echo "For EMD models, deploy them first:"
echo "   emd deploy --model-id Qwen2-VL-7B-Instruct --instance-type g5.12xlarge --engine-type vllm --service-type sagemaker_realtime --model-tag dev"