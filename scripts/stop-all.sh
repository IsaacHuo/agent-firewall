#!/usr/bin/env bash
# Stop Agent Firewall services
# Usage: ./scripts/stop-all.sh

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[stop-all]${NC} $*"; }
ok()  { echo -e "${GREEN}[stop-all]${NC} $*"; }

stopped=0

# Kill by saved PIDs (graceful SIGTERM first)
if [[ -d "$RUN_DIR" ]]; then
  for pidfile in "$RUN_DIR"/*.pid; do
    [[ -f "$pidfile" ]] || continue
    pid=$(cat "$pidfile")
    name=$(basename "$pidfile" .pid)
    if kill -0 "$pid" 2>/dev/null; then
      log "Stopping $name (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      # Wait briefly for graceful shutdown
      for _ in 1 2 3 4; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      # Force kill if still alive
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
      stopped=$((stopped + 1))
    fi
    rm -f "$pidfile"
  done
fi

# Also kill gateway process by name
pkill -f "openclaw gateway run" 2>/dev/null && { log "Stopped openclaw gateway"; stopped=$((stopped + 1)); } || true

# Kill uvicorn / vite processes by name (handles --reload workers too)
pkill -f "uvicorn src.main:app" 2>/dev/null && { log "Stopped uvicorn workers"; stopped=$((stopped + 1)); } || true
pkill -f "vite --port 9091" 2>/dev/null && { log "Stopped vite"; stopped=$((stopped + 1)); } || true
sleep 0.3

# Safety net: kill by port
for port in 9090 9091 18789; do
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    log "Killing remaining process on port $port..."
    echo "$pids" | xargs kill -9 2>/dev/null || true
    stopped=$((stopped + 1))
  fi
done

rm -rf "$RUN_DIR" 2>/dev/null || true

echo ""
if [[ $stopped -gt 0 ]]; then
  ok "All services stopped ($stopped processes)."
else
  ok "No running services found."
fi
