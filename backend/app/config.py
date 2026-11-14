import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(ROOT / "storage"))).resolve()
WEIGHTS_DIR = Path(os.getenv("WEIGHTS_DIR", str(ROOT / "weights"))).resolve()
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://panorama:panorama@localhost:3306/panorama360")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-change-before-deploy")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_VIDEO_BYTES = 350 * 1024 * 1024
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
