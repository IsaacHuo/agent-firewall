#!/usr/bin/env bash
# Stop all Agent Firewall services
# Usage: ./scripts/stop-all.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[stop-all]${NC} $*"; }
ok()  { echo -e "${GREEN}[stop-all]${NC} $*"; }

stopped=0

# Kill by saved PIDs
if [[ -d "$RUN_DIR" ]]; then
  for pidfile in "$RUN_DIR"/*.pid; do
    [[ -f "$pidfile" ]] || continue
    pid=$(cat "$pidfile")
    name=$(basename "$pidfile" .pid)
    if kill -0 "$pid" 2>/dev/null; then
      log "Stopping $name (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      stopped=$((stopped + 1))
    fi
    rm -f "$pidfile"
  done
fi

# Also kill by port as a safety net
for port in 9090 9091 5173; do
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    log "Killing process on port $port..."
    echo "$pids" | xargs kill -9 2>/dev/null || true
    stopped=$((stopped + 1))
  fi
done

rmdir "$RUN_DIR" 2>/dev/null || true

echo ""
if [[ $stopped -gt 0 ]]; then
  ok "All services stopped."
else
  ok "No running services found."
fi
