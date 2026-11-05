#!/usr/bin/env bash
# ==============================================================================
# Sensa AI - Local Development Startup Script
# Boots all 5 microservices across their dedicated ports
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

echo "=========================================================="
echo "🚀 Booting Sensa AI Autonomous Multi-Agent Platform"
echo "=========================================================="

# 1. Job Find Agent (Port 8000)
echo "▶ Starting Job Find Agent (Port 8000)..."
cd "${PROJECT_ROOT}/job-find-agent"
if [ -d "venv" ]; then source venv/bin/activate; fi
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > "${LOG_DIR}/job-find.log" 2>&1 &
echo $! > "${LOG_DIR}/job-find.pid"

# 2. Resume Prep Agent (Port 8001)
echo "▶ Starting Resume Prep Agent (Port 8001)..."
cd "${PROJECT_ROOT}/resume-prep-agent"
if [ -d "venv" ]; then source venv/bin/activate; fi
uvicorn backend.app.main:app --host 0.0.0.0 --port 8001 > "${LOG_DIR}/resume-prep.log" 2>&1 &
echo $! > "${LOG_DIR}/resume-prep.pid"

# 3. Job Apply Agent (Port 8002)
echo "▶ Starting Job Apply Agent (Port 8002)..."
cd "${PROJECT_ROOT}/job-apply-agent"
if [ -d "venv" ]; then source venv/bin/activate; fi
uvicorn backend.app.main:app --host 0.0.0.0 --port 8002 > "${LOG_DIR}/job-apply.log" 2>&1 &
echo $! > "${LOG_DIR}/job-apply.pid"

# 4. Manager Agent (Port 8005)
echo "▶ Starting Executive Manager Agent (Port 8005)..."
cd "${PROJECT_ROOT}/manager-agent"
if [ -d "venv" ]; then source venv/bin/activate; fi
uvicorn backend.app.main:app --host 0.0.0.0 --port 8005 > "${LOG_DIR}/manager.log" 2>&1 &
echo $! > "${LOG_DIR}/manager.pid"

# 5. Agent UI (Port 3001)
echo "▶ Starting Sensa AI Frontend (Port 3001)..."
cd "${PROJECT_ROOT}/agent-ui"
npm run dev -- --port 3001 --host 0.0.0.0 > "${LOG_DIR}/agent-ui.log" 2>&1 &
echo $! > "${LOG_DIR}/agent-ui.pid"

echo "=========================================================="
echo "✅ All Sensa AI microservices successfully launched!"
echo "   - Web UI:         http://localhost:3001"
echo "   - Manager Agent:  http://localhost:8005/docs"
echo "   - Apply Agent:    http://localhost:8002/docs"
echo "   - Resume Agent:   http://localhost:8001/docs"
echo "   - Job Find Agent: http://localhost:8000/docs"
echo "   - Logs Directory: ${LOG_DIR}"
echo "=========================================================="
