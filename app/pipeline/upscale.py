import cv2
from cv2 import dnn_superres
import numpy as np
from pathlib import Path

class ImageUpscaler:
    def __init__(self, scale=2):
        self.scale = scale
        model_dir = Path(__file__).resolve().parent.parent.parent / "data" / "models"
        self.model_path = str(model_dir / f"ESPCN_x{scale}.pb")
        self.sr = dnn_superres.DnnSuperResImpl_create()
        self.sr.readModel(self.model_path)
        self.sr.setModel("espcn", self.scale)

    def _upscale_tiled(self, img: np.ndarray, tile_size: int = 256) -> np.ndarray:
        h, w = img.shape[:2]
        upscaled_img = np.zeros((h * self.scale, w * self.scale, img.shape[2]), dtype=np.uint8)
        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                tile = img[y:min(y+tile_size, h), x:min(x+tile_size, w)]
                upscaled_tile = self.sr.upsample(tile)

                start_y = y * self.scale
                end_y = start_y + upscaled_tile.shape[0]
                start_x = x * self.scale
                end_x = start_x + upscaled_tile.shape[1]

                upscaled_img[start_y:end_y, start_x:end_x] = upscaled_tile
        return upscaled_img

    def process(self, img_np: np.ndarray) -> np.ndarray:
        tile_size = 256
        if len(img_np.shape) == 3 and img_np.shape[2] == 4:
            rgb = img_np[:, :, :3]
            alpha = img_np[:, :, 3]

            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            bgr_up = self._upscale_tiled(bgr, tile_size)
            rgb_up = cv2.cvtColor(bgr_up, cv2.COLOR_BGR2RGB)

            # CLEAN UPSCALING: No more binary thresholds destroying the hairs!
            h, w = rgb_up.shape[:2]
            alpha_up = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LANCZOS4)

            # Just a tiny cleanup to prevent resize ringing
            alpha_up[alpha_up < 10] = 0

            return np.dstack((rgb_up, alpha_up))
        else:
            bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            bgr_up = self._upscale_tiled(bgr, tile_size)
            return cv2.cvtColor(bgr_up, cv2.COLOR_BGR2RGB)
