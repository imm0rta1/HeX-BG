from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.core.config import settings
from app.api.schemas import JobResponse
from redis import Redis
from rq import Queue
from app.workers.tasks import process_image_task, preload_model_task
import uuid, time, shutil, logging, os

router = APIRouter()
logger = logging.getLogger(__name__)
redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
q_default = Queue('default', connection=redis_conn)
q_upscale = Queue('upscale', connection=redis_conn)


@router.post("/jobs/preload", response_model=JobResponse)
async def preload_model(model_name: str = Form(...)):
    job_id = str(uuid.uuid4())
    job_dir = settings.STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    q_default.enqueue(preload_model_task, model_name, job_id=job_id, job_timeout=600)
    return JobResponse(job_id=job_id, status="queued", created_at=time.time())

@router.post("/jobs", response_model=JobResponse)
async def create_job(
    file: UploadFile = File(...),
    model_name: str = Form("isnet-general-use"),
    erode_size: int = Form(0),
    blur_size: int = Form(0),
    auto_cleanup: bool = Form(True),
    upscale: bool = Form(False),
    upscale_mode: str = Form('none')
):
    job_id = str(uuid.uuid4())
    job_dir = settings.STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    original_path = job_dir / f"original_{file.filename}"
    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Stability guard: BiRefNet + upscale is too heavy on low VRAM; force 2-step workflow
    if "birefnet" in model_name.lower() and upscale_mode not in ("none", ""):
         logger.warning(f"Forcing upscale_mode=none for model={model_name} (use 2-step upscale)")
         upscale_mode = "none"

    if upscale_mode != 'none' and upscale_mode != '':
         q_upscale.enqueue(process_image_task, job_id, str(original_path), model_name, erode_size, blur_size, auto_cleanup, upscale, upscale_mode, job_id=job_id, job_timeout=1200)
    else:
         q_default.enqueue(process_image_task, job_id, str(original_path), model_name, erode_size, blur_size, auto_cleanup, upscale, upscale_mode, job_id=job_id, job_timeout=1200)

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
        # Check default queue first
        job = q_default.fetch_job(job_id)
        if not job:
            # Check upscale queue
            job = q_upscale.fetch_job(job_id)
            
        if job:
            if job.get_status() == "finished":
                 return JobResponse(job_id=job_id, status="done", created_at=job_dir.stat().st_ctime, result=job.result)
            if job.get_status() == "failed":
                 return JobResponse(job_id=job_id, status="failed", created_at=job_dir.stat().st_ctime, result={"error": "Processing failed"})
            return JobResponse(job_id=job_id, status=job.get_status(), created_at=job_dir.stat().st_ctime)
    except Exception:
        pass

    if (job_dir / "cutout.png").exists():
        return JobResponse(job_id=job_id, status="done", created_at=job_dir.stat().st_ctime, result={"cutout_url": f"/files/{job_id}/cutout.png", "mask_url": f"/files/{job_id}/mask.png"})
    return JobResponse(job_id=job_id, status="processing", created_at=job_dir.stat().st_ctime)
