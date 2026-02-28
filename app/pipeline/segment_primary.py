import time
import rembg
import numpy as np
from PIL import Image
import cv2
from .detect_hair_fur import detect_hair_fur
from .final_edge_cleanup import final_edge_cleanup


class PrimarySegmenter:
    def __init__(self, model_name="isnet-general-use"):
        self.model_name = model_name
        self.session = rembg.new_session(model_name=self.model_name)

    def process(
        self,
        image: Image.Image,
        erode_size: int = 0,
        blur_size: int = 0,
        auto_cleanup: bool = True,
        infer_max_side: int = 1536,
    ) -> dict:
        start_time = time.time()
        orig_image = image.convert("RGB")
        orig_np = np.array(orig_image)
        oh, ow = orig_np.shape[:2]

        scale = 1.0
        work_image = orig_image
        if infer_max_side and max(oh, ow) > infer_max_side:
            scale = float(infer_max_side) / float(max(oh, ow))
            nw, nh = int(round(ow * scale)), int(round(oh * scale))
            work_image = orig_image.resize((nw, nh), Image.Resampling.LANCZOS)

        result = rembg.remove(
            work_image,
            session=self.session,
            only_mask=False,
            post_process_mask=False,
            alpha_matting=True,
            alpha_matting_foreground_threshold=235,
            alpha_matting_background_threshold=8,
            alpha_matting_erode_size=2,
        )

        work_np = np.array(result)
        mask_raw = work_np[:, :, 3].copy()

        if scale != 1.0:
            mask_raw = cv2.resize(mask_raw, (ow, oh), interpolation=cv2.INTER_CUBIC)
            result_np = np.dstack([orig_np, mask_raw]).astype(np.uint8)
        else:
            result_np = work_np.copy()

        is_hairy = False
        if auto_cleanup:
            is_hairy, _ = detect_hair_fur(mask_raw)

            if not is_hairy:
                lookup = np.array([
                    np.clip(pow(i / 255.0, 1.35) * 255.0, 0, 255)
                    for i in range(256)
                ], dtype=np.uint8)
                mask_np = cv2.LUT(mask_raw, lookup)
            else:
                mask_np = mask_raw.copy()

            clamp = 4 if is_hairy else 6
            mask_np[mask_np < clamp] = 0
            result_np[:, :, 3] = mask_np

            # Compatibility: support both cleanup signatures
            try:
                result_np = final_edge_cleanup(result_np, is_hairy=is_hairy)
            except TypeError:
                result_np = final_edge_cleanup(result_np)

            mask_np = result_np[:, :, 3].copy()
        else:
            mask_np = mask_raw

        return {
            "cutout": Image.fromarray(result_np),
            "mask": Image.fromarray(mask_np),
            "runtime_ms": int((time.time() - start_time) * 1000),
            "hair_detected": is_hairy,
            "inference_scale": round(scale, 4),
        }
