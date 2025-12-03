#!/bin/bash

echo "🚀 Setting up Performance Evaluation Platform"
echo "=========================================="

echo "🚀 Setting up backend environment ..."

cd backend
# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add uv to PATH for this session
    export PATH="\$HOME/.local/bin:\$PATH"
    source ~/.local/bin/env
    
    # Check again after installation
    if ! command -v uv &> /dev/null; then
        echo "❌ Failed to install uv. Please install it manually from https://github.com/astral-sh/uv"
        exit 1
    fi
    
    echo "✅ uv installed successfully"
fi

echo "✅ Prerequisites check passed"

# Install dependencies
echo "📦 Installing dependencies..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with Python 3.10..."
    uv venv --python 3.10
fi

source .venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
uv pip install --upgrade pip
uv pip install -r requirements.txt
uv pip install -e evalscope

echo "✓ Backend setup complete!"

# Setup frontend
echo ""
echo "🎨 Setting up frontend..."

# Install Node.js
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

# Check Node.js version
node_version=$(node --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✓ Node.js found: $node_version"
else
    echo "❌ Node.js not found. Please install Node.js 16+"
    exit 1
fi

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


echo ""
echo "🎉 Setup complete!"
echo ""
echo "🚀 Starting the platform..."

# Create logs directory if it doesn't exist
mkdir -p logs

echo "Start the platform by running ./start.sh"