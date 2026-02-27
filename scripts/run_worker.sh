
export LD_LIBRARY_PATH=/usr/lib/wsl/drivers/nvaci.inf_amd64_011de684f165cb6f:$LD_LIBRARY_PATH
#!/bin/bash
cd "$(dirname "$0")/.."
export PYTHONPATH=$PYTHONPATH:$(pwd)
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
# Start RQ worker
rq worker default --url redis://localhost:6379/0
