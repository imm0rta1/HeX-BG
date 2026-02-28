import time, sys, os
from PIL import Image
import numpy as np
import rembg

image_path = "/a0/usr/uploads/pixelcut.png.png"
print(f"Processing image: {image_path}")
img = Image.open(image_path).convert("RGB")

print("Loading BiRefNet-general on CPU to bypass GPU bug...")
# Force CPU Execution
session = rembg.new_session("birefnet-general", providers=['CPUExecutionProvider'])

print("Extracting background (This will be slower on CPU)...")
start = time.time()
out = rembg.remove(img, session=session)
print(f"Done in {time.time() - start:.2f} seconds.")

out_path = "/a0/usr/workdir/birefnet_cpu_test.png"
out.save(out_path)
print(f"Saved to {out_path}")

out_np = np.array(out)
print("\n--- Pixel Analysis ---")
print(f"Max values -> R: {out_np[:,:,0].max()}, G: {out_np[:,:,1].max()}, B: {out_np[:,:,2].max()}, Alpha: {out_np[:,:,3].max()}")

if out_np[:,:,3].max() == 0:
    print("\n[DIAGNOSTIC] The image is 100% transparent. The AI math failed.")
elif out_np[:,:,:3].max() == 0:
    print("\n[DIAGNOSTIC] The image is 100% black. The AI math failed.")
else:
    print("\n[DIAGNOSTIC] Success! The image has valid color and alpha data.")
