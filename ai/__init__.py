"""SmartSite AI Computer Vision & Analytics Module."""
from ai.detector import SafetyDetector, Detection, PPE_DATASET_CLASSES
from ai.tracker import WorkerTracker, TrackedWorker
from ai.zone_detector import ZoneDetector
from ai.ppe_analyzer import PPEAnalyzer, WorkerPPEProfile
from ai.video_processor import VideoProcessor, save_evidence_snapshot
from ai.face_recognizer import FaceRecognizer, get_face_recognizer, FaceMatchResult

__all__ = [
    "SafetyDetector",
    "Detection",
    "PPE_DATASET_CLASSES",
    "WorkerTracker",
    "TrackedWorker",
    "ZoneDetector",
    "PPEAnalyzer",
    "WorkerPPEProfile",
    "VideoProcessor",
    "save_evidence_snapshot",
    "FaceRecognizer",
    "get_face_recognizer",
    "FaceMatchResult"
]
