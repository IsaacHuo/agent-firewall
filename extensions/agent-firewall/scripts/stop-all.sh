#!/bin/bash
# Agent Firewall — Stop All Services (Gateway + Backend + Frontend)
# Usage: ./scripts/stop-all.sh

echo "🛡️  Agent Firewall — Stopping All Services"
echo "============================================"

# Stop Gateway (port 18789)
echo "🛑 Stopping OpenClaw Gateway (port 18789)..."
if openclaw gateway stop 2>/dev/null; then
    echo "   ✅ Gateway stopped"
else
    echo "   ℹ️  Gateway not running"
fi

# Stop Backend (port 9090)
echo "🛑 Stopping Backend (port 9090)..."
BACKEND_PIDS=$(lsof -ti :9090 2>/dev/null || true)
if [ -n "$BACKEND_PIDS" ]; then
    echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null || true
    echo "   ✅ Backend stopped"
else
    echo "   ℹ️  Backend not running"
fi

# Stop Frontend (port 9091)
echo "🛑 Stopping Frontend Dashboard (port 9091)..."
FRONTEND_PIDS=$(lsof -ti :9091 2>/dev/null || true)
if [ -n "$FRONTEND_PIDS" ]; then
    echo "$FRONTEND_PIDS" | xargs kill -9 2>/dev/null || true
    echo "   ✅ Frontend stopped"
else
    echo "   ℹ️  Frontend not running"
fi

# Also kill any orphan processes
echo "🔄 Cleaning up any orphan processes..."
pkill -f "openclaw gateway" 2>/dev/null || true
pkill -f "uvicorn src.main:app" 2>/dev/null || true
pkill -f "vite.*9091" 2>/dev/null || true

echo ""
echo "============================================"
echo "✅ All services stopped"
