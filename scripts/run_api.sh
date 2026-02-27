#!/bin/bash
export LD_LIBRARY_PATH=/usr/lib/wsl/drivers/nvaci.inf_amd64_011de684f165cb6f:$LD_LIBRARY_PATH
cd "$(dirname "$0")/.."
export PYTHONPATH=$PYTHONPATH:$(pwd)
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000