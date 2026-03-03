#!/usr/bin/env bash
# Start all Agent Firewall services
# Usage: ./scripts/start-all.sh [--no-gateway] [--no-open]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIREWALL_DIR="$ROOT/extensions/agent-firewall"
FRONTEND_DIR="$FIREWALL_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

log()  { echo -e "${CYAN}[start-all]${NC} $*"; }
ok()   { echo -e "${GREEN}[start-all]${NC} $*"; }
warn() { echo -e "${YELLOW}[start-all]${NC} $*"; }
err()  { echo -e "${RED}[start-all]${NC} $*" >&2; }

# --- Parse flags ---
SKIP_GATEWAY=false
SKIP_OPEN=false
for arg in "$@"; do
  case "$arg" in
    --no-gateway) SKIP_GATEWAY=true ;;
    --no-open)    SKIP_OPEN=true ;;
    -h|--help)
      echo "Usage: $0 [--no-gateway] [--no-open]"
      echo "  --no-gateway  Skip OpenClaw Gateway (for frontend-only dev)"
      echo "  --no-open     Don't auto-open browser"
      exit 0 ;;
  esac
done

# Kill anything already on our ports
cleanup_ports() {
  local ports=(9090 9091)
  $SKIP_GATEWAY || ports+=(18789)
  for port in "${ports[@]}"; do
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      log "Killing existing process on port $port"
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
  done
  sleep 0.5
}

# Wait for a port to become available (up to N seconds)
wait_for_port() {
  local port=$1 timeout=${2:-10} elapsed=0
  while ! lsof -ti :"$port" &>/dev/null; do
    sleep 0.5
    elapsed=$((elapsed + 1))
    if [[ $elapsed -ge $((timeout * 2)) ]]; then
      return 1
    fi
  done
}

# Wait for HTTP 200 on a URL (up to N seconds)
wait_for_http() {
  local url=$1 timeout=${2:-15} elapsed=0
  while ! curl -sf --max-time 2 "$url" >/dev/null 2>&1; do
    sleep 0.5
    elapsed=$((elapsed + 1))
    if [[ $elapsed -ge $((timeout * 2)) ]]; then
      return 1
    fi
  done
}

# --- Pre-checks ---
HAS_GATEWAY=false
if ! $SKIP_GATEWAY; then
  if command -v openclaw &>/dev/null; then
    HAS_GATEWAY=true
  else
    warn "openclaw CLI not found — skipping Gateway. Install with: npm i -g openclaw"
  fi
fi

if [[ ! -f "$FIREWALL_DIR/.venv/bin/uvicorn" ]]; then
  log "Setting up Python virtual environment..."
  (cd "$FIREWALL_DIR" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

# --- Start ---
cleanup_ports

ALL_PIDS=()

# 1) Gateway (optional)
PID_GATEWAY=""
if $HAS_GATEWAY; then
  log "Starting OpenClaw Gateway on :18789..."
  openclaw gateway run --bind loopback --port 18789 --force > /tmp/openclaw-gateway.log 2>&1 &
  PID_GATEWAY=$!
  ALL_PIDS+=("$PID_GATEWAY")

  if wait_for_port 18789 8; then
    ok "Gateway ready (PID $PID_GATEWAY)"
  else
    warn "Gateway slow to start — check /tmp/openclaw-gateway.log"
  fi
fi

# 2) Backend
log "Starting Agent Firewall Backend on :9090..."
(cd "$FIREWALL_DIR" && mkdir -p audit && .venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 9090) &
PID_BACKEND=$!
ALL_PIDS+=("$PID_BACKEND")

if wait_for_http "http://localhost:9090/api/stats" 15; then
  ok "Backend ready (PID $PID_BACKEND)"
else
  warn "Backend slow to respond — may still be loading"
fi

# 3) Frontend
log "Starting Unified Console on :9091..."
(cd "$FRONTEND_DIR" && npx vite --port 9091 --host) &
PID_FRONTEND=$!
ALL_PIDS+=("$PID_FRONTEND")

if wait_for_port 9091 10; then
  ok "Frontend ready (PID $PID_FRONTEND)"
else
  warn "Frontend slow to start"
fi

# Save PIDs for stop script
mkdir -p "$ROOT/.run"
[[ -n "$PID_GATEWAY" ]] && echo "$PID_GATEWAY" > "$ROOT/.run/gateway.pid"
echo "$PID_BACKEND"  > "$ROOT/.run/backend.pid"
echo "$PID_FRONTEND" > "$ROOT/.run/frontend.pid"

echo ""
ok "════════════════════════════════════════════"
ok " Agent Firewall — All services running"
ok "════════════════════════════════════════════"
$HAS_GATEWAY && \
ok " Gateway (WS RPC):    ws://localhost:18789/ws"
ok " Backend (FastAPI):   http://localhost:9090"
ok " Unified Console:     http://localhost:9091"
ok "════════════════════════════════════════════"
echo ""
log "Stop with: ./scripts/stop-all.sh"
log "Press Ctrl+C to stop all services"

# Auto-open browser
if ! $SKIP_OPEN && command -v open &>/dev/null; then
  open "http://localhost:9091"
fi

# Wait for all background processes; forward Ctrl+C
cleanup() {
  log "Shutting down..."
  for pid in "${ALL_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup INT TERM
wait
