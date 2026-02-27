import cv2
import numpy as np


def _largest_component(mask_u8: np.ndarray):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if n <= 1:
        return None, labels, stats
    areas = stats[1:, cv2.CC_STAT_AREA]
    main_id = int(np.argmax(areas)) + 1
    return main_id, labels, stats


def _resize_if_needed(rgb: np.ndarray, a: np.ndarray, max_side: int = 1024):
    h, w = a.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return rgb, a, 1.0
    s = max_side / float(m)
    nh, nw = int(round(h * s)), int(round(w * s))
    rgb2 = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    a2 = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_AREA)
    return rgb2, a2, s


def _roi_from_mask(mask_u8: np.ndarray, pad: int = 48):
    ys, xs = np.where(mask_u8 > 0)
    h, w = mask_u8.shape[:2]
    if len(xs) == 0:
        return 0, h, 0, w
    y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad + 1)
    return y0, y1, x0, x1


def qc_halo_haze_check(
    rgba: np.ndarray,
    haze_max_ratio: float = 0.003,
    halo_max_score: float = 0.12,
    orphan_min_area: int = 12,
    orphan_area_ratio_max: float = 0.0008,
    max_side: int = 1024,
):
    """
    Fast/stable QC for bg-removal outputs.
    - evaluates on downscaled mask (max_side)
    - computes metrics in ROI near subject
    - orphan gating uses area ratio (robust for hairy edges)
    """
    if rgba is None or rgba.ndim != 3 or rgba.shape[2] != 4:
        return {"pass": False, "reasons": ["invalid_rgba"]}

    rgb = rgba[:, :, :3].astype(np.uint8)
    a = rgba[:, :, 3].astype(np.uint8)

    # 1. Downscale for speed on massive/noisy images
    rgb, a, scale = _resize_if_needed(rgb, a, max_side=max_side)

    fg_soft = (a >= 5).astype(np.uint8) * 255
    fg_core = (a >= 20).astype(np.uint8) * 255

    fg_px = int(cv2.countNonZero(fg_soft))
    if fg_px == 0:
        return {
            "pass": False,
            "haze_ratio": 1.0,
            "halo_score": 1.0,
            "orphan_count": 0,
            "orphan_area_ratio": 1.0,
            "reasons": ["empty_foreground"],
        }

    main_id, labels, stats = _largest_component((fg_core > 0).astype(np.uint8))
    if main_id is None:
        return {
            "pass": False,
            "haze_ratio": 1.0,
            "halo_score": 1.0,
            "orphan_count": 0,
            "orphan_area_ratio": 1.0,
            "reasons": ["no_main_component"],
        }

    main_mask = (labels == main_id).astype(np.uint8) * 255

    # 2. ROI Optimization: Crop to subject + padding
    # This prevents processing empty space on 4k images
    y0, y1, x0, x1 = _roi_from_mask(main_mask, pad=max(24, int(round(48 * scale))))
    rgb = rgb[y0:y1, x0:x1]
    a = a[y0:y1, x0:x1]
    main_mask = main_mask[y0:y1, x0:x1]

    # Neighborhood around valid subject wisps
    ksz = max(5, int(round(11 * scale)))
    if ksz % 2 == 0:
        ksz += 1
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksz, ksz))
    allowed = cv2.dilate(main_mask, k, iterations=1) > 0

    # Haze metric
    semi = (a >= 1) & (a <= 80)
    haze_mask = semi & (~allowed)
    haze_ratio = float(haze_mask.sum() / max(int((a > 0).sum()), 1))

    # Halo metric
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    main_er = cv2.erode(main_mask, k3, iterations=1)
    edge_band = cv2.subtract(main_mask, main_er) > 0

    hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    semi_edge = edge_band & (a >= 8) & (a <= 180)
    halo_candidates = semi_edge & (sat < 35) & (val > 185)
    edge_px = int(semi_edge.sum())
    halo_score = float(halo_candidates.sum() / max(edge_px, 1))

    # Orphans metric (outside neighborhood only)
    n2, labels2, stats2, _ = cv2.connectedComponentsWithStats((a >= 8).astype(np.uint8), connectivity=8)
    orphan_count = 0
    orphan_area = 0
    orphan_min_area_ds = max(3, int(round(orphan_min_area * scale * scale)))
    
    for i in range(1, n2):
        area = int(stats2[i, cv2.CC_STAT_AREA])
        if area >= orphan_min_area_ds:
            continue
        comp = labels2 == i
        # Fast check: if component bbox is far from allowed, it's orphan
        if not np.any(allowed & comp):
            orphan_count += 1
            orphan_area += area

    # Normalize area ratio against foreground pixels
    orphan_area_ratio = float(orphan_area / max(int((a > 0).sum()), 1))

    reasons = []
    if haze_ratio > haze_max_ratio:
        reasons.append(f"haze_ratio>{haze_max_ratio}")
    if halo_score > halo_max_score:
        reasons.append(f"halo_score>{halo_max_score}")
    if orphan_area_ratio > orphan_area_ratio_max:
        reasons.append(f"orphan_area_ratio>{orphan_area_ratio_max}")

    return {
        "pass": len(reasons) == 0,
        "haze_ratio": round(haze_ratio, 6),
        "halo_score": round(halo_score, 6),
        "orphan_count": int(orphan_count),
        "orphan_area_ratio": round(orphan_area_ratio, 6),
        "reasons": reasons,
    }
