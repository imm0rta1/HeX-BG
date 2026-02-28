import re

filepath = '/a0/agent-zero-data/workdir/bg-removal-service/bg-removal-service/app/api/routes_jobs.py'
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace(
    "from app.workers.tasks import process_image_task",
    "from app.workers.tasks import process_image_task, preload_model_task"
)

preload_endpoint = """
@router.post("/jobs/preload", response_model=JobResponse)
async def preload_model(model_name: str = Form(...)):
    job_id = str(uuid.uuid4())
    job_dir = settings.STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    q_default.enqueue(preload_model_task, model_name, job_id=job_id, job_timeout=600)
    return JobResponse(job_id=job_id, status="queued", created_at=time.time())

"""

content = content.replace("@router.post(\"/jobs\", response_model=JobResponse)", preload_endpoint + "@router.post(\"/jobs\", response_model=JobResponse)")

with open(filepath, 'w') as f:
    f.write(content)
