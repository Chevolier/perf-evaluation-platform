#!/bin/bash

echo "🚀 Setting up Model Inference Platform"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✓ Python found: $python_version"
else
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

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
pip install -r ../requirements.txt

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


echo ""
echo "🎉 Setup complete!"
echo ""
echo "🚀 Starting the platform..."

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to cleanup background processes on script exit
cleanup() {
    echo ""
    echo "🛑 Shutting down platform..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo "✓ Backend stopped"
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        echo "✓ Frontend stopped"
    fi
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Start backend in background
echo "1. Starting backend..."
cd backend
source venv/bin/activate
cd ..
python run_backend.py > logs/backend.out 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"

# Wait a moment for backend to initialize
sleep 3

# Start frontend in background
echo "2. Starting frontend..."
cd frontend
npm start > ../logs/frontend.out 2>&1 &
FRONTEND_PID=$!
echo "✓ Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "🌐 Platform is starting up..."
echo "📊 Backend: http://localhost:5000"
echo "🖥️  Frontend: http://localhost:3000"
echo ""
echo "📋 Logs:"
echo "   Backend: logs/backend.out"
echo "   Frontend: logs/frontend.out"
echo ""
echo "Press Ctrl+C to stop the platform"

# Wait for user to stop the platform
wait