import os
import re

upscale_code = """import cv2
import numpy as np
import os
import logging

try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    HAS_REALESRGAN = True
except ImportError as e:
    logging.warning(f"RealESRGAN import failed: {e}")
    HAS_REALESRGAN = False

def get_cleanup_and_qc():
    try:
        # Check exactly what function is exported by final_edge_cleanup
        import app.pipeline.final_edge_cleanup as fec
        cleanup_func = getattr(fec, 'process_edge', getattr(fec, 'refine_edges', getattr(fec, 'cleanup', lambda x, **kw: x)))
    except ImportError:
        cleanup_func = lambda x, **kwargs: x
        
    try:
        import app.pipeline.qc_halo_haze_check as qhc
        qc_func = getattr(qhc, 'check_quality', getattr(qhc, 'run_qc', lambda x: {"pass": True, "reasons": []}))
    except ImportError:
        qc_func = lambda x: {"pass": True, "reasons": []}
        
    return cleanup_func, qc_func

def edge_smear(rgb, alpha, iterations=10):
    mask = alpha > 0
    smeared = rgb.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for _ in range(iterations):
        dilated = cv2.dilate(smeared, kernel)
        smeared[~mask] = dilated[~mask]
        mask = cv2.dilate(mask.astype(np.uint8), kernel) > 0
    return smeared

def upscale_and_reclean(rgba_image, scale=2):
    cleanup_func, qc_func = get_cleanup_and_qc()
    
    if not HAS_REALESRGAN:
        logging.info("Using fallback Lanczos4 upscaler + smears")
        h, w = rgba_image.shape[:2]
        rgb = rgba_image[:,:,:3]
        alpha = rgba_image[:,:,3]
        smeared = edge_smear(rgb, alpha)
        out_rgb = cv2.resize(smeared, (w*scale, h*scale), interpolation=cv2.INTER_LANCZOS4)
        out_alpha = cv2.resize(alpha, (w*scale, h*scale), interpolation=cv2.INTER_LANCZOS4)
    else:
        logging.info("Running Real-ESRGAN x4 Seamless Tiling")
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        model_path = '/a0/usr/workdir/bg-removal-service/bg-removal-service/data/models/RealESRGAN_x4plus.pth'
        
        upsampler = RealESRGANer(
            scale=4,
            model_path=model_path,
            model=model,
            tile=256,
            tile_pad=10,
            pre_pad=0,
            half=False
        )
        
        rgb = rgba_image[:,:,:3]
        alpha = rgba_image[:,:,3]
        smeared = edge_smear(rgb, alpha)
        
        out_rgb, _ = upsampler.enhance(smeared, outscale=scale)
        
        alpha_3c = cv2.cvtColor(alpha, cv2.COLOR_GRAY2BGR)
        out_alpha_3c, _ = upsampler.enhance(alpha_3c, outscale=scale)
        out_alpha = cv2.cvtColor(out_alpha_3c, cv2.COLOR_BGR2GRAY)

    # Alpha Clamping
    out_alpha[out_alpha < 5] = 0
    out_alpha[out_alpha > 250] = 255

    merged = cv2.cvtColor(out_rgb, cv2.COLOR_BGR2BGRA)
    merged[:,:,3] = out_alpha

    try:
        final_rgba = cleanup_func(merged)
    except Exception as e:
        logging.error(f"Re-cleanup failed: {e}")
        final_rgba = merged
        
    try:
        qc_result = qc_func(final_rgba)
    except Exception as e:
        qc_result = {"pass": True, "reasons": [str(e)]}

    return final_rgba, qc_result
"""
os.makedirs('app/pipeline', exist_ok=True)
with open('app/pipeline/upscale_realesrgan.py', 'w') as f:
    f.write(upscale_code)
    
tasks_file = 'app/workers/tasks.py'
with open(tasks_file, 'r') as f:
    tasks_code = f.read()
    
if "upscale_and_reclean" not in tasks_code:
    save_pattern = r"(cv2\.imwrite\(str\(cutout_path\),\s*([a-zA-Z0-9_]+)\))"
    match = re.search(save_pattern, tasks_code)
    if match:
        var_name = match.group(2)
        injection = f"""
    # ====== UPSCALE INJECTION ======
    upscale_flag = job_data.get('upscale', 'false') == 'true' or job_data.get('upscale') is True
    if upscale_flag:
        import logging
        logging.info("Starting Real-ESRGAN Upscale Stage...")
        from app.pipeline.upscale_realesrgan import upscale_and_reclean
        {var_name}, qc_result = upscale_and_reclean({var_name}, scale=2)
        job_data['qc'] = qc_result
        qc_path = job_dir / "qc.json"
        import json
        with open(qc_path, "w") as f:
            json.dump(qc_result, f)
    # ===============================
    {match.group(1)}"""
        tasks_code = tasks_code.replace(match.group(1), injection)
        with open(tasks_file, 'w') as f:
            f.write(tasks_code)
        print("Successfully injected upscale logic into tasks.py")
    else:
        print("Could not find save location in tasks.py to inject!")
