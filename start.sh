#!/bin/bash

# Default ports
BACKEND_PORT=5000
FRONTEND_PORT=3000

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-port)
            BACKEND_PORT="$2"
            shift 2
            ;;
        --frontend-port)
            FRONTEND_PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: ./start.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend-port PORT   Set backend port (default: 5000)"
            echo "  --frontend-port PORT  Set frontend port (default: 3000)"
            echo "  -h, --help            Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🚀 Starting Performance Evaluation Platform..."
echo "   Backend port: $BACKEND_PORT"
echo "   Frontend port: $FRONTEND_PORT"

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ] || [ ! -f "frontend/node_modules/react/package.json" ]; then
    echo "⚠️  Frontend dependencies not found. Run setup first:"
    echo "  ./setup.sh"
    ./setup.sh
fi

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
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port $BACKEND_PORT --reload > ../logs/backend.out 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"
cd ..

# Wait a moment for backend to initialize
sleep 3

# Start frontend in background
echo "2. Starting frontend..."
cd frontend
PORT=$FRONTEND_PORT npm start > ../logs/frontend.out 2>&1 &
FRONTEND_PID=$!
echo "✓ Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "🌐 Platform is starting up..."
echo "🖥️  Frontend: http://localhost:$FRONTEND_PORT"
echo "📊 Backend: http://localhost:$BACKEND_PORT"
echo "📚 API Docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "📋 Logs:"
echo "   Frontend: logs/frontend.out"
echo "   Backend: logs/backend.out"
echo ""
echo "Press Ctrl+C to stop the platform"

# Wait for user to stop the platform
wait
