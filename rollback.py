import os

# --- 1. Revert routes_jobs.py ---
routes_code = """from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.core.config import settings
from app.api.schemas import JobResponse
from redis import Redis
from rq import Queue
from app.workers.tasks import process_image_task
import uuid, time, shutil, logging, os

router = APIRouter()
logger = logging.getLogger(__name__)
redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
q = Queue(connection=redis_conn)

@router.post("/jobs", response_model=JobResponse)
async def create_job(
    file: UploadFile = File(...),
    model_name: str = Form("isnet-general-use"),
    erode_size: int = Form(0),
    blur_size: int = Form(0),
    auto_cleanup: bool = Form(True),
    upscale: bool = Form(False)
):
    job_id = str(uuid.uuid4())
    job_dir = settings.STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    original_path = job_dir / f"original_{file.filename}"
    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    q.enqueue(process_image_task, job_id, str(original_path), model_name, erode_size, blur_size, auto_cleanup, upscale, job_id=job_id, job_timeout=1200)

    return JobResponse(
        job_id=job_id,
        status="queued",
        created_at=start_time
    )

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    job_dir = settings.STORAGE_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        job = q.fetch_job(job_id)
        if job and job.result:
            return JobResponse(job_id=job_id, status="done", created_at=job_dir.stat().st_ctime, result=job.result)
        if job and job.exc_info:
             return JobResponse(job_id=job_id, status="failed", created_at=job_dir.stat().st_ctime, result={"error": "Processing failed"})
    except Exception as e:
        pass
    if (job_dir / "cutout.png").exists():
        return JobResponse(job_id=job_id, status="done", created_at=job_dir.stat().st_ctime, result={"cutout_url": f"/files/{job_id}/cutout.png", "mask_url": f"/files/{job_id}/mask.png"})
    return JobResponse(job_id=job_id, status="processing", created_at=job_dir.stat().st_ctime)
"""
with open('/a0/usr/workdir/bg-removal-service/bg-removal-service/app/api/routes_jobs.py', 'w') as f:
    f.write(routes_code)

# --- 2. Revert tasks.py ---
tasks_code = """import time, sys, os, logging
from pathlib import Path
from PIL import Image
import redis
from rq import get_current_job
import numpy as np
import cv2

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path: sys.path.append(str(BASE_DIR))

from app.core.config import settings
from app.utils.image_io import load_image, save_image
from app.pipeline.segment_primary import PrimarySegmenter
from app.pipeline.qc_halo_haze_check import qc_halo_haze_check

logger = logging.getLogger(__name__)
segmenters = {}
upscalers = {}

def get_worker_upscaler(scale=2):
    if scale not in upscalers:
        from app.pipeline.upscale import ImageUpscaler
        upscalers[scale] = ImageUpscaler(scale=scale)
    return upscalers[scale]

def get_worker_segmenter(model_name="isnet-general-use"):
    if model_name not in segmenters:
        settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        os.environ['U2NET_HOME'] = str(settings.MODEL_DIR)
        segmenters[model_name] = PrimarySegmenter(model_name=model_name)
    return segmenters[model_name]

def process_image_task(job_id: str, image_path: str, model_name: str = "isnet-general-use", erode_size: int = 0, blur_size: int = 0, auto_cleanup: bool = True, upscale: bool = False):
    try:
        job_dir = settings.STORAGE_DIR / job_id
        model = get_worker_segmenter(model_name)
        img = load_image(image_path)

        result = model.process(img, erode_size=erode_size, blur_size=blur_size, auto_cleanup=auto_cleanup)

        cutout_img = result["cutout"]
        mask_img = result["mask"]

        if upscale:
            upscaler = get_worker_upscaler(scale=2)
            cutout_np = np.array(cutout_img)
            upscaled_np = upscaler.process(cutout_np)
            cutout_img = Image.fromarray(upscaled_np)

            mask_np = np.array(mask_img)
            mask_up = cv2.resize(mask_np, (cutout_img.width, cutout_img.height), interpolation=cv2.INTER_LANCZOS4)
            mask_img = Image.fromarray(mask_up)

        # Strict QC Gate (OpenClaw V3)
        cutout_np = np.array(cutout_img)
        qc_metrics = qc_halo_haze_check(cutout_np, haze_max_ratio=0.003, halo_max_score=0.12, orphan_min_area=12)
        if not qc_metrics["pass"]:
            logger.error(f"QC failed: {qc_metrics}")
            logger.warning(f"QC failed but returning image: {qc_metrics}")

        save_image(cutout_img, job_dir / "cutout.png")
        save_image(mask_img, job_dir / "mask.png")

        return {
            "status": "done",
            "runtime_ms": result["runtime_ms"],
            "qc": qc_metrics,
            "cutout_url": f"/files/{job_id}/cutout.png",
            "mask_url": f"/files/{job_id}/mask.png"
        }
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise e
"""
with open('/a0/usr/workdir/bg-removal-service/bg-removal-service/app/workers/tasks.py', 'w') as f:
    f.write(tasks_code)

