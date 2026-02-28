import time, sys, os
from PIL import Image
import numpy as np
import rembg

image_path = sys.argv[1]
print(f"Processing image: {image_path}")
img = Image.open(image_path).convert("RGB")

print("Loading BiRefNet-general...")
session = rembg.new_session("birefnet-general")

print("Extracting background...")
start = time.time()
out = rembg.remove(img, session=session)
print(f"Done in {time.time() - start:.2f} seconds.")

out_path = "/a0/usr/workdir/birefnet_test_pixelcut.png"
out.save(out_path)
print(f"Saved to {out_path}")

# Diagnose the pixels
out_np = np.array(out)
print("\n--- Pixel Analysis ---")
print(f"Output shape: {out_np.shape}")
print(f"Max values -> R: {out_np[:,:,0].max()}, G: {out_np[:,:,1].max()}, B: {out_np[:,:,2].max()}, Alpha: {out_np[:,:,3].max()}")

if out_np[:,:,3].max() == 0:
    print("\n[DIAGNOSTIC] The image is 100% transparent. The AI math failed completely.")
elif out_np[:,:,:3].max() == 0:
    print("\n[DIAGNOSTIC] The image is 100% black. The AI math failed completely.")
else:
    print("\n[DIAGNOSTIC] Success! The image has valid color and alpha data.")
