#!/bin/bash
export LD_LIBRARY_PATH=/usr/lib/wsl/drivers/nvaci.inf_amd64_011de684f165cb6f:$LD_LIBRARY_PATH
pkill -9 -f 'uvicorn'
pkill -9 -f 'rq worker'
pkill -9 -f 'vite'
sleep 2
source /opt/venv/bin/activate || source /opt/venv-a0/bin/activate
export PYTHONPATH=$(pwd)
nohup python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
nohup rq worker default upscale > worker.log 2>&1 &
cd frontend/web-ui
nohup npm run dev -- --host 0.0.0.0 --port 5173 > ui.log 2>&1 &
