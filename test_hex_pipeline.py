import sys
import os
from PIL import Image
import numpy as np
import json

sys.path.append(os.path.join('/a0/usr/workdir/bg-removal-service/bg-removal-service', 'app'))

from pipeline.segment_primary import PrimarySegmenter
from pipeline.qc_halo_haze_check import qc_halo_haze_check

def run_test():
    input_path = "/a0/usr/workdir/bg-removal-service/bg-removal-service/data/test_images/petela.png"
    output_path = "/a0/usr/workdir/bg-removal-service/bg-removal-service/data/test_images/petela_out_perfect_hex.png"

    img = Image.open(input_path)
    segmenter = PrimarySegmenter(model_name="isnet-general-use")
    result = segmenter.process(img, auto_cleanup=True)

    cutout = result['cutout']
    cutout.save(output_path)

    cutout_np = np.array(cutout)
    qc = qc_halo_haze_check(
        cutout_np, 
        haze_max_ratio=0.003, 
        halo_max_score=0.12, 
        orphan_min_area=12
    )

    print("--- QC JSON RESULT ---")
    print(json.dumps(qc, indent=2))
    print("OUTPUT_PNG:", output_path)

if __name__ == "__main__":
    run_test()
