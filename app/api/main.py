from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes_jobs
from app.core.config import settings
from app.core.logging import setup_logging
import uvicorn

setup_logging()

app = FastAPI(title=settings.PROJECT_NAME)

# Allow LAN access via CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=settings.STORAGE_DIR), name="files")
app.include_router(routes_jobs.router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "LocalBgRemoval", "mode": "queued"}

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000)
