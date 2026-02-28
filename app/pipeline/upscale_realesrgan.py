import cv2
import numpy as np
import logging

import torch
# GTX 1650 / Turing hardware bug bypass for pure black output
torch.backends.cudnn.enabled = False
import torch

try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    HAS_REALESRGAN = True
except ImportError as e:
    logging.warning(f"RealESRGAN import failed: {e}")
    HAS_REALESRGAN = False

_UPSAMPLERS = {}
MODEL_PATH = "/a0/agent-zero-data/workdir/bg-removal-service/bg-removal-service/data/models/RealESRGAN_x4plus.pth"


def _get_upsampler(tile=256):
    use_half = torch.cuda.is_available()
    key = f"x4_t{tile}_h{int(use_half)}"
    if key in _UPSAMPLERS:
        return _UPSAMPLERS[key]

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(
        scale=4,
        model_path=MODEL_PATH,
        model=model,
        tile=tile,
        tile_pad=10,
        pre_pad=0,
        half=use_half,
    )
    _UPSAMPLERS[key] = upsampler
    return upsampler


def get_cleanup_func():
    try:
        import app.pipeline.final_edge_cleanup as fec
        return getattr(fec, "final_edge_cleanup", lambda x: x)
    except Exception:
        return lambda x: x


def edge_smear(rgb, alpha, iterations=3):
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


def _hw_profile(mode="2x"):
    if torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        if vram_gb > 10:
            return (448 if mode == "2x" else 256, 36 if mode == "2x" else 20)
        if vram_gb > 6:
            return (384 if mode == "2x" else 224, 25 if mode == "2x" else 16)
        return (320 if mode == "2x" else 192, 20 if mode == "2x" else 12)
    if torch.backends.mps.is_available():
        return (320 if mode == "2x" else 192, 20 if mode == "2x" else 12)
    return (256 if mode == "2x" else 192, 9 if mode == "2x" else 6)


def upscale_and_reclean(rgba_image, mode="4x_topaz"):
    scale = 4 if mode == "4x_topaz" else 2
    if not HAS_REALESRGAN:
        return rgba_image, {"pass": True, "reasons": ["realesrgan_unavailable"]}

    h_full, w_full = rgba_image.shape[:2]
    alpha_channel = rgba_image[:, :, 3]
    coords = cv2.findNonZero(alpha_channel)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        b = 16
        x1, y1 = max(0, x - b), max(0, y - b)
        x2, y2 = min(w_full, x + w + b), min(h_full, y + h + b)
        rgba_image = rgba_image[y1:y2, x1:x2]
    else:
        x1, y1, x2, y2 = 0, 0, w_full, h_full

    tile, max_tiles = _hw_profile(mode="2x" if scale == 2 else "4x")
    upsampler = _get_upsampler(tile=tile)

    h_orig, w_orig = rgba_image.shape[:2]
    max_pixels = max_tiles * (tile * tile)
    if w_orig * h_orig > max_pixels:
        ratio = float(np.sqrt(max_pixels / (w_orig * h_orig)))
        new_w, new_h = int(w_orig * ratio), int(h_orig * ratio)
        rgba_image = cv2.resize(rgba_image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    rgb = rgba_image[:, :, :3]
    alpha = rgba_image[:, :, 3]
    smeared = edge_smear(rgb, alpha, iterations=3)
    out_rgb, _ = upsampler.enhance(smeared, outscale=scale)

    h, w = rgba_image.shape[:2]
    target = (w * scale, h * scale)
    a_cubic = cv2.resize(alpha, target, interpolation=cv2.INTER_CUBIC)
    a_area = cv2.resize(alpha, target, interpolation=cv2.INTER_AREA)
    out_alpha = np.clip(0.7 * a_cubic + 0.3 * a_area, 0, 255).astype(np.uint8)

    out_rgb = apply_unsharp_mask(out_rgb, amount=0.30 if mode == "2x" else 0.45, radius=1.0)
    out_alpha[out_alpha < 12] = 0
    out_alpha[out_alpha > 245] = 255

    merged = cv2.cvtColor(out_rgb, cv2.COLOR_BGR2BGRA)
    merged[:, :, 3] = out_alpha

    ch_up, cw_up = merged.shape[:2]
    cw_orig = x2 - x1
    overall_scale = cw_up / float(cw_orig) if cw_orig > 0 else scale

    final_w, final_h = int(w_full * overall_scale), int(h_full * overall_scale)
    final_x1, final_y1 = int(x1 * overall_scale), int(y1 * overall_scale)

    canvas = np.zeros((final_h, final_w, 4), dtype=np.uint8)
    ph, pw = merged.shape[:2]
    end_y, end_x = min(final_y1 + ph, final_h), min(final_x1 + pw, final_w)
    canvas[final_y1:end_y, final_x1:end_x] = merged[: end_y - final_y1, : end_x - final_x1]
    merged = canvas

    final_img = fit_and_pad_to_4096(merged) if mode == "4x_topaz" else merged

    cleanup_func = get_cleanup_func()
    try:
        final_rgba = cleanup_func(final_img)
    except Exception as e:
        logging.error(f"Re-cleanup failed: {e}")
        final_rgba = final_img

    return final_rgba, {"pass": True, "reasons": []}
