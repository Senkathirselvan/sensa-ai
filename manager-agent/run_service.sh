#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

exec python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8005

