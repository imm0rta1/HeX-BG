# High-Precision Background Removal & Upscaling Service

A production-grade, asynchronous AI pipeline for flawless image segmentation and upscaling. Built with an Agent-Centric philosophy for seamless deployment.

## 🌟 Core Architecture
* **Perfect Mode Edge Cleanup:** Custom algorithms dynamically applying solid-object snapping vs. hairy/fur logic to preserve sub-pixel details.
* **Dual Queue Architecture:** Dedicated 'Fast Lane' (8s) for standard removals and 'Heavy Lane' (30s) for Real-ESRGAN upscales to prevent queue blocking.
* **Smart Bounding Box & Adaptive Tile Cap:** Aggressive ROI cropping and dynamic VRAM-aware tile limits prevent OOM crashes on hardware like the 4GB GTX 1650.
* **Hardware Auto-Detect:** Automatically switches between FP16/FP32 and CUDA/MPS based on the host system's capabilities.

## 🤖 Agent-Centric Installation
If you are using an AI coding agent (Cursor, Windsurf, Claude Code):
Simply prompt your agent: **"Install and run this application."**

The repository includes strict `.cursorrules` and a zero-touch `setup_env.py` hardware profiler. Your agent will autonomously detect your OS, calculate disk space, install the correct CUDA/MPS dependencies, and boot the frontend/backend without requiring manual intervention.

## 🛠️ Manual Installation (Docker)
Run `docker-compose up -d --build`
