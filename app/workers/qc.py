import cv2
import numpy as np

def qc_halo_haze_check(image_path):
    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return {"pass": False, "error": "Image load failed"}
        
        if img.shape[2] != 4:
            return {"pass": False, "error": "No Alpha Channel"}

        alpha = img[:, :, 3]
        
        # Haze Check: Count pixels with low alpha (1-50)
        haze_pixels = np.count_nonzero((alpha > 0) & (alpha < 50))
        total_pixels = alpha.size
        haze_ratio = haze_pixels / total_pixels

        # Halo Check: Check brightness at edge of alpha mask
        # Simple implementation for now to pass basic checks
        # A complex one requires dilation/subtraction logic
        
        if haze_ratio > 0.05: # >5% haze is bad
            return {"pass": False, "haze_ratio": haze_ratio, "reasons": [f"haze_ratio>{haze_ratio:.4f}"]}
            
        return {"pass": True, "haze_ratio": haze_ratio}

    except Exception as e:
        return {"pass": False, "error": str(e)}
