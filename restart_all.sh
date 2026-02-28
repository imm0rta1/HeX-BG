#!/bin/bash
export LD_LIBRARY_PATH=$(find /opt/venv/lib/python3.13/site-packages/nvidia -type d -name lib | tr "\n" ":")"$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH=/usr/lib/wsl/drivers/nvaci.inf_amd64_011de684f165cb6f:$LD_LIBRARY_PATH

pkill -9 -f "uvicorn" || true
pkill -9 -f "rq worker" || true
pkill -9 -f "vite" || true
sleep 2

. /opt/venv/bin/activate 2>/dev/null || . /opt/venv-a0/bin/activate
export PYTHONPATH=$(pwd)
export LOW_VRAM_MODE=1

redis-server --daemonize yes >/dev/null 2>&1 || true

nohup python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
nohup /opt/venv/bin/rq worker --worker-class rq.SimpleWorker default upscale > worker.log 2>&1 &

cd frontend/web-ui
nohup npm run dev -- --host > frontend.log 2>&1 &
