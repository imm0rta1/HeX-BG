import cv2
import numpy as np

def detect_hair_fur(alpha_mask: np.ndarray):
    edges = cv2.Canny(alpha_mask, 100, 200)
    edge_density = np.count_nonzero(edges) / alpha_mask.size
    is_hairy = edge_density > 0.01
    return is_hairy, {"density": edge_density}
