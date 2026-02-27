import cv2
import numpy as np


def detect_hair_fur(alpha: np.ndarray):
    """
    alpha: uint8 mask (0..255), shape HxW
    returns: (is_hairy: bool, metrics: dict)
    """
    if alpha.dtype != np.uint8:
        alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    h, w = alpha.shape[:2]
    total = h * w
    if total == 0:
        return False, {"reason": "empty"}

    fg = (alpha >= 5).astype(np.uint8) * 255

    fg_px = int(cv2.countNonZero(fg))
    if fg_px < max(200, int(0.002 * total)):
        return False, {"reason": "tiny_fg"}

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg_er = cv2.erode(fg, k3, iterations=1)
    edge_band = cv2.subtract(fg, fg_er)

    edge_px = int(cv2.countNonZero(edge_band))
    if edge_px < 100:
        return False, {"reason": "tiny_edge_band"}

    band_vals = alpha[edge_band > 0]
    soft_ratio = float(np.mean((band_vals >= 10) & (band_vals <= 180)))

    can = cv2.Canny(alpha, 40, 120)
    can_band = cv2.bitwise_and(can, can, mask=edge_band)
    fine_density = float(cv2.countNonZero(can_band) / max(edge_px, 1))

    contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    roughness = 1.0
    if contours:
        c = max(contours, key=cv2.contourArea)
        area = float(max(cv2.contourArea(c), 1.0))
        peri = float(cv2.arcLength(c, True))
        roughness = (peri * peri) / (4.0 * np.pi * area)

    c1 = soft_ratio > 0.38
    c2 = fine_density > 0.16
    c3 = roughness > 2.40
    score = int(c1) + int(c2) + int(c3)
    is_hairy = score >= 2

    metrics = {
        "soft_ratio": round(soft_ratio, 4),
        "fine_density": round(fine_density, 4),
        "roughness": round(roughness, 4),
        "hair_flags": {"soft": c1, "fine": c2, "rough": c3},
        "hair_score": score,
        "edge_px": edge_px,
        "fg_px": fg_px,
    }
    return is_hairy, metrics


def adaptive_kernel_size(h: int, w: int, min_k: int = 1, max_k: int = 7):
    k = max(min_k, int(round(min(h, w) / 300)))
    k = min(k, max_k)
    if k % 2 == 0:
        k += 1
    return k
