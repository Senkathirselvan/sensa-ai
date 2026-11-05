#!/usr/bin/env bash
# ==============================================================================
# Sensa AI - Graceful Shutdown Script
# Terminates all running microservice processes
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"

echo "🛑 Stopping Sensa AI Platform microservices..."

for pidfile in "${LOG_DIR}"/*.pid; do
  if [ -f "$pidfile" ]; then
    PID=$(cat "$pidfile")
    NAME=$(basename "$pidfile" .pid)
    if kill -0 "$PID" 2>/dev/null; then
      echo "  • Stopping $NAME (PID: $PID)..."
      kill "$PID" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
done

echo "✓ Graceful shutdown complete."
