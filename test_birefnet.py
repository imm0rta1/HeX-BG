import time, sys, os
from PIL import Image
import rembg

image_path = sys.argv[1]
img = Image.open(image_path).convert("RGB")
print(f"Image size: {img.size}")

print("Loading BiRefNet-general into GPU...")
try:
    start_load = time.time()
    session = rembg.new_session("birefnet-general")
    print(f"Model loaded in {time.time() - start_load:.2f} seconds.")

    print("Extracting background...")
    start_proc = time.time()
    out = rembg.remove(img, session=session)
    proc_time = time.time() - start_proc
    print(f"[SUCCESS] Extraction completed in {proc_time:.2f} seconds!")

    out_path = "birefnet_offline_test.png"
    out.save(out_path)
    print(f"Result saved to {os.path.abspath(out_path)}")
except Exception as e:
    print(f"[ERROR] {e}")
