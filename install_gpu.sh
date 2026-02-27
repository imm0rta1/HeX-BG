#!/bin/bash
echo "--- Removing old CPU versions ---"
/opt/venv/bin/pip uninstall -y torch torchvision torchaudio onnxruntime rembg

echo "--- Installing PyTorch CUDA 12.1 (This takes a few minutes) ---"
/opt/venv/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo "--- Installing ONNX GPU and rembg ---"
/opt/venv/bin/pip install onnxruntime-gpu rembg[gpu]

echo "--- Restarting App ---"
bash restart_all.sh
