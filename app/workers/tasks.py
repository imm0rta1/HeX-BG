import torch
torch.multiprocessing.set_sharing_strategy("file_system")
import time, sys, os, logging
from pathlib import Path
from PIL import Image
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.core.config import settings
from app.utils.image_io import load_image, save_image
from app.pipeline.segment_primary import PrimarySegmenter
from app.pipeline.qc_halo_haze_check import qc_halo_haze_check

logger = logging.getLogger(__name__)
segmenters = {}


def get_worker_segmenter(model_name="isnet-general-use"):
    if model_name not in segmenters:
        settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        os.environ["U2NET_HOME"] = str(settings.MODEL_DIR)
        segmenters[model_name] = PrimarySegmenter(model_name=model_name)
    return segmenters[model_name]


def process_image_task(
    job_id: str,
    image_path: str,
    model_name: str = "isnet-general-use",
    erode_size: int = 0,
    blur_size: int = 0,
    auto_cleanup: bool = True,
    upscale: bool = False,
    upscale_mode: str = "none",
):
    try:
        job_dir = settings.STORAGE_DIR / job_id
        model = get_worker_segmenter(model_name)
        img = load_image(image_path)

        # Logic: If NOT upscaling, use faster inference resolution (1536px)
        # If upscaling (2x/4x), we might want higher base quality, so use 2048px or full res.
        # But 'none' mode needs to be snappy.
        infer_max_side = 1536 if (not upscale_mode or upscale_mode == "none") else 2048

        t_seg0 = time.time()
        result = model.process(
            img,
            erode_size=erode_size,
            blur_size=blur_size,
            auto_cleanup=auto_cleanup,
            infer_max_side=infer_max_side,
        )
        seg_ms = int((time.time() - t_seg0) * 1000)

        cutout_img = result["cutout"]
        mask_img = result["mask"]
        qc_ms = 0
        upscale_ms = 0
        qc_metrics = {}

        if upscale_mode and upscale_mode != "none":
            from app.pipeline.upscale_realesrgan import upscale_and_reclean
            cutout_np = np.array(cutout_img)
            t_up0 = time.time()
            final_rgba_np, qc_metrics = upscale_and_reclean(cutout_np, mode=upscale_mode)
            upscale_ms = int((time.time() - t_up0) * 1000)
            cutout_img = Image.fromarray(final_rgba_np)
            mask_img = Image.fromarray(final_rgba_np[:, :, 3])
        else:
            # Fast QC path
            cutout_np = np.array(cutout_img)
            t_qc0 = time.time()
            # Downscale QC to 1024px for speed on large images
            qc_metrics = qc_halo_haze_check(
                cutout_np,
                haze_max_ratio=0.003,
                halo_max_score=0.12,
                orphan_min_area=12,
                max_side=1024, 
            )
            qc_ms = int((time.time() - t_qc0) * 1000)
            if not qc_metrics["pass"]:
                logger.error(f"QC failed: {qc_metrics}")
                logger.warning(f"QC failed but returning image: {qc_metrics}")

        save_image(cutout_img, job_dir / "cutout.png")
        save_image(mask_img, job_dir / "mask.png")

        return {
            "status": "done",
            "runtime_ms": result["runtime_ms"],
            "qc": qc_metrics,
            "cutout_url": f"/files/{job_id}/cutout.png",
            "mask_url": f"/files/{job_id}/mask.png",
            "timing": {
                "seg_ms": seg_ms,
                "qc_ms": qc_ms,
                "upscale_ms": upscale_ms,
                "inference_scale": result.get("inference_scale", 1.0),
            },
        }
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise e
