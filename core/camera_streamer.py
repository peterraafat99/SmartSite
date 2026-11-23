"""
SmartSite High-Performance Threaded Camera Streaming Service.
Runs AI computer vision pipelines in dedicated background worker threads,
serving smooth 30+ FPS MJPEG streams with near-zero latency.
"""
import os
import cv2
import time
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, Generator, Tuple

import config
from ai.detector import SafetyDetector
from ai.video_processor import VideoProcessor
from ai.zone_detector import ZoneDetector
from ai.face_recognizer import get_face_recognizer
from database.db import get_active_zone

logger = logging.getLogger(__name__)

class CameraStreamService:
    """Manages background frame capture, AI inference, and MJPEG byte streaming."""

    def __init__(self):
        self.detector = SafetyDetector(config.DEFAULT_MODEL_PATH)
        
        # Load active zone from DB
        db_zone = get_active_zone()
        if db_zone:
            self.zone_detector = ZoneDetector(
                name=db_zone["zone_name"],
                x1_norm=db_zone["x1"],
                y1_norm=db_zone["y1"],
                x2_norm=db_zone["x2"],
                y2_norm=db_zone["y2"],
                min_consecutive_frames=db_zone.get("min_frames_confirmation", 3)
            )
        else:
            self.zone_detector = ZoneDetector()

        self.processor = VideoProcessor(
            detector=self.detector,
            zone_detector=self.zone_detector,
            conf_threshold=config.DEFAULT_CONFIDENCE,
            frame_sampling_interval=config.DEFAULT_SAMPLE_INTERVAL,
            target_resolution=config.TARGET_RESOLUTION
        )

        self.source_path = config.SAMPLE_VIDEO_PATH
        self.is_running = False
        self.is_paused = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Latest processed frames (JPEG bytes)
        self.latest_ppe_jpeg: Optional[bytes] = None
        self.latest_gate_jpeg: Optional[bytes] = None
        
        # Latest telemetry metrics
        self.latest_metrics: Dict[str, Any] = {
            "worker_count": 0,
            "compliance_rate": 100.0,
            "workers_in_zone": 0,
            "confirmed_breaches": 0,
            "is_breach": False
        }

        # Gate camera state
        self.face_recognizer = get_face_recognizer()
        self.gate_source = "demo"
        self._gate_thread: Optional[threading.Thread] = None

    def start(self, source: Optional[str] = None):
        """Starts background video processing worker thread."""
        if source:
            self.source_path = source

        if self._thread and self._thread.is_alive():
            self.is_running = False
            self._thread.join(timeout=1.0)

        self.is_running = True
        self.is_paused = False
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info(f"AI Camera worker started with source: {self.source_path}")

    def stop(self):
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("AI Camera worker stopped.")

    def update_zone_boundaries(self, x1: float, y1: float, x2: float, y2: float, name: Optional[str] = None):
        """Dynamically adjusts restricted zone boundaries without interrupting streaming."""
        with self._lock:
            self.zone_detector.update_zone(x1, y1, x2, y2, name=name)

    def _worker_loop(self):
        """Dedicated thread executing OpenCV read, YOLO detection, and JPEG encoding with auto-recovery."""
        logger.info("Starting camera worker loop...")
        while self.is_running:
            cap = None
            try:
                # Handle webcam vs file
                if str(self.source_path).isdigit():
                    cap = cv2.VideoCapture(int(self.source_path))
                else:
                    cap = cv2.VideoCapture(self.source_path)

                if not cap.isOpened():
                    logger.error(f"Failed to open video source: {self.source_path}")
                    time.sleep(1.0)
                    continue

                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                frame_delay = max(0.015, 1.0 / (fps * 1.2))

                while self.is_running and cap.isOpened():
                    if self.is_paused:
                        time.sleep(0.1)
                        continue

                    ret, frame = cap.read()
                    if not ret or frame is None:
                        # For video files, seamlessly rewind to frame 0 without recreating decoder handle
                        if not str(self.source_path).isdigit():
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, frame = cap.read()
                            if not ret or frame is None:
                                break
                        else:
                            break

                    try:
                        with self._lock:
                            annotated_bgr, metrics = self.processor.process_frame(frame, emit_events=True)

                        # Encode to high-quality JPEG
                        success, buffer = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if not success:
                            continue
                        jpeg_bytes = buffer.tobytes()

                        with self._lock:
                            self.latest_ppe_jpeg = jpeg_bytes
                            self.latest_metrics = {
                                "worker_count": metrics["worker_count"],
                                "compliance_rate": metrics["ppe_summary"]["compliance_rate"],
                                "workers_in_zone": metrics["zone_status"]["workers_in_zone"],
                                "confirmed_breaches": metrics["zone_status"]["confirmed_breaches"],
                                "is_breach": metrics["zone_status"]["breach_active"],
                                "profiles": [
                                    {
                                        "worker_id": p.worker_id,
                                        "helmet": p.helmet_status,
                                        "vest": p.vest_status,
                                        "violations": p.violations
                                    }
                                    for p in metrics["ppe_summary"]["profiles"]
                                ]
                            }
                    except Exception as frame_err:
                        logger.warning(f"Error in video frame processing: {frame_err}")
                        time.sleep(0.05)

                    time.sleep(frame_delay)

            except Exception as loop_err:
                logger.error(f"Camera worker outer loop exception: {loop_err}")
                time.sleep(1.0)
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
            time.sleep(0.1)

    def get_ppe_stream(self) -> Generator[bytes, None, None]:
        """Generator yielding multipart MJPEG frames for HTTP streaming."""
        while self.is_running:
            if self.latest_ppe_jpeg:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + self.latest_ppe_jpeg + b'\r\n')
            time.sleep(0.033)  # ~30 FPS

    def generate_gate_snapshot(self, image_bgr: cv2.Mat, gate_name: str = "Gate 1 - Main Turnstile") -> Tuple[bytes, list]:
        """Runs face recognition on gate image and returns JPEG bytes + matches."""
        annotated_bgr, matches = self.face_recognizer.process_access_gate_frame(
            image_bgr, gate_name=gate_name, emit_events=True
        )
        _, buffer = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes(), [m.to_dict() for m in matches]

# Global singleton camera streaming service
camera_service = CameraStreamService()
