import cv2
import numpy as np
from app.pipeline.upscale_realesrgan import upscale_and_reclean

# Create a simple red square with an alpha channel (like a cutout)
test_img = np.zeros((100, 100, 4), dtype=np.uint8)
test_img[20:80, 20:80] = [0, 0, 255, 255] # Red square, fully opaque

print("Input Max RGB:", np.max(test_img[:,:,:3]))

# Test the full upscale pipeline
try:
    out_img, _ = upscale_and_reclean(test_img, "2x")
    print("Final Max RGB:", np.max(out_img[:,:,:3]))
    if np.max(out_img[:,:,:3]) == 0:
        print("\nRESULT: PURE BLACK! The PyTorch CUDA bug is confirmed.")
    else:
        print("\nRESULT: Normal. The bug is somewhere else.")
except Exception as e:
    print(f"\nError during upscale: {e}")
