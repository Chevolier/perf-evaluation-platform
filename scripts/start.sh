#!/bin/bash
# Startup script for the new Inference Platform

set -e  # Exit on any error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 Starting New Inference Platform"
echo "📁 Project root: $PROJECT_ROOT"

# Set environment (default to development)
ENVIRONMENT="${ENVIRONMENT:-development}"
echo "📊 Environment: $ENVIRONMENT"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not available"
    exit 1
fi

# Check if required dependencies are installed
echo "🔍 Checking dependencies..."
python3 -c "import flask" 2>/dev/null || {
    echo "⚠️  Flask not found. Installing dependencies..."
    pip3 install -r requirements_new.txt
}

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/logs
mkdir -p data/benchmarks/by_model
mkdir -p data/benchmarks/by_timestamp
mkdir -p data/temp

# Set Python path
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
export ENVIRONMENT="$ENVIRONMENT"

echo "▶️  Starting server..."
echo "-" | head -c 50

# Run the new application
python3 run_new.py "$ENVIRONMENT"