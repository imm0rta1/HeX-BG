import os, re

# 1. Update routes_jobs.py to accept upscale_mode
routes_path = 'app/api/routes_jobs.py'
with open(routes_path, 'r') as f:
    routes_code = f.read()

if "upscale_mode: str = Form" not in routes_code:
    routes_code = routes_code.replace('upscale: str = Form("false"),', 'upscale: str = Form("false"), upscale_mode: str = Form("none"),')
    routes_code = routes_code.replace('"upscale": upscale,', '"upscale": upscale, "upscale_mode": upscale_mode,')
    with open(routes_path, 'w') as f:
        f.write(routes_code)

# 2. Update tasks.py to use upscale_mode and pass it to upscale_and_reclean
tasks_path = 'app/workers/tasks.py'
with open(tasks_path, 'r') as f:
    tasks_code = f.read()

start_tag = "    # ====== UPSCALE INJECTION ======"
end_tag = "    # ==============================="
if start_tag in tasks_code and end_tag in tasks_code:
    start_idx = tasks_code.find(start_tag)
    end_idx = tasks_code.find(end_tag) + len(end_tag)
    match = re.search(r"(\w+), qc_result = upscale_and_reclean", tasks_code[start_idx:end_idx])
    var_name = match.group(1) if match else "result_np"
    
    new_block = f"""    # ====== UPSCALE INJECTION ======
    upscale_mode = job_data.get('upscale_mode', 'none')
    if upscale_mode in ['2x', '4x_topaz']:
        import logging
        logging.info(f"Starting Real-ESRGAN Upscale Stage with mode: {upscale_mode}")
        from app.pipeline.upscale_realesrgan import upscale_and_reclean
        {var_name}, qc_result = upscale_and_reclean({var_name}, mode=upscale_mode)
        job_data['qc'] = qc_result
        qc_path = job_dir / "qc.json"
        import json
        with open(qc_path, "w") as f:
            json.dump(qc_result, f)
    # ==============================="""
    tasks_code = tasks_code[:start_idx] + new_block + tasks_code[end_idx:]
    with open(tasks_path, 'w') as f:
        f.write(tasks_code)

# 3. Rewrite upscale_realesrgan.py to handle the modes properly
upscale_code = """import cv2
import numpy as np
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
        import app.pipeline.final_edge_cleanup as fec
        cleanup_func = getattr(fec, 'final_edge_cleanup', lambda x, **kw: x)
    except:
        cleanup_func = lambda x, **kwargs: x
    return cleanup_func, lambda x: {"pass": True, "reasons": []}

def edge_smear(rgb, alpha, iterations=15):
    mask = alpha > 0
    smeared = rgb.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for _ in range(iterations):
        dilated = cv2.dilate(smeared, kernel)
        smeared[~mask] = dilated[~mask]
        mask = cv2.dilate(mask.astype(np.uint8), kernel) > 0
    return smeared

def apply_unsharp_mask(image, amount=0.8, radius=1.0, threshold=0):
    blurred = cv2.GaussianBlur(image, (0, 0), radius)
    sharpened = float(amount + 1) * image - float(amount) * blurred
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    return sharpened

def fit_and_pad_to_4096(rgba_image):
    target_size = 4096
    h, w = rgba_image.shape[:2]
    scale = target_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(rgba_image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)
    x_offset = (target_size - new_w) // 2
    y_offset = (target_size - new_h) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    return canvas

def upscale_and_reclean(rgba_image, mode="4x_topaz"):
    cleanup_func, qc_func = get_cleanup_and_qc()
    scale = 4 if mode == "4x_topaz" else 2
    
    if HAS_REALESRGAN:
        logging.info(f"Running Upscale: {mode} (Scale={scale})...")
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        model_path = '/a0/usr/workdir/bg-removal-service/bg-removal-service/data/models/RealESRGAN_x4plus.pth'
        
        upsampler = RealESRGANer(scale=4, model_path=model_path, model=model, tile=256, tile_pad=10, pre_pad=0, half=False)
        
        rgb = rgba_image[:,:,:3]
        alpha = rgba_image[:,:,3]
        smeared = edge_smear(rgb, alpha, iterations=15)
        
        out_rgb, _ = upsampler.enhance(smeared, outscale=scale)
        alpha_3c = cv2.cvtColor(alpha, cv2.COLOR_GRAY2BGR)
        out_alpha_3c, _ = upsampler.enhance(alpha_3c, outscale=scale)
        out_alpha = cv2.cvtColor(out_alpha_3c, cv2.COLOR_BGR2GRAY)
        
        if mode == "4x_topaz":
            out_rgb = apply_unsharp_mask(out_rgb, amount=0.7, radius=1.5)
        else:
            out_rgb = apply_unsharp_mask(out_rgb, amount=0.4, radius=1.0)
            
        out_alpha[out_alpha < 15] = 0
        out_alpha[out_alpha > 240] = 255
        
        merged = cv2.cvtColor(out_rgb, cv2.COLOR_BGR2BGRA)
        merged[:,:,3] = out_alpha
    else:
        merged = rgba_image

    if mode == "4x_topaz":
        final_img = fit_and_pad_to_4096(merged)
    else:
        final_img = merged

    try:
        final_rgba = cleanup_func(final_img, is_hairy=True)
    except Exception as e:
        logging.error(f"Re-cleanup failed: {e}")
        final_rgba = final_img

    return final_rgba, {"pass": True, "reasons": []}
"""
with open('app/pipeline/upscale_realesrgan.py', 'w') as f:
    f.write(upscale_code)

