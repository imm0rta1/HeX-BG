import sys
import os
import traceback
import torch

torch.multiprocessing.set_sharing_strategy('file_system')

# Add app to path
sys.path.append('/a0/usr/workdir/bg-removal-service/bg-removal-service')
from app.workers.tasks import process_image_task

job_id = 'd57c9553-80ec-47f1-8bb1-96f5a0a21cab' # Failed job from worker logs
img_path = f'/a0/usr/workdir/bg-removal-service/bg-removal-service/data/jobs/{job_id}/original.png'

print(f"--- STARTING DIRECT TEST FOR {job_id} ---")
if not os.path.exists(img_path):
    print("Error: Original image missing.")
else:
    try:
        print("Running pipeline: isnet-anime + 2x Upscale...")
        process_image_task(job_id, img_path, 'isnet-anime', 0, 0, True, False, '2x')
        print("--- SUCCESS ---")
    except Exception as e:
        print("--- PYTHON ERROR ---")
        traceback.print_exc()
