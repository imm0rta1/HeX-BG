import numpy as np
from .upscale_realesrgan import upscale_and_reclean

class ImageUpscaler:
    def __init__(self, scale=2):
        self.scale = scale
        self.mode = "4x_topaz" if scale >= 4 else "2x"

    def process(self, img_np: np.ndarray) -> np.ndarray:
        # The upscale_and_reclean function expects RGBA or RGB
        # It handles the complex tiling and hardware detection internally
        result, _ = upscale_and_reclean(img_np, mode=self.mode)
        return result
