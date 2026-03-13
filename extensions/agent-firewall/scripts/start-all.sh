#!/bin/bash
# Agent Firewall — Start All Services (Backend + Frontend + Gateway)
# Usage: cd extensions/agent-firewall && ./scripts/start-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$PROJECT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"

discover_gateway_tokens() {
        node - <<'NODE'
const fs = require('fs');
const os = require('os');
const path = require('path');

const files = [
    path.join(os.homedir(), '.agent-shield-dev', 'agent-shield.json'),
    path.join(os.homedir(), '.openclaw', 'openclaw.json'),
    path.join(os.homedir(), '.agent-shield', 'agent-shield.json'),
];

const seen = new Set();
for (const file of files) {
    if (fs.existsSync(file) === false) continue;
    let parsed;
    try {
        parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
        continue;
    }
    const gateway = parsed && parsed.gateway ? parsed.gateway : {};
    const auth = gateway && gateway.auth ? gateway.auth : {};
    const token = typeof auth.token === 'string' ? auth.token.trim() : '';
    if (!token) continue;
    if (seen.has(token)) continue;
    seen.add(token);
    const port = Number(gateway.port || 18789);
    process.stdout.write(`${token}|${port}|${file}\n`);
}
NODE
}

probe_gateway_auth() {
        local token="$1"
        local port="${2:-18789}"

        if [ -z "$token" ]; then
                return 1
        fi

        node - "$token" "$port" <<'NODE'
const token = process.argv[2] || '';
const port = Number(process.argv[3] || 18789);

if (!token) {
    process.exit(1);
}

const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`);
let sent = false;
const timer = setTimeout(() => {
    process.exit(2);
}, 5000);

ws.onmessage = (event) => {
    let msg;
    try {
        msg = JSON.parse(String(event.data));
    } catch {
        clearTimeout(timer);
        process.exit(1);
    }

    if (msg.type === 'event' && msg.event === 'connect.challenge' && sent === false) {
        sent = true;
        ws.send(JSON.stringify({
            type: 'req',
            id: 'auth-probe',
            method: 'connect',
            params: {
                minProtocol: 3,
                maxProtocol: 3,
                client: {
                    id: 'gateway-client',
                    version: '1.0.0',
                    platform: 'web',
                    mode: 'backend',
                },
                role: 'operator',
                scopes: ['operator.admin'],
                auth: { token },
            },
        }));
        return;
    }

    if (msg.type === 'res' && msg.id === 'auth-probe') {
        clearTimeout(timer);
        process.exit(msg.ok ? 0 : 1);
    }
};

ws.onerror = () => {
    clearTimeout(timer);
    process.exit(1);
};
NODE
}

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
TOKEN_CANDIDATES="$(discover_gateway_tokens || true)"
GATEWAY_TOKEN=""
GATEWAY_TOKEN_SOURCE=""

if [ -n "$TOKEN_CANDIDATES" ]; then
    while IFS='|' read -r token candidate_port token_source; do
        [ -z "$token" ] && continue
        if [ -z "$GATEWAY_TOKEN" ]; then
            GATEWAY_TOKEN="$token"
            GATEWAY_TOKEN_SOURCE="$token_source"
        fi
    done <<< "$TOKEN_CANDIDATES"
fi

if [ -n "$GATEWAY_TOKEN" ]; then
    echo "   🔐 Found gateway token in $GATEWAY_TOKEN_SOURCE"
else
    echo "   ⚠️  No gateway token found in local config files."
fi

if ! command -v openclaw &> /dev/null && [ ! -f "$ROOT_DIR/agent-shield.mjs" ]; then
    echo "   ⚠️  Neither openclaw CLI nor agent-shield.mjs is available."
    echo "   Skipping gateway startup."
else
    restart_gateway=false

    # Check if gateway is already running and auth is valid
    if lsof -ti :18789 > /dev/null 2>&1; then
        echo "   ✅ Gateway already running on port 18789"
        if [ -n "$GATEWAY_TOKEN" ] && probe_gateway_auth "$GATEWAY_TOKEN" 18789; then
            echo "   ✅ Gateway auth probe passed"
        else
            echo "   ⚠️  Gateway auth probe failed; restarting gateway with explicit token."
            restart_gateway=true
            pids_gateway=$(lsof -ti :18789 || true)
            if [ -n "$pids_gateway" ]; then
                kill $pids_gateway 2>/dev/null || true
                sleep 1
                if lsof -ti :18789 > /dev/null 2>&1; then
                    kill -9 $pids_gateway 2>/dev/null || true
                fi
            fi
        fi
    fi

    if ! lsof -ti :18789 > /dev/null 2>&1 || [ "$restart_gateway" = true ]; then
        gateway_cmd=()
        if command -v openclaw &> /dev/null; then
            gateway_cmd=(openclaw gateway --port 18789 --allow-unconfigured)
        else
            gateway_cmd=(node "$ROOT_DIR/agent-shield.mjs" gateway --port 18789 --allow-unconfigured)
        fi
        if [ -n "$GATEWAY_TOKEN" ]; then
            gateway_cmd+=(--token "$GATEWAY_TOKEN")
        fi

        "${gateway_cmd[@]}" > /tmp/agent-firewall-gateway.log 2>&1 &
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
            echo "   ⚠️  Gateway failed to start. Check /tmp/agent-firewall-gateway.log"
            echo "   Continuing without gateway..."
        else
            if [ -n "$GATEWAY_TOKEN" ] && probe_gateway_auth "$GATEWAY_TOKEN" 18789; then
                echo "   ✅ Gateway healthy (auth probe passed)"
            else
                echo "   ⚠️  Gateway started but auth probe failed. Check /tmp/agent-firewall-gateway.log"
            fi
        fi
    fi
    export AF_UPSTREAM_PORT=18789
fi

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
echo "   kill $BACKEND_PID $FRONTEND_PID ${GATEWAY_PID:-}"
