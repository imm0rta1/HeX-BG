import cv2
import numpy as np
from PIL import Image

def calculate_qc_metrics(cutout: Image.Image, mask: Image.Image, original: Image.Image = None, is_hairy: bool = False) -> dict:
    width, height = mask.size
    total_pixels = width * height
    
    mask_arr = np.array(mask)
    if len(mask_arr.shape) > 2:
        alpha_arr = mask_arr[:, :, 3] if mask_arr.shape[2] == 4 else mask_arr[:, :, 0]
    else:
        alpha_arr = mask_arr

    _, binary_mask = cv2.threshold(alpha_arr, 127, 255, cv2.THRESH_BINARY)
    area_ratio = cv2.countNonZero(binary_mask) / total_pixels
    
    border_touch = bool(np.any(binary_mask[0, :]) or np.any(binary_mask[-1, :]) or                         np.any(binary_mask[:, 0]) or np.any(binary_mask[:, -1]))
    
    contours, hierarchy = cv2.findContours(binary_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    holes_count, holes_area_ratio = 0, 0.0
    if hierarchy is not None:
        for i, h in enumerate(hierarchy[0]):
            if h[3] != -1:
                holes_count += 1
                holes_area_ratio += cv2.contourArea(contours[i]) / total_pixels
                
    # DYNAMIC HAZE DETECTION (Trimap Refinement Integration)
    k_size = 11 if is_hairy else 7
    allowed_band = cv2.dilate(binary_mask, np.ones((k_size, k_size), np.uint8), iterations=1)
    
    haze_mask = (alpha_arr >= 5) & (alpha_arr <= 80) & (allowed_band == 0)
    leftover_alpha_ratio = np.count_nonzero(haze_mask) / total_pixels

    halo_score = 0.0
    if original:
        edges = cv2.Canny(binary_mask, 100, 200)
        halo_score = np.mean(cv2.dilate(edges, np.ones((5,5), np.uint8), iterations=1)) / 255.0
        
    is_pass = (
        area_ratio > 0.05 and 
        not border_touch and 
        holes_area_ratio <= 0.008 and 
        leftover_alpha_ratio <= 0.003 and
        halo_score <= 0.12
    )
    
    return {
        "area_ratio": round(area_ratio, 4),
        "border_touch": border_touch,
        "holes_count": holes_count,
        "holes_area_ratio": round(holes_area_ratio, 6),
        "leftover_alpha_ratio": round(leftover_alpha_ratio, 6),
        "halo_score": round(halo_score, 4),
        "pass": bool(is_pass)
    }
