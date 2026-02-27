import cv2
import numpy as np

def _remove_tiny_outside_allowed(alpha: np.ndarray, allowed: np.ndarray, min_area: int = 24, alpha_thresh: int = 8):
    n, labels, stats, _ = cv2.connectedComponentsWithStats((alpha >= alpha_thresh).astype(np.uint8), connectivity=8)
    out = alpha.copy()
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area:
            comp = labels == i
            if not np.any(allowed & comp):
                out[comp] = 0
    return out

def final_edge_cleanup(rgba: np.ndarray, is_hairy: bool = True):
    out = rgba.copy()
    rgb = out[:, :, :3]
    a = out[:, :, 3].astype(np.uint8)

    fg_core = (a >= 20).astype(np.uint8) * 255

    n, labels, stats, _ = cv2.connectedComponentsWithStats((fg_core > 0).astype(np.uint8), connectivity=8)
    if n > 1:
        main_id = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
        main_mask = (labels == main_id).astype(np.uint8) * 255
    else:
        main_mask = fg_core

    k13 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    allowed = cv2.dilate(main_mask, k13, iterations=1) > 0

    # 1) remove far haze
    haze_far = (a >= 1) & (a <= 80) & (~allowed)
    a[haze_far] = 0

    # 2) remove tiny components outside allowed (pre)
    a = _remove_tiny_outside_allowed(a, allowed, min_area=24, alpha_thresh=8)

    # 3) edge band operations
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg_now = (a >= 5).astype(np.uint8) * 255
    inner = cv2.erode(fg_now, k3, iterations=1)
    edge_band = cv2.subtract(fg_now, inner) > 0
    semi_edge = edge_band & (a >= 8) & (a <= 180)

    # 4) suppress bright-neutral halo-like pixels (VFX Color Pull)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    halo_like = semi_edge & (sat < 35) & (val > 185)
    smooth_rgb = cv2.bilateralFilter(rgb, d=7, sigmaColor=35, sigmaSpace=35)
    rgb[halo_like] = smooth_rgb[halo_like]

    outside_edge = ~edge_band

    if is_hairy:
        # =========================================================
        # HAIRY / FEATHER ROUTE (Soft edges, preserve micro-alpha)
        # =========================================================
        smoothed_alpha = cv2.medianBlur(a, 3)
        blend_factor = 0.25  # 25% strength anti-stair
        a_float = a.astype(np.float32)
        smoothed_float = smoothed_alpha.astype(np.float32)
        blended = (a_float * (1.0 - blend_factor) + smoothed_float * blend_factor)
        
        a[edge_band] = blended[edge_band].astype(np.uint8)
        a[(outside_edge) & (a <= 70)] = 0
        a[(edge_band) & (a < 3)] = 0
    else:
        # =========================================================
        # SOLID OBJECT ROUTE (Razor-sharp, Gamma Hardened edges)
        # =========================================================
        # Steep Sigmoid Snapping: Force gray pixels to snap to 0 or 255
        edge_vals = a[edge_band].astype(np.float32)
        snapped = np.clip((edge_vals - 78) * (255.0 / 100.0), 0, 255)
        a[edge_band] = snapped.astype(np.uint8)

        # Harder clamping outside edge to kill haze entirely
        a[(outside_edge) & (a <= 120)] = 0

        # Harder clamp inside edge band to maintain geometric solidity
        a[(edge_band) & (a < 35)] = 0
        a[a > 220] = 255

    # 7) remove tiny components again AFTER clamps
    a = _remove_tiny_outside_allowed(a, allowed, min_area=24, alpha_thresh=6)

    rgb[a == 0] = 0

    out[:, :, :3] = rgb
    out[:, :, 3] = a
    return out
