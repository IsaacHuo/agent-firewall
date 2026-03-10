#!/bin/bash
# Agent Firewall — Start All Services (Backend + Frontend + Gateway)
# Usage: ./scripts/start-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"

echo "🛡️  Agent Firewall — Starting All Services"
echo "============================================"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
fi

# Kill existing processes
echo "🔄 Stopping existing services..."
lsof -ti :9090 | xargs kill -9 2>/dev/null || true
lsof -ti :9091 | xargs kill -9 2>/dev/null || true
openclaw gateway stop 2>/dev/null || true
sleep 1

# Start OpenClaw Gateway (port 18789)
echo "🚀 Starting OpenClaw Gateway (port 18789)..."
openclaw gateway --port 18789 > /tmp/agent-firewall-gateway.log 2>&1 &
GATEWAY_PID=$!
echo "   Gateway PID: $GATEWAY_PID"

# Wait for gateway to start (check if port is listening)
for i in $(seq 1 10); do
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
"$VENV_DIR/bin/uvicorn" src.main:app --host 127.0.0.1 --port 9090 --reload > /tmp/agent-firewall-backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend to start (Feishu WebSocket init takes time)
for i in $(seq 1 15); do
    if curl -s http://localhost:9090/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done
if ! curl -s http://localhost:9090/health > /dev/null 2>&1; then
    echo "❌ Backend failed to start. Check /tmp/agent-firewall-backend.log"
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
npx vite --port 9091 --host > /tmp/agent-firewall-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

# Wait for frontend to start
sleep 3

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
echo "   Gateway:  /tmp/agent-firewall-gateway.log"
echo "   Backend:  /tmp/agent-firewall-backend.log"
echo "   Frontend: /tmp/agent-firewall-frontend.log"
echo ""
echo "🛑 To stop all: ./scripts/stop-all.sh"