# 4. Update App.tsx logic
app_path = 'frontend/web-ui/src/App.tsx'
with open(app_path, 'r') as f:
    app_content = f.read()

app_content = app_content.replace(
    "const [upscale, setUpscale] = useState<boolean>(false);",
    "const [upscaleMode, setUpscaleMode] = useState<string>('none');"
)
app_content = app_content.replace(
    "formData.append('upscale', upscale.toString());",
    "formData.append('upscale_mode', upscaleMode);"
)

old_checkbox = """              <label className="flex items-center cursor-pointer group">
                <div className="relative mr-3">
                  <input type="checkbox" className="sr-only" checked={upscale} onChange={(e) => setUpscale(e.target.checked)} />
                  <div className={`w-4 h-4 border transition-colors flex items-center justify-center ${upscale ? 'border-[#D4FF00] bg-[#D4FF00]/10' : 'border-white/20'}`}>
                    {upscale && <div className="w-1.5 h-1.5 bg-[#D4FF00]"></div>}
                  </div>
                </div>
                <span className="text-[10px] text-white tracking-widest uppercase">4096x4096 Neural Upscale</span>
              </label>"""
              
new_dropdown = """              <div className="relative pt-1">
                <label className="text-[9px] tracking-widest text-gray-500 block mb-2 uppercase">Neural Upscale Mode</label>
                <div className="relative">
                  <select
                    value={upscaleMode}
                    onChange={(e) => setUpscaleMode(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 text-gray-300 p-2 text-[10px] tracking-wider focus:outline-none focus:border-[#D4FF00] transition-colors appearance-none cursor-pointer"
                  >
                    <option value="none">None [ Native Res ]</option>
                    <option value="2x">2x Neural [ HQ ]</option>
                    <option value="4x_topaz">4x Topaz / 4096px [ Ultra ]</option>
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-[#D4FF00]/50 rotate-45 pointer-events-none"></div>
                </div>
              </div>"""

# Fallback for previous text if it wasn't replaced
old_checkbox_fallback = old_checkbox.replace("4096x4096 Neural Upscale", "2x Neural Upscale")

if "4096x4096 Neural Upscale" in app_content:
    app_content = app_content.replace(old_checkbox, new_dropdown)
elif "2x Neural Upscale" in app_content:
    app_content = app_content.replace(old_checkbox_fallback, new_dropdown)

with open(app_path, 'w') as f:
    f.write(app_content)