# --- 3. Revert segment_primary.py ---
seg_code = """import time
import rembg
import numpy as np
from PIL import Image
import cv2
from .detect_hair_fur import detect_hair_fur
from .final_edge_cleanup import final_edge_cleanup

class PrimarySegmenter:
    def __init__(self, model_name="isnet-general-use"):
        self.model_name = model_name
        self.session = rembg.new_session(model_name=self.model_name)

    def process(self, image: Image.Image, erode_size: int = 0, blur_size: int = 0, auto_cleanup: bool = True) -> dict:
        start_time = time.time()
        orig_image = image.convert("RGB")

        result = rembg.remove(
            image,
            session=self.session,
            only_mask=False,
            post_process_mask=False,
            alpha_matting=True,
            alpha_matting_foreground_threshold=235,
            alpha_matting_background_threshold=8,
            alpha_matting_erode_size=2
        )
        result_np = np.array(result)
        mask_raw = result_np[:, :, 3].copy()

        is_hairy = False
        if auto_cleanup:
            is_hairy, hair_metrics = detect_hair_fur(mask_raw)

            if not is_hairy:
                lookup = np.array([
                    np.clip(pow(i / 255.0, 1.35) * 255.0, 0, 255)
                    for i in range(256)
                ], dtype=np.uint8)
                mask_np = cv2.LUT(mask_raw, lookup)
            else:
                mask_np = mask_raw.copy()

            clamp = 4 if is_hairy else 6
            mask_np[mask_np < clamp] = 0

            result_np[:, :, 3] = mask_np
            result_np = final_edge_cleanup(result_np)
            mask_np = result_np[:, :, 3].copy()
        else:
            mask_np = mask_raw

        return {
            "cutout": Image.fromarray(result_np),
            "mask": Image.fromarray(mask_np),
            "runtime_ms": int((time.time() - start_time) * 1000),
            "hair_detected": is_hairy
        }
"""
with open('/a0/usr/workdir/bg-removal-service/bg-removal-service/app/pipeline/segment_primary.py', 'w') as f:
    f.write(seg_code)

# --- 4. Revert final_edge_cleanup.py ---
edge_code = """import cv2
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

def final_edge_cleanup(rgba: np.ndarray):
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

    # 3.5) Anti-stair edge refinement (reduce quantization)
    smoothed_alpha = cv2.medianBlur(a, 3)
    blend_factor = 0.25  # 25% strength
    a_float = a.astype(np.float32)
    smoothed_float = smoothed_alpha.astype(np.float32)
    blended = (a_float * (1.0 - blend_factor) + smoothed_float * blend_factor)

    # Apply to edge band to keep smooth ramp in [8..80]
    a[edge_band] = blended[edge_band].astype(np.uint8)

    # 4) suppress bright-neutral halo-like pixels
    hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    halo_like = semi_edge & (sat < 35) & (val > 185)
    smooth_rgb = cv2.bilateralFilter(rgb, d=7, sigmaColor=35, sigmaSpace=35)
    rgb[halo_like] = smooth_rgb[halo_like]

    # 5) stronger clamp outside edge only
    outside_edge = ~edge_band
    a[(outside_edge) & (a <= 70)] = 0

    # 6) tiny clamp in edge (keep soft ramp, avoid hard jumps)
    a[(edge_band) & (a < 3)] = 0

    # 7) remove tiny components again AFTER clamps
    a = _remove_tiny_outside_allowed(a, allowed, min_area=24, alpha_thresh=6)

    rgb[a == 0] = 0

    out[:, :, :3] = rgb
    out[:, :, 3] = a
    return out
"""
with open('/a0/usr/workdir/bg-removal-service/bg-removal-service/app/pipeline/final_edge_cleanup.py', 'w') as f:
    f.write(edge_code)

