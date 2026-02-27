import cv2
from app.pipeline.upscale import ImageUpscaler
import time

print("Loading cutout image...")
img = cv2.imread('data/test_images/petela_out_perfect_v4.png', cv2.IMREAD_UNCHANGED)

print("Initializing Upscaler (EDSR x2)...")
upscaler = ImageUpscaler(scale=2)

print(f"Original shape: {img.shape} (Width x Height x Channels)")

start = time.time()
print("Upsampling using AI (this may take a few seconds on CPU)...")
result = upscaler.process(img)
print(f"Upscaled shape: {result.shape} in {time.time()-start:.2f}s")

cv2.imwrite('data/test_images/petela_upscaled.png', result)
print("Saved to data/test_images/petela_upscaled.png")
