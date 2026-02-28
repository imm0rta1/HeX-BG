import torch
torch.multiprocessing.set_sharing_strategy("file_system")
import time, sys, os, logging, threading, gc
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
segmenter_load_ms = {}
_segmenter_lock = threading.Lock()
LOW_VRAM_MODE = True # FORCE ON for GTX 1650

def _normalize_model_name(name: str) -> str:
    return (name or "isnet-general-use").strip()

def _cleanup_gpu():
    gc.collect()
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass

def get_worker_segmenter(model_name="isnet-general-use"):
    model_name = _normalize_model_name(model_name)

    if model_name in segmenters:
        return segmenters[model_name]

    with _segmenter_lock:
        # STRICT VRAM SWAP: If a different model is loaded, DELETE IT to free VRAM
        if segmenters:
            logger.warning(f"Swapping VRAM: Deleting old models {list(segmenters.keys())}")
            segmenters.clear()
            _cleanup_gpu()

        t0 = time.time()
        settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        os.environ["U2NET_HOME"] = str(settings.MODEL_DIR)
        segmenters[model_name] = PrimarySegmenter(model_name=model_name)
        load_ms = int((time.time() - t0) * 1000)
        segmenter_load_ms[model_name] = load_ms
        logger.warning(f"Model loaded into worker cache: {model_name} ({load_ms} ms)")
        return segmenters[model_name]

def _safe_segment(model_name, img, erode_size, blur_size, auto_cleanup, infer_max_side):
    model = get_worker_segmenter(model_name)
    try:
        return model.process(img, erode_size=erode_size, blur_size=blur_size, auto_cleanup=auto_cleanup, infer_max_side=infer_max_side)
    except Exception as e:
        logger.error(f"Segmentation error: {e}")
        raise e

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
    model_name = _normalize_model_name(model_name)
    try:
        job_dir = settings.STORAGE_DIR / job_id
        
        # 1. LOAD MODEL (Swaps out old ones if necessary)
        get_worker_segmenter(model_name)
        img = load_image(image_path)
        
        # 2. RUN EXTRACTION
        # Reduce resolution for BiRefNet on 4GB cards to prevent OOM
        infer_max_side = 1024 if "birefnet" in model_name.lower() else 1400
        result = _safe_segment(model_name, img, erode_size, blur_size, auto_cleanup, infer_max_side)
        cutout_img, mask_img = result["cutout"], result["mask"]
        
        # 3. SWAP VRAM BEFORE UPSCALE: If upscaling, we MUST delete the segmenter from VRAM first!
        if upscale_mode and upscale_mode != "none":
            logger.warning("VRAM SWAP: Deleting segmenter to make room for Upscaler!")
            segmenters.clear()
            _cleanup_gpu()
            
            from app.pipeline.upscale_realesrgan import upscale_and_reclean
            cutout_np = np.array(cutout_img)
            final_rgba_np, qc_metrics = upscale_and_reclean(cutout_np, mode=upscale_mode)
            cutout_img = Image.fromarray(final_rgba_np)
            mask_img = Image.fromarray(final_rgba_np[:, :, 3])
            
            # SWAP VRAM AFTER UPSCALE
            _cleanup_gpu()
            logger.warning("VRAM SWAP: Upscale done, GPU cleared.")
        else:
            # Just do QC if not upscaling
            qc_metrics = qc_halo_haze_check(np.array(cutout_img), haze_max_ratio=0.003, halo_max_score=0.12, orphan_min_area=12, max_side=1024)

        save_image(cutout_img, job_dir / "cutout.png")
        save_image(mask_img, job_dir / "mask.png")
        return {"status": "done", "qc": qc_metrics, "cutout_url": f"/files/{job_id}/cutout.png", "mask_url": f"/files/{job_id}/mask.png"}
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise e

def preload_model_task(model_name: str):
    logger.info(f"Preloading model {model_name}...")
    try:
        get_worker_segmenter(model_name)
        return {"status": "done", "model": model_name}
    except Exception as e:
        logger.error(f"Preload failed: {e}")
        raise e
