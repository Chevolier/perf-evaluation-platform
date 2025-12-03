#!/bin/bash

echo "🚀 Starting Performance Evaluation Platform..."

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
python run_backend.py > ../logs/backend.out 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"
cd ..

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
echo "🖥️  Frontend: http://localhost:3000"
echo "📊 Backend: http://localhost:5000"
echo ""
echo "📋 Logs:"
echo "   Frontend: logs/frontend.out"
echo "   Backend: logs/backend.out"
echo ""
echo "Press Ctrl+C to stop the platform"

# Wait for user to stop the platform
wait