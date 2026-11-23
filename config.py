"""
SmartSite Production Configuration.
Centralized pathing, server parameters, and detection defaults.
"""
import os

# Prevent OpenBLAS/MKL thread buffer allocation exhaustion on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
EVIDENCE_DIR = os.path.join(DATA_DIR, "evidence")
FACES_DIR = os.path.join(DATA_DIR, "faces")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
DB_PATH = os.path.join(DATA_DIR, "smartsite.db")

# Server Config
HOST = "127.0.0.1"
PORT = 8000
DEBUG = False

# AI Inference Config
DEFAULT_MODEL_PATH = "yolo11n.pt"
CUSTOM_MODEL_PATH = os.path.join(MODELS_DIR, "best.pt")
DEFAULT_CONFIDENCE = 0.35
DEFAULT_SAMPLE_INTERVAL = 2  # Process 1 of every 2 frames for CPU optimization
TARGET_RESOLUTION = (1280, 720)

# Sample Media
SAMPLE_VIDEO_PATH = os.path.join(VIDEOS_DIR, "sample_construction.mp4")

# Ensure essential directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(EVIDENCE_DIR, exist_ok=True)
os.makedirs(FACES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
