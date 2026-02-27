from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.core.config import settings
from app.api.schemas import JobResponse
from redis import Redis
from rq import Queue
from app.workers.tasks import process_image_task
import uuid, time, shutil, logging, os, zipfile, io
from fastapi.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)
redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
q_default = Queue('default', connection=redis_conn)
q_upscale = Queue('upscale', connection=redis_conn)

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

@router.get("/jobs/batch/zip")
def download_batch_zip(job_ids: str):
    ids = [i.strip() for i in job_ids.split(",") if i.strip()]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for j_id in ids:
            job_dir = settings.STORAGE_DIR / j_id
            cutout_path = job_dir / "cutout.png"
            orig_name = f"cutout_{j_id[:8]}"
            for f in job_dir.glob("original_*"):
                orig_name = f.name.replace("original_", "").rsplit(".", 1)[0]
                break
            if cutout_path.exists():
                zip_file.write(cutout_path, arcname=f"{orig_name}_cutout.png")
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=batch_cutouts.zip"})
