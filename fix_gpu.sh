#!/bin/bash
echo "--- Removing slow CPU engines ---"
/opt/venv/bin/pip uninstall -y onnxruntime

echo "--- Installing fast GPU engines ---"
/opt/venv/bin/pip install onnxruntime-gpu --extra-index-url https://download.pytorch.org/whl/cu121

echo "--- Restarting Services ---"
bash restart_all.sh
