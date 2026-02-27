import os, sys, platform, subprocess, shutil

def check_space():
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)
    if free_gb < 2:
        sys.stderr.write(f"[ERROR] Insufficient Disk Space. Requires >2GB, found {free_gb}GB.
")
        sys.exit(1)
    print(f"[OK] Disk space sufficient: {free_gb}GB free.")

def install_pytorch():
    os_name = platform.system()
    if os_name == "Darwin":
        print("[INFO] Apple macOS detected. Routing to MPS-compatible PyTorch...")
        subprocess.run([sys.executable, "-m", "pip", "install", "torch", "torchvision"])
    else:
        print("[INFO] Windows/Linux detected. Checking for NVIDIA GPU...")
        try:
            subprocess.check_output("nvidia-smi", stderr=subprocess.STDOUT)
            print("[INFO] NVIDIA GPU detected. Installing CUDA-accelerated PyTorch...")
            subprocess.run([sys.executable, "-m", "pip", "install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu121"])
        except Exception:
            print("[INFO] No NVIDIA GPU detected. Installing CPU-fallback PyTorch...")
            subprocess.run([sys.executable, "-m", "pip", "install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"])

if __name__ == "__main__":
    print("Starting Zero-Touch Hardware Profiler...")
    check_space()
    install_pytorch()
    print("Installing requirements...")
    if os.path.exists("requirements.txt"):
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("[SUCCESS] Environment setup complete. Ready for model download.")
