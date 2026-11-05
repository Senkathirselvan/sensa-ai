#!/bin/bash
cd /home/senkathir-selvan/job-apply-agent
exec /home/senkathir-selvan/job-apply-agent/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8002

