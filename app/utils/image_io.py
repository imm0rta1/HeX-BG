from PIL import Image
from io import BytesIO
from pathlib import Path
import requests

def load_image(source: str | Path) -> Image.Image:
    """Load image from path or URL"""
    if str(source).startswith(('http://', 'https://')):
        response = requests.get(source)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(source)
    
    # Convert to RGBA (for consistency) or RGB if no alpha needed yet
    return img.convert("RGB")

def save_image(image: Image.Image, path: Path) -> None:
    """Save image ensuring directory exists"""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
