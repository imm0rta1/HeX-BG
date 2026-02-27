from pydantic import BaseModel
from typing import Optional, Dict, Any

class JobResponse(BaseModel):
    job_id: str
    status: str
    created_at: float
    result: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    device: str
