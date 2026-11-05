#!/bin/bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Kill any existing process on port 8001
fuser -k 8001/tcp 2>/dev/null || true

if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

export PYTHONPATH="$DIR"
exec "$DIR/venv/bin/python3" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