# --- 5. Revert App.tsx (Removing Eraser UI, keeping max-w/max-h upscale fix) ---
app_code = r"""import React, { useState } from 'react';

interface JobResult {
  status: string;
  qc?: any;
  cutout_url?: string;
  mask_url?: string;
}

function App() {
  const [, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [result, setResult] = useState<JobResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  
  const [modelName, setModelName] = useState<string>('isnet-general-use');
  const [erodeSize, setErodeSize] = useState<number>(0);
  const [blurSize, setBlurSize] = useState<number>(0);
  const [autoCleanup, setAutoCleanup] = useState<boolean>(true);
  const [upscale, setUpscale] = useState<boolean>(false);
  const [bgMode, setBgMode] = useState<string>('checkerboard');
  const [customBg, setCustomBg] = useState<string>('#FF00FF');
  const [zoom, setZoom] = useState<number>(1);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setFile(f);
      setPreview(URL.createObjectURL(f));
      setStatus('idle');
      setResult(null);
      setZoom(1);
    }
  };

  const uploadJob = async () => {
    if (!file) return;
    setStatus('uploading');
    setZoom(1);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_name', modelName);
    formData.append('erode_size', erodeSize.toString());
    formData.append('blur_size', blurSize.toString());
    formData.append('auto_cleanup', autoCleanup.toString());
    formData.append('upscale', upscale.toString());

    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      setJobId(data.job_id);
      setStatus('queued');
      pollStatus(data.job_id);
    } catch (err) {
      console.error(err);
      setStatus('error');
    }
  };

  const pollStatus = async (id: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${id}`);
        const data = await res.json();
        
        if (data.status === 'done') {
          clearInterval(interval);
          setStatus('done');
          setResult(data.result);
        } else if (data.status === 'failed') {
          clearInterval(interval);
          setStatus('failed');
        }
      } catch (err) {
        clearInterval(interval);
        setStatus('error');
      }
    }, 1000);
  };

  const bgClasses: any = {
    checkerboard: "bg-[url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMUlEQVQ4T2NkYNgfQEhQGHAAksD///9OQXBwAmhmYABiwAEDo4D//w8wAAhE8QYQIAAA/3J/8b2mXbgAAAAASUVORK5CYII=')] bg-repeat",
    black: "bg-black",
    white: "bg-white",
    green: "bg-[#00FF00]",
    gray: "bg-gray-500"
  };

  return (
    <div className="h-screen w-screen overflow-hidden text-gray-200 selection:bg-[#00F0FF] selection:text-black relative flex flex-col">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400;1,700&family=Syne:wght@400..800&display=swap');
        body {
          margin: 0;
          overflow: hidden;
          background-color: #030303;
          background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
          font-family: 'Space Mono', monospace;
        }
        .font-display { font-family: 'Syne', sans-serif; }
        .glass-panel {
          background: rgba(10, 10, 10, 0.6);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .stagger-1 { animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both; }
        .stagger-2 { animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both; }
        
        .cyber-button {
          position: relative;
          background: transparent;
          color: #00F0FF;
          border: 1px solid #00F0FF;
          overflow: hidden;
          transition: all 0.3s ease;
        }
        .cyber-button::before {
          content: '';
          position: absolute;
          top: 0; left: -100%; width: 100%; height: 100%;
          background: linear-gradient(90deg, transparent, rgba(0, 240, 255, 0.4), transparent);
          transition: all 0.5s ease;
        }
        .cyber-button:hover::before { left: 100%; }
        .cyber-button:hover {
          background: rgba(0, 240, 255, 0.1);
          box-shadow: 0 0 15px rgba(0, 240, 255, 0.3);
        }
        .cyber-button.ready {
          background: transparent;
          color: #D4FF00;
          border-color: #D4FF00;
        }
        .cyber-button.ready::before {
          background: linear-gradient(90deg, transparent, rgba(212, 255, 0, 0.4), transparent);
        }
        .cyber-button.ready:hover {
          background: rgba(212, 255, 0, 0.1);
          box-shadow: 0 0 15px rgba(212, 255, 0, 0.3);
        }
        .cyber-button.executing {
          border-color: #FF003C;
          color: #FF003C;
          background: rgba(255, 0, 60, 0.1);
          box-shadow: 0 0 20px rgba(255, 0, 60, 0.4);
          animation: pulse 1s infinite alternate;
        }
        @keyframes pulse {
          from { box-shadow: 0 0 10px rgba(255, 0, 60, 0.2); }
          to { box-shadow: 0 0 25px rgba(255, 0, 60, 0.6); }
        }
        
        input[type=range] {
          -webkit-appearance: none;
          background: transparent;
          width: 100%;
        }
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          height: 16px; width: 8px;
          background: #00F0FF;
          cursor: pointer;
          border-radius: 0;
          margin-top: -7px;
        }
        input[type=range]::-webkit-slider-runnable-track {
          width: 100%; height: 2px;
          cursor: pointer;
          background: rgba(255, 255, 255, 0.2);
        }
        
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0, 240, 255, 0.3); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #00F0FF; }
      `}</style>

      <div className="fixed top-[-20%] left-[-10%] w-[50vw] h-[50vw] bg-[#00F0FF] rounded-full mix-blend-screen filter blur-[150px] opacity-[0.03] pointer-events-none z-0"></div>
      <div className="fixed bottom-[-20%] right-[-10%] w-[50vw] h-[50vw] bg-[#D4FF00] rounded-full mix-blend-screen filter blur-[150px] opacity-[0.03] pointer-events-none z-0"></div>

      <div className="w-full max-w-[1600px] mx-auto p-4 md:p-6 flex-1 flex flex-col min-h-0 z-10">
        
        <header className="shrink-0 mb-4 stagger-1 flex flex-col md:flex-row items-baseline justify-between border-b border-white/10 pb-4">
          <div>
            <h1 className="font-display text-3xl md:text-5xl font-bold tracking-tighter uppercase text-white">
              Surgical Extraction
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="text-[10px] tracking-[0.2em] text-[#00F0FF] border border-[#00F0FF]/30 px-2 py-1 rounded-sm uppercase bg-[#00F0FF]/5">
                V4 Perfect Mode
              </span>
              <span className="text-[9px] text-gray-500 tracking-widest uppercase">
                Hex OS / Agent Zero Integration
              </span>
            </div>
          </div>
          <div className="mt-4 md:mt-0 text-left md:text-right">
            <p className="text-[10px] text-gray-400 max-w-xs ml-auto leading-relaxed tracking-wider">
              High-fidelity neural matting.<br/> Zero edge destruction. VFX decontamination.
            </p>
          </div>
        </header>

        <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0 overflow-hidden">
          
          {/* Controls Column */}
          <div className="lg:w-[400px] xl:w-[450px] shrink-0 flex flex-col gap-6 overflow-y-auto custom-scrollbar pr-2 pb-6 lg:pb-0">
            
            <div className="glass-panel p-5 relative overflow-hidden group shrink-0">
              <div className="absolute top-0 left-0 w-1 h-full bg-white/10 group-hover:bg-[#00F0FF] transition-colors"></div>
              <h2 className="font-display text-lg mb-4 tracking-wide text-white uppercase flex justify-between items-end border-b border-white/5 pb-2">
                <span>01. Input</span>
                <span className="text-[9px] text-gray-600 tracking-widest">[ RAW_DATA ]</span>
              </h2>
              
              <label className="block w-full border border-dashed border-white/10 hover:border-[#00F0FF]/50 transition-all p-6 text-center cursor-pointer relative bg-white/5">
                <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
                <div className="text-[10px] tracking-widest text-gray-400 uppercase group-hover:text-[#00F0FF] transition-colors">
                  {file ? file.name : "[ SELECT IMAGE DATA ]"}
                </div>
              </label>

              {preview && (
                <div className="mt-4 relative p-1 border border-white/5 bg-black/50 h-40 flex items-center justify-center overflow-hidden">
                  <img src={preview} alt="Preview" className="w-full h-full object-contain opacity-80 mix-blend-screen" />
                </div>
              )}
            </div>

            <div className="glass-panel p-5 relative overflow-hidden shrink-0">
               <div className="absolute top-0 left-0 w-1 h-full bg-white/10 hover:bg-[#D4FF00] transition-colors"></div>
               <h2 className="font-display text-lg mb-6 tracking-wide text-white uppercase flex justify-between items-end border-b border-white/5 pb-2">
                <span>02. Parameters</span>
                <span className="text-[9px] text-gray-600 tracking-widest">[ SYS_CONF ]</span>
              </h2>

              <div className="space-y-8">
                <div className="group">
                  <label className="text-[9px] tracking-widest text-gray-500 block mb-2 uppercase group-hover:text-white transition-colors">Neural Core Model</label>
                  <div className="relative">
                    <select
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      className="w-full bg-black/50 border border-white/10 text-gray-300 p-2 text-[10px] tracking-wider focus:outline-none focus:border-[#D4FF00] transition-colors appearance-none cursor-pointer"
                    >
                      <option value="isnet-general-use">ISNet [ High Freq / Hair ]</option>
                      <option value="u2net">U2NET [ Standard ]</option>
                      <option value="isnet-anime">ISNet Anime [ Vector ]</option>
                      <option value="u2netp">U2NETp [ Fast ]</option>
                    </select>
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-[#D4FF00]/50 rotate-45 pointer-events-none"></div>
                  </div>
                </div>

                <div className="space-y-5">
                  <label className="flex items-start cursor-pointer group">
                    <div className="relative mt-1 mr-3">
                      <input type="checkbox" className="sr-only" checked={autoCleanup} onChange={(e) => setAutoCleanup(e.target.checked)} />
                      <div className={`w-4 h-4 border transition-colors flex items-center justify-center ${autoCleanup ? 'border-[#00F0FF] bg-[#00F0FF]/10' : 'border-white/20 group-hover:border-white/50'}`}>
                        {autoCleanup && <div className="w-1.5 h-1.5 bg-[#00F0FF]"></div>}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-white tracking-widest uppercase mb-1">Color Pull Decon</div>
                      <div className="text-[9px] text-gray-500 leading-relaxed tracking-wider">Extracts core colors to overwrite edge halo.</div>
                    </div>
                  </label>

                  <label className="flex items-start cursor-pointer group">
                    <div className="relative mt-1 mr-3">
                      <input type="checkbox" className="sr-only" checked={upscale} onChange={(e) => setUpscale(e.target.checked)} />
                      <div className={`w-4 h-4 border transition-colors flex items-center justify-center ${upscale ? 'border-[#D4FF00] bg-[#D4FF00]/10' : 'border-white/20 group-hover:border-white/50'}`}>
                        {upscale && <div className="w-1.5 h-1.5 bg-[#D4FF00]"></div>}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-white tracking-widest uppercase mb-1">2x Neural Upscale</div>
                      <div className="text-[9px] text-gray-500 leading-relaxed tracking-wider">Deep learning pass to hallucinate detail.</div>
                    </div>
                  </label>
                </div>

                <div className="space-y-5 pt-4 border-t border-white/5">
                  <div className="group pt-2">
                    <div className="flex justify-between text-[9px] tracking-widest text-gray-500 uppercase mb-3 group-hover:text-white transition-colors">
                      <span>Erosion Threshold</span>
                      <span className="text-[#00F0FF]">[{erodeSize}px]</span>
                    </div>
                    <input type="range" min="0" max="10" value={erodeSize} onChange={(e) => setErodeSize(parseInt(e.target.value))} />
                  </div>

                  <div className="group">
                    <div className="flex justify-between text-[9px] tracking-widest text-gray-500 uppercase mb-3 group-hover:text-white transition-colors">
                      <span>Edge Softness</span>
                      <span className="text-[#00F0FF]">[{blurSize}px]</span>
                    </div>
                    <input type="range" min="0" max="15" step="1" value={blurSize} onChange={(e) => setBlurSize(parseInt(e.target.value))} />
                  </div>
                </div>
              </div>
            </div>

            <div className="shrink-0">
              <button
                onClick={uploadJob}
                disabled={!file || status === 'uploading' || status === 'queued' || status === 'processing'}
                className={`w-full p-4 font-display font-bold text-xs tracking-[0.2em] uppercase transition-all flex items-center justify-center gap-2
                  ${status === 'processing' || status === 'queued' || status === 'uploading' ? 'cyber-button executing' : 
                    status === 'done' ? 'cyber-button' : 'cyber-button ready'} 
                  disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {status === 'processing' || status === 'queued' || status === 'uploading'
                  ? <span>[ EXECUTING... ]</span>
                  : (status === 'done' ? <span>[ RE-CALCULATE ]</span> : <span>[ INITIATE ]</span>)}
              </button>
            </div>
          </div>

          {/* Visualization Column */}
          <div className="flex-1 flex flex-col min-h-0 stagger-2">
            <div className="glass-panel flex-1 flex flex-col min-h-0 relative">
              
              <div className="shrink-0 flex flex-wrap gap-4 justify-between items-center p-3 border-b border-white/5 bg-white/5">
                <div className="text-[9px] tracking-widest uppercase text-gray-400 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-[#00F0FF] animate-pulse"></div>
                  OUTPUT.VIEWPORT
                </div>
              </div>

              <div className="flex-1 min-h-0 relative m-2 md:m-4">
                {status === 'done' && result ? (
                  <div 
                    className={`absolute inset-0 flex items-center justify-center ${bgMode !== 'custom' ? bgClasses[bgMode] : ''} border border-white/5 transition-colors duration-500 overflow-hidden`}
                    style={bgMode === 'custom' ? { backgroundColor: customBg } : {}}
                  >
                     <img 
                       src={result.cutout_url} 
                       alt="Cutout" 
                       className="max-w-full max-h-full object-contain drop-shadow-2xl z-10 transition-transform duration-200"
                       style={{ transform: `scale(${zoom})`, transformOrigin: 'center center' }}
                     />
                     
                     <div className="absolute inset-0 pointer-events-none border border-white/10 z-20"></div>

                     {/* Main Floating Controls: Bg Picker and Zoom */}
                     <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 flex flex-col sm:flex-row items-center gap-4 sm:gap-6 glass-panel px-6 py-4 rounded-xl sm:rounded-full border border-white/20 shadow-[0_10px_40px_rgba(0,0,0,0.8)] backdrop-blur-xl">
                       
                       <div className="flex items-center gap-4 sm:border-r border-white/20 sm:pr-6">
                         <span className="text-[10px] tracking-[0.2em] text-gray-400 uppercase font-bold">Bg_Color:</span>
                         <div className="flex items-center gap-3">
                           {['checkerboard', 'black', 'white', 'green', 'gray'].map(mode => (
                             <button 
                               key={mode} 
                               onClick={() => setBgMode(mode)}
                               className={`w-6 h-6 rounded-full border-2 transition-all hover:scale-125 ${bgMode === mode ? 'border-[#00F0FF] scale-110 shadow-[0_0_15px_rgba(0,240,255,0.6)]' : 'border-white/20'} ${bgClasses[mode]}`}
                               title={mode}
                             />
                           ))}
                           <div className="w-px h-4 bg-white/20 mx-1"></div>
                           {/* Custom BG Color Wheel Toggle */}
                           <label 
                             className={`relative w-6 h-6 rounded-full border-2 transition-all hover:scale-125 cursor-pointer flex items-center justify-center ${bgMode === 'custom' ? 'border-[#00F0FF] scale-110 shadow-[0_0_15px_rgba(0,240,255,0.6)]' : 'border-white/20'}`} 
                             style={{ backgroundColor: customBg }} 
                             title="Custom BG"
                           >
                             <input type="color" value={customBg} onChange={(e) => { setCustomBg(e.target.value); setBgMode('custom'); }} className="opacity-0 absolute inset-0 w-full h-full cursor-pointer" />
                           </label>
                         </div>
                       </div>
                       
                       <div className="flex items-center gap-3">
                         <span className="text-[10px] tracking-[0.2em] text-gray-400 uppercase font-bold">Zoom:</span>
                         <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="w-6 h-6 flex items-center justify-center bg-white/5 hover:bg-[#00F0FF]/20 text-[#00F0FF] border border-[#00F0FF]/30 rounded transition-colors font-bold">-</button>
                         <span className="text-xs text-white w-10 text-center font-mono font-bold">{Math.round(zoom * 100)}%</span>
                         <button onClick={() => setZoom(z => Math.min(5, z + 0.25))} className="w-6 h-6 flex items-center justify-center bg-white/5 hover:bg-[#00F0FF]/20 text-[#00F0FF] border border-[#00F0FF]/30 rounded transition-colors font-bold">+</button>
                         <button onClick={() => setZoom(1)} className="text-[9px] text-gray-500 hover:text-white ml-2 tracking-[0.2em] uppercase transition-colors">Reset</button>
                       </div>

                     </div>
                     
                     <a 
                       href={result.cutout_url} 
                       download 
                       className="absolute top-4 right-4 z-30 bg-black/80 backdrop-blur border border-white/20 text-white text-[9px] tracking-[0.2em] uppercase px-4 py-3 hover:bg-[#00F0FF] hover:text-black hover:border-[#00F0FF] transition-all flex items-center gap-2 group shadow-xl"
                     >
                       <svg className="w-3 h-3 group-hover:-translate-y-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="square" strokeLinejoin="miter" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                       Save Artifact
                     </a>
                  </div>
                ) : (
                  <div className="absolute inset-0 text-center flex flex-col items-center justify-center border border-white/5 bg-white/[0.02]">
                    {status === 'processing' || status === 'queued' || status === 'uploading' ? (
                       <div className="relative w-20 h-20 flex items-center justify-center">
                         <div className="absolute inset-0 border border-[#FF003C]/20 rounded-full animate-ping"></div>
                         <div className="absolute inset-3 border border-l-transparent border-t-[#FF003C] border-r-transparent border-b-[#FF003C] rounded-full animate-spin"></div>
                         <div className="absolute inset-6 border border-l-[#00F0FF] border-t-transparent border-r-[#00F0FF] border-b-transparent rounded-full animate-spin" style={{animationDirection: 'reverse', animationDuration: '1.5s'}}></div>
                         <div className="text-[9px] font-bold text-white tracking-widest absolute">SYS</div>
                       </div>
                    ) : (
                       <>
                         <div className="w-px h-16 bg-gradient-to-b from-transparent to-[#00F0FF]/30 mb-4"></div>
                         <div className="text-[10px] tracking-[0.4em] font-display uppercase text-gray-500">Awaiting Signal</div>
                         <div className="text-[9px] tracking-widest text-gray-700 mt-2 uppercase">System Idle</div>
                       </>
                    )}
                  </div>
                )}
              </div>
              
              <div className="shrink-0 h-1 w-full bg-gradient-to-r from-transparent via-[#00F0FF]/20 to-transparent"></div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App
"""
with open('/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx', 'w') as f:
    f.write(app_code)

print("Rollback scripts written. Rebuilding and restarting...")
