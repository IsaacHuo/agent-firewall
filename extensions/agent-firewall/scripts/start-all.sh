#!/bin/bash
# Agent Firewall — Start All Services (Backend + Frontend + Gateway)
# Usage: ./scripts/start-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo "🛡️  Agent Firewall — Starting All Services"
echo "============================================"

# Detect Upstream Gateway Port
echo "🔍 Detecting OpenClaw Gateway..."
# Check port 18789 (default)
if lsof -i :18789 -sTCP:LISTEN >/dev/null; then
    echo "   ✅ Found Gateway on port 18789"
    export AF_UPSTREAM_PORT=18789
# Check port 19001 (alternative/dev)
elif lsof -i :19001 -sTCP:LISTEN >/dev/null; then
    echo "   ✅ Found Gateway on port 19001"
    export AF_UPSTREAM_PORT=19001
else
    echo "   ⚠️  Gateway not found on standard ports (18789, 19001)."
    echo "       Make sure OpenClaw Gateway is running."
    echo "       Defaulting to 18789."
    export AF_UPSTREAM_PORT=18789
fi

# Check if venv exists and is valid
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/pip" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "📦 Installing backend dependencies..."
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
fi

# Kill existing processes gracefully
echo "🔄 Stopping existing services..."
# Backend
pids_backend=$(lsof -ti :9090 || true)
if [ -n "$pids_backend" ]; then
    echo "   Stopping backend (port 9090)..."
    kill $pids_backend 2>/dev/null || true
    sleep 1
    # Force kill if still running
    if lsof -ti :9090 >/dev/null; then
        echo "   Force killing backend..."
        kill -9 $pids_backend 2>/dev/null || true
    fi
fi

# Frontend
pids_frontend=$(lsof -ti :9091 || true)
if [ -n "$pids_frontend" ]; then
    echo "   Stopping frontend (port 9091)..."
    kill $pids_frontend 2>/dev/null || true
    sleep 1
    if lsof -ti :9091 >/dev/null; then
        echo "   Force killing frontend..."
        kill -9 $pids_frontend 2>/dev/null || true
    fi
fi

# Start OpenClaw Gateway (port 18789)
echo "🚀 Starting OpenClaw Gateway (port 18789)..."
openclaw gateway --port 18789 > /tmp/agent-firewall-gateway.log 2>&1 &
GATEWAY_PID=$!
echo "   Gateway PID: $GATEWAY_PID"

# Wait for gateway to start (check if port is listening)
for i in $(seq 1 30); do
    if lsof -ti :18789 > /dev/null 2>&1; then
        break
    fi
    sleep 1
done
if ! lsof -ti :18789 > /dev/null 2>&1; then
    echo "❌ Gateway failed to start. Check /tmp/agent-firewall-gateway.log"
    exit 1
fi
echo "   ✅ Gateway healthy"

# Start Backend (port 9090)
echo "🚀 Starting Backend (port 9090)..."
cd "$PROJECT_DIR"
# Pass the detected upstream port to the backend
# Using nohup to detach, redirect output to logs
nohup "$VENV_DIR/bin/uvicorn" src.main:app --host 127.0.0.1 --port 9090 --reload > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"
echo "   Upstream Port: $AF_UPSTREAM_PORT"

# Wait for backend to start (Loop check with timeout)
echo "⏳ Waiting for backend to become healthy..."
max_retries=15
count=0
backend_ready=false

while [ $count -lt $max_retries ]; do
    if curl -s http://localhost:9090/health > /dev/null; then
        backend_ready=true
        break
    fi
    sleep 1
    count=$((count+1))
    echo -n "."
done
echo ""

if [ "$backend_ready" = false ]; then
    echo "❌ Backend failed to start within $max_retries seconds."
    echo "   Check logs: $LOG_DIR/backend.log"
    echo "   Last 10 lines of log:"
    tail -n 10 "$LOG_DIR/backend.log"
    exit 1
fi
echo "   ✅ Backend healthy"

# Start Frontend (port 9091)
echo "🚀 Starting Frontend Dashboard (port 9091)..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Start Vite
nohup npx vite --port 9091 --host > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

# Wait a moment for frontend to initialize
sleep 2

echo ""
echo "============================================"
echo "✅ All services started successfully!"
echo ""
echo "📍 Access Points:"
echo "   Gateway:      http://localhost:18789"
echo "   Backend API:  http://localhost:9090"
echo "   Dashboard:    http://localhost:9091"
echo ""
echo "📄 Logs:"
echo "   Backend:  $LOG_DIR/backend.log"
echo "   Frontend: $LOG_DIR/frontend.log"
echo ""
echo "🛑 To stop all manually:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
