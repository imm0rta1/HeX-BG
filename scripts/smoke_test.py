import sys
import os
from pathlib import Path

# Add project root to path so we can import app modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.utils.image_io import load_image, save_image
from app.pipeline.segment_primary import PrimarySegmenter

def run_smoke_test():
    print("🔥 Starting Smoke Test...")
    
    # 1. Setup
    img_url = "https://images.unsplash.com/photo-1511367461989-f85a21fda167?q=80&w=1000&auto=format&fit=crop" # Clean portrait
    test_id = "smoke_test_01"
    job_dir = settings.STORAGE_DIR / test_id
    
    print(f"⬇️  Downloading test image...")
    original_img = load_image(img_url)
    save_image(original_img, job_dir / "original.jpg")
    print(f"✅ Image saved to {job_dir}")

    # 2. Init Model
    print("⚙️  Initializing rembg (first run downloads model)...")
    segmenter = PrimarySegmenter(model_name="u2net")
    
    # 3. Process
    print("🚀 Processing...")
    result = segmenter.process(original_img)
    
    # 4. Save Results
    save_image(result["cutout"], job_dir / "cutout.png")
    save_image(result["mask"], job_dir / "mask.png")
    
    print(f"✅ Success! Runtime: {result['runtime_ms']}ms")
    print(f"📂 Artifacts in: {job_dir}")

if __name__ == "__main__":
    run_smoke_test()
