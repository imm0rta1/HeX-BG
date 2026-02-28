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

def hq_color_pull(rgb: np.ndarray, alpha: np.ndarray, is_hairy: bool) -> np.ndarray:
    core_thresh = 150 if is_hairy else 200
    core_mask = (alpha >= core_thresh).astype(np.uint8)
    
    if not is_hairy:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        core_mask = cv2.erode(core_mask, kernel, iterations=2)
        
    core_f = core_mask.astype(np.float32)
    core_exp = np.expand_dims(core_f, axis=-1)
    
    core_rgb = rgb.astype(np.float32) * core_exp
    
    kernel_sizes = [(7,7), (15,15), (31,31)] if is_hairy else [(3,3), (7,7), (15,15), (31,31)]
    
    extended_rgb = np.zeros_like(core_rgb)
    weight_sum = np.zeros_like(core_exp)
    
    for k in kernel_sizes:
        b_rgb = cv2.GaussianBlur(core_rgb, k, 0)
        b_mask_2d = cv2.GaussianBlur(core_f, k, 0)
        b_mask = np.expand_dims(b_mask_2d, axis=-1)
        
        extended_rgb += b_rgb
        weight_sum += b_mask
        
    weight_sum[weight_sum == 0] = 1.0
    extended_rgb = extended_rgb / weight_sum
    
    bg_mask = (alpha == 0).astype(np.uint8)
    k_bg = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    near_bg = cv2.dilate(bg_mask, k_bg, iterations=1) > 0
    
    edge_band = (alpha > 0) & (core_mask == 0) & near_bg
    
    new_rgb = rgb.copy()
    new_rgb[edge_band] = np.clip(extended_rgb[edge_band], 0, 255).astype(np.uint8)
    return new_rgb

def punch_solid_background(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    if h < 20 or w < 20: return a
    
    corners = np.array([rgb[5,5], rgb[5,w-5], rgb[h-5,5], rgb[h-5,w-5]], dtype=np.int32)
    
    if np.max(np.ptp(corners, axis=0)) < 60:
        bg_bgr = np.median(corners, axis=0).astype(np.uint8)
        bg_bgr_1x1 = np.array([[bg_bgr]], dtype=np.uint8)
        bg_hsv = cv2.cvtColor(bg_bgr_1x1, cv2.COLOR_BGR2HSV)[0,0]
        bg_hue = int(bg_hsv[0])
        bg_sat = int(bg_hsv[1])
        
        img_hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
        
        if bg_sat < 15:
            bg_val = int(bg_hsv[2])
            v_channel = img_hsv[:,:,2]
            mask = (v_channel >= max(0, bg_val - 30)) & (v_channel <= min(255, bg_val + 30))
            a[mask] = 0
        else:
            hue_tolerance = 8
            # STRICT SATURATION GATE:
            # Shadows inside letters retain the background's high saturation (~250).
            # Leaves are a natural, washed-out green with lower saturation (~160).
            # By demanding a saturation above ~200, we protect the leaves completely!
            sat_floor = max(30, bg_sat - 50)
            
            lower_hue = bg_hue - hue_tolerance
            upper_hue = bg_hue + hue_tolerance
            
            if lower_hue < 0:
                mask1 = cv2.inRange(img_hsv, np.array([0, sat_floor, 30]), np.array([upper_hue, 255, 255]))
                mask2 = cv2.inRange(img_hsv, np.array([179 + lower_hue, sat_floor, 30]), np.array([179, 255, 255]))
                green_mask = mask1 | mask2
            elif upper_hue > 179:
                mask1 = cv2.inRange(img_hsv, np.array([lower_hue, sat_floor, 30]), np.array([179, 255, 255]))
                mask2 = cv2.inRange(img_hsv, np.array([0, sat_floor, 30]), np.array([upper_hue - 179, 255, 255]))
                green_mask = mask1 | mask2
            else:
                lower_bound = np.array([lower_hue, sat_floor, 30])
                upper_bound = np.array([upper_hue, 255, 255])
                green_mask = cv2.inRange(img_hsv, lower_bound, upper_bound)
                
            a[green_mask > 0] = 0
            
        n, labels, stats, _ = cv2.connectedComponentsWithStats((a > 0).astype(np.uint8), connectivity=8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < 15:
                a[labels == i] = 0
    return a

def final_edge_cleanup(rgba: np.ndarray, is_hairy: bool = False):
    out = rgba.copy()
    rgb = out[:, :, :3]
    a = out[:, :, 3].astype(np.uint8)

    a = punch_solid_background(rgb, a)
    rgb = hq_color_pull(rgb, a, is_hairy)

    fg_core = (a >= 200).astype(np.uint8) * 255
    n, labels, stats, _ = cv2.connectedComponentsWithStats((fg_core > 0).astype(np.uint8), connectivity=8)
    if n > 1:
        main_id = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
        main_mask = (labels == main_id).astype(np.uint8) * 255
    else:
        main_mask = fg_core

    k13 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    allowed = cv2.dilate(main_mask, k13, iterations=1) > 0

    haze_far = (a >= 1) & (a <= 80) & (~allowed)
    a[haze_far] = 0
    a = _remove_tiny_outside_allowed(a, allowed, min_area=24, alpha_thresh=8)

    if not is_hairy:
        a_float = a.astype(np.float32)
        a_float = (a_float - 128.0) * 4.0 + 128.0
        a = np.clip(a_float, 0, 255).astype(np.uint8)
        a[a < 32] = 0
    else:
        a[a < 12] = 0
        edge_band = (a > 5) & (a < 200)
        smoothed_alpha = cv2.medianBlur(a, 3)
        a_float = a.astype(np.float32)
        smoothed_float = smoothed_alpha.astype(np.float32)
        blended = (a_float * 0.75 + smoothed_float * 0.25)
        a[edge_band] = blended[edge_band].astype(np.uint8)

    rgb[a == 0] = 0
    out[:, :, :3] = rgb
    out[:, :, 3] = a
    return out
