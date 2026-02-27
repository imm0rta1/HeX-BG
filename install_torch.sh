#!/bin/bash
/opt/venv/bin/pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
bash restart_all.sh
