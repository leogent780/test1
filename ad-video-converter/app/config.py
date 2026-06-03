from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

DIRS = {
    "reference": UPLOAD_DIR / "reference",
    "product": UPLOAD_DIR / "product",
    "clips": UPLOAD_DIR / "clips",
    "output": UPLOAD_DIR / "output",
}

for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "")

SCENE_THRESHOLD = 27.0  # 장면 전환 감도 (낮을수록 민감)
MIN_CLIP_DURATION = 1.0  # 최소 클립 길이 (초)
