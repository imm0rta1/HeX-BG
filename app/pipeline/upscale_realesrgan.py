import cv2
import numpy as np
import logging

try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    HAS_REALESRGAN = True
except ImportError as e:
    logging.warning(f"RealESRGAN import failed: {e}")
    HAS_REALESRGAN = False

_UPSAMPLERS = {}


def _get_upsampler(tile=256):
    key = f"x4_t{tile}"
    if key in _UPSAMPLERS:
        return _UPSAMPLERS[key]

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    model_path = '/a0/agent-zero-data/workdir/bg-removal-service/bg-removal-service/data/models/RealESRGAN_x4plus.pth'
    upsampler = RealESRGANer(
        scale=4,
        model_path=model_path,
        model=model,
        tile=tile,
        tile_pad=10,
        pre_pad=0,
        half=False,
    )
    _UPSAMPLERS[key] = upsampler
    return upsampler


def get_cleanup_func():
    try:
        import app.pipeline.final_edge_cleanup as fec
        return getattr(fec, 'final_edge_cleanup', lambda x: x)
    except Exception:
        return lambda x: x


def edge_smear(rgb, alpha, iterations=4):
    mask = alpha > 0
    smeared = rgb.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for _ in range(iterations):
        dilated = cv2.dilate(smeared, kernel)
        smeared[~mask] = dilated[~mask]
        mask = cv2.dilate(mask.astype(np.uint8), kernel) > 0
    return smeared


def apply_unsharp_mask(image, amount=0.35, radius=1.0):
    blurred = cv2.GaussianBlur(image, (0, 0), radius)
    sharpened = float(amount + 1) * image - float(amount) * blurred
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def fit_and_pad_to_4096(rgba_image):
    target_size = 4096
    h, w = rgba_image.shape[:2]
    scale = target_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(rgba_image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)
    x_offset = (target_size - new_w) // 2
    y_offset = (target_size - new_h) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
    return canvas


def upscale_and_reclean(rgba_image, mode="4x_topaz"):
    scale = 4 if mode == "4x_topaz" else 2

    if not HAS_REALESRGAN:
        return rgba_image, {"pass": True, "reasons": ["realesrgan_unavailable"]}

    logging.info(f"Running Upscale FAST: {mode} (scale={scale})")

    import cv2
    import numpy as np
    # --- Smart Bounding Box Crop ---
    h_full, w_full = rgba_image.shape[:2]
    alpha_channel = rgba_image[:, :, 3]
    coords = cv2.findNonZero(alpha_channel)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        buffer = 16
        x1 = max(0, x - buffer)
        y1 = max(0, y - buffer)
        x2 = min(w_full, x + w + buffer)
        y2 = min(h_full, y + h + buffer)
        rgba_image = rgba_image[y1:y2, x1:x2]
        logging.info(f"Smart Bounding Box: Cropped from {w_full}x{h_full} to {x2-x1}x{y2-y1} to save processing time.")
    else:
        x1, y1, x2, y2 = 0, 0, w_full, h_full
    # -------------------------------
    # --- Smart Hardware Auto-Detect & Tile Cap ---
    import torch
    import numpy as np
    import cv2

    device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')

    if device.type == 'cuda':
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        if vram_gb > 20: # e.g., 24GB RTX 4090
            base_tile = 256 if mode == "4x_topaz" else 512
            max_tiles = 64
        elif vram_gb > 10: # e.g., 12GB RTX 3060/4070
            base_tile = 256 if mode == "4x_topaz" else 400
            max_tiles = 36
        elif vram_gb > 6: # e.g., 8GB
            base_tile = 192 if mode == "4x_topaz" else 320
            max_tiles = 25
        else: # <= 6GB (Like GTX 1650)
            base_tile = 192 if mode == "4x_topaz" else 256
            max_tiles = 16
        logging.info(f"Hardware Auto-Detect: {vram_gb:.1f}GB VRAM detected. Setting tile={base_tile}, max_tiles={max_tiles}")
    elif device.type == 'mps':
        base_tile = 192 if mode == "4x_topaz" else 320
        max_tiles = 25
        logging.info(f"Hardware Auto-Detect: Apple Silicon (MPS) detected. Setting tile={base_tile}, max_tiles={max_tiles}")
    else:
        base_tile = 192 if mode == "4x_topaz" else 256
        max_tiles = 9
        logging.info(f"Hardware Auto-Detect: CPU detected. Setting tile={base_tile}, max_tiles={max_tiles} to prevent freezing.")

    tile = base_tile
    upsampler = _get_upsampler(tile=tile)

    h_orig, w_orig = rgba_image.shape[:2]
    max_pixels = max_tiles * (tile * tile)
    if w_orig * h_orig > max_pixels:
        ratio = float(np.sqrt(max_pixels / (w_orig * h_orig)))
        new_w, new_h = int(w_orig * ratio), int(h_orig * ratio)
        logging.info(f"Adaptive Tile Cap: Downscaling {w_orig}x{h_orig} to {new_w}x{new_h} to prevent hardware overload.")
        rgba_image = cv2.resize(rgba_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # ---------------------------------------------

    rgb = rgba_image[:, :, :3]
    alpha = rgba_image[:, :, 3]

    smeared = edge_smear(rgb, alpha, iterations=4)

    out_rgb, _ = upsampler.enhance(smeared, outscale=scale)

    # Fast alpha upscale via CV2 (way faster than running ESRGAN on alpha)
    h, w = rgba_image.shape[:2]
    target = (w * scale, h * scale)
    a_cubic = cv2.resize(alpha, target, interpolation=cv2.INTER_CUBIC)
    a_area = cv2.resize(alpha, target, interpolation=cv2.INTER_AREA)
    out_alpha = np.clip(0.7 * a_cubic + 0.3 * a_area, 0, 255).astype(np.uint8)

    # Gentle sharpening
    out_rgb = apply_unsharp_mask(out_rgb, amount=0.35 if mode == '2x' else 0.5, radius=1.0)

    out_alpha[out_alpha < 12] = 0
    out_alpha[out_alpha > 245] = 255

    merged = cv2.cvtColor(out_rgb, cv2.COLOR_BGR2BGRA)
    merged[:, :, 3] = out_alpha

    # --- Restore Smart Bounding Box ---
    ch_up, cw_up = merged.shape[:2]
    cw_orig = x2 - x1
    overall_scale = cw_up / float(cw_orig) if cw_orig > 0 else scale

    final_w = int(w_full * overall_scale)
    final_h = int(h_full * overall_scale)
    final_x1 = int(x1 * overall_scale)
    final_y1 = int(y1 * overall_scale)

    canvas = np.zeros((final_h, final_w, 4), dtype=np.uint8)

    paste_h, paste_w = merged.shape[:2]
    end_y = min(final_y1 + paste_h, final_h)
    end_x = min(final_x1 + paste_w, final_w)
    actual_paste_h = end_y - final_y1
    actual_paste_w = end_x - final_x1

    canvas[final_y1:end_y, final_x1:end_x] = merged[:actual_paste_h, :actual_paste_w]
    merged = canvas
    logging.info(f"Smart Bounding Box: Restored to {final_w}x{final_h} canvas.")
    # ----------------------------------

    final_img = fit_and_pad_to_4096(merged) if mode == "4x_topaz" else merged

    cleanup_func = get_cleanup_func()
    try:
        final_rgba = cleanup_func(final_img)
    except Exception as e:
        logging.error(f"Re-cleanup failed: {e}")
        final_rgba = final_img

    return final_rgba, {"pass": True, "reasons": []}
