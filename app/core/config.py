import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "LocalBgRemoval"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "data" / "jobs"
    MODEL_DIR: Path = BASE_DIR / "data" / "models"
    
    def __init__(self):
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
