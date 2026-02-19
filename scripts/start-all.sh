#!/usr/bin/env bash
# Start all Agent Firewall services
# Usage: ./scripts/start-all.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIREWALL_DIR="$ROOT/extensions/agent-firewall"
FRONTEND_DIR="$FIREWALL_DIR/frontend"
UI_DIR="$ROOT/ui"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[start-all]${NC} $*"; }
ok()  { echo -e "${GREEN}[start-all]${NC} $*"; }
err() { echo -e "${RED}[start-all]${NC} $*" >&2; }

# Kill anything already on our ports
cleanup_ports() {
  for port in 9090 9091 5173; do
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      log "Killing existing process on port $port"
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
  done
  sleep 1
}

# --- Pre-checks ---
if [[ ! -f "$FIREWALL_DIR/.venv/bin/uvicorn" ]]; then
  err "Python venv not found. Run: cd $FIREWALL_DIR && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

if [[ ! -d "$UI_DIR/node_modules" ]]; then
  log "Installing Gateway UI dependencies..."
  (cd "$UI_DIR" && npm install)
fi

# --- Start ---
cleanup_ports

log "Starting Agent Firewall Backend on :9090..."
(cd "$FIREWALL_DIR" && mkdir -p audit && .venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 9090) &
PID_BACKEND=$!

log "Starting Agent Firewall Dashboard on :9091..."
(cd "$FRONTEND_DIR" && npx vite --port 9091 --host) &
PID_FRONTEND=$!

log "Starting Gateway Control Panel on :5173..."
(cd "$UI_DIR" && npx vite --port 5173 --host) &
PID_GATEWAY=$!

# Save PIDs for stop script
mkdir -p "$ROOT/.run"
echo "$PID_BACKEND"  > "$ROOT/.run/backend.pid"
echo "$PID_FRONTEND" > "$ROOT/.run/frontend.pid"
echo "$PID_GATEWAY"  > "$ROOT/.run/gateway.pid"

# Wait for services to be ready
sleep 3

echo ""
ok "============================================"
ok " All services started!"
ok "============================================"
ok " Backend (FastAPI):     http://localhost:9090"
ok " Firewall Dashboard:   http://localhost:9091"
ok " Gateway Control Panel: http://localhost:5173"
ok "============================================"
echo ""
log "PIDs saved to .run/  — stop with: ./scripts/stop-all.sh"
log "Press Ctrl+C to stop all services"

# Wait for all background processes; forward Ctrl+C
trap 'kill $PID_BACKEND $PID_FRONTEND $PID_GATEWAY 2>/dev/null; exit 0' INT TERM
wait
