# scraper_bot/config.py
import os
from dotenv import load_dotenv
 
load_dotenv()

# Settings for Ingestion to Main Server
MAIN_SERVER_URL = os.environ.get("MAIN_SERVER_URL", "http://127.0.0.1:8000")
INGEST_ENDPOINT = f"{MAIN_SERVER_URL.rstrip('/')}/cars/api/internal/ingest/"
BOT_CONFIG_ENDPOINT = f"{MAIN_SERVER_URL.rstrip('/')}/bot-manager/api/config/"
INGESTION_API_KEY = os.environ.get("INGESTION_API_KEY", "raahcar-secure-bot-key-2026")

# Redis / Celery Broker Settings
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# Output & Assets Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMP_IMAGE_DIR = os.path.join(BASE_DIR, "temp_images")

# Primary logo path: check scraper root first, fallback to assets/logo.png
_root_logo = os.path.join(BASE_DIR, "logo.png")
_assets_logo = os.path.join(ASSETS_DIR, "logo.png")
LOGO_PATH = _root_logo if os.path.exists(_root_logo) else _assets_logo

# Watermark logo path for top-right corner branding
WATERMARK_LOGO_PATH = os.path.join(BASE_DIR, "logo.webp")

PLATE_MODEL_PATH = os.path.join(ASSETS_DIR, "plate_detector.onnx")
PLATE_IRAN_MODEL_PATH = os.path.join(ASSETS_DIR, "plate_yolo_iran.onnx")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

