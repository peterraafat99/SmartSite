"""
SmartSite Video Processing Pipeline.
Handles video streams (file, sample, webcam), frame sampling,
annotation rendering, evidence snapshot generation, and event dispatch.
"""
import os
import cv2
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Generator
import numpy as np

from ai.detector import SafetyDetector, Detection
from ai.tracker import WorkerTracker, TrackedWorker
from ai.zone_detector import ZoneDetector
from ai.ppe_analyzer import PPEAnalyzer

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "evidence")

def save_evidence_snapshot(frame_bgr: np.ndarray, tag: str = "violation") -> str:
    """Saves a timestamped JPEG image of the violation frame and returns the relative path."""
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    filename = f"{tag}_{ts}.jpg"
    full_path = os.path.join(EVIDENCE_DIR, filename)
    cv2.imwrite(full_path, frame_bgr)
    # Store relative path for database portability
    rel_path = os.path.join("data", "evidence", filename).replace("\\", "/")
    return rel_path

class VideoProcessor:
    """Processes video frames through detector, tracker, zone analyzer, and PPE evaluator."""

    def __init__(
        self,
        detector: SafetyDetector,
        zone_detector: Optional[ZoneDetector] = None,
        conf_threshold: float = 0.35,
        frame_sampling_interval: int = 2,
        target_resolution: Optional[Tuple[int, int]] = (1280, 720)
    ):
        self.detector = detector
        self.zone_detector = zone_detector or ZoneDetector()
        self.tracker = WorkerTracker()
        self.conf_threshold = conf_threshold
        self.sampling_interval = max(1, frame_sampling_interval)
        self.target_resolution = target_resolution
        self.frame_count = 0
        self.last_annotated_frame = None

    def annotate_frame(
        self,
        frame_bgr: np.ndarray,
        detections: list,
        workers: list,
        zone_status: dict,
        ppe_summary: dict,
        draw_zone: bool = True
    ) -> np.ndarray:
        """Draws bounding boxes, labels, worker IDs, and status overlays."""
        annotated = frame_bgr.copy()
        h, w = annotated.shape[:2]

        # 1. Draw Restricted Zone (only if enabled)
        if self.zone_detector and draw_zone:
            annotated = self.zone_detector.render_overlay(annotated, zone_status)

        # 2. Draw Object Detections (PPE & Equipment)
        for det in detections:
            x1, y1, x2, y2 = det.box
            cls_name = det.class_name
            conf = det.conf

            if det.is_violation:
                # Crimson Red for missing PPE
                color = (0, 0, 230)
                label = f"VIOLATION: {cls_name} ({conf:.2f})"
            elif det.is_ppe:
                # Emerald Green for compliant PPE
                color = (0, 200, 100)
                label = f"{cls_name} ({conf:.2f})"
            elif cls_name == "Person":
                # Person box handled below by tracker
                continue
            elif "forklift" in cls_name.lower():
                color = (255, 140, 0)
                label = f"Vehicle: {cls_name} ({conf:.2f})"
            else:
                color = (200, 200, 200)
                label = f"{cls_name} ({conf:.2f})"

            # Draw rectangle and label
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated, label, (x1, max(15, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
            )

        # 3. Draw Tracked Workers
        for worker in workers:
            wx1, wy1, wx2, wy2 = worker.box
            in_zone = worker.in_zone
            is_breach = in_zone and (worker.consecutive_zone_frames >= self.zone_detector.min_consecutive_frames)

            # Determine worker border color
            if is_breach:
                worker_color = (0, 0, 240)  # Bright Red
            elif in_zone:
                worker_color = (0, 165, 255)  # Orange
            else:
                worker_color = (0, 220, 220)  # Yellow / Cyan

            # Draw worker bounding box
            cv2.rectangle(annotated, (wx1, wy1), (wx2, wy2), worker_color, 2)

            # Draw worker ground contact point (bottom-center)
            bx, by = worker.bottom_center
            pt_color = (0, 0, 255) if in_zone else (0, 255, 0)
            cv2.circle(annotated, (bx, by), 6, pt_color, -1)
            cv2.circle(annotated, (bx, by), 8, (255, 255, 255), 1)

            # Build worker tag string
            tag = f"Worker #{worker.track_id}"
            if worker.helmet_status == "Compliant":
                tag += " [Helmet: OK]"
            elif worker.helmet_status == "Missing":
                tag += " [NO HELMET!]"

            if in_zone:
                tag += " [IN ZONE!]"

            # Header tag background
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (wx1, max(0, wy1 - th - 8)), (wx1 + tw + 6, wy1), worker_color, -1)
            cv2.putText(
                annotated, tag, (wx1 + 3, max(12, wy1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA
            )

        # 4. Top Telemetry Banner
        total_workers = len(workers)
        comp_rate = ppe_summary.get("compliance_rate", 100.0)
        zone_breaches = zone_status.get("confirmed_breaches", 0)

        banner_text = f"WORKERS ON SITE: {total_workers}  |  PPE COMPLIANCE: {comp_rate:.0f}%  |  ZONE BREACHES: {zone_breaches}"
        cv2.rectangle(annotated, (0, 0), (w, 28), (20, 24, 33), -1)
        cv2.putText(
            annotated, banner_text, (15, 19),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 225, 235), 1, cv2.LINE_AA
        )

        return annotated

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        emit_events: bool = True,
        resize: bool = True,
        single_frame_mode: bool = False,
        enable_zone: bool = True
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Processes a video or static frame and returns (annotated_bgr, metrics)."""
        self.frame_count += 1
        h, w = frame_bgr.shape[:2]

        # Optional resize
        if resize and self.target_resolution:
            tw, th = self.target_resolution
            if (w, h) != (tw, th):
                frame_bgr = cv2.resize(frame_bgr, (tw, th))
                h, w = frame_bgr.shape[:2]

        # For single static images, reset tracker tracks so each worker gets fresh clean IDs
        if single_frame_mode:
            self.tracker.tracks.clear()
            self.tracker.next_id = 1

        # Run inference on frame
        detections = self.detector.detect(frame_bgr, conf_threshold=self.conf_threshold)

        # Extract Person boxes for tracker
        person_boxes = [d.box for d in detections if d.class_name == "Person"]
        tracked_workers = self.tracker.update(person_boxes)

        # Zone detection
        if enable_zone and self.zone_detector:
            zone_status = self.zone_detector.evaluate_workers(
                workers=tracked_workers,
                frame_w=w,
                frame_h=h,
                emit_events=emit_events,
                evidence_frame_bgr=frame_bgr,
                evidence_save_fn=save_evidence_snapshot,
                single_frame_mode=single_frame_mode
            )
        else:
            zone_status = {
                "workers_in_zone": 0,
                "confirmed_breaches": 0,
                "breach_active": False,
                "zone_name": "Disabled"
            }

        # PPE analysis
        ppe_summary = PPEAnalyzer.analyze(
            workers=tracked_workers,
            all_detections=detections,
            is_custom_model=self.detector.is_custom_ppe_model,
            emit_events=emit_events,
            site_zone=self.zone_detector.name if (enable_zone and self.zone_detector) else "General Inspection",
            evidence_frame_bgr=frame_bgr,
            evidence_save_fn=save_evidence_snapshot
        )

        # Render annotations
        annotated_bgr = self.annotate_frame(
            frame_bgr, detections, tracked_workers, zone_status, ppe_summary, draw_zone=enable_zone
        )
        self.last_annotated_frame = annotated_bgr

        # Build comprehensive worker telemetry list
        worker_details = []
        for p in ppe_summary.get("profiles", []):
            matching_w = next((w for w in tracked_workers if w.track_id == p.worker_id), None)
            in_zone = matching_w.in_zone if matching_w else False
            has_vio = len(p.violations) > 0
            
            # Risk categorization
            if in_zone and has_vio:
                risk = "CRITICAL"
            elif in_zone or has_vio:
                risk = "HIGH" if in_zone else "WARNING"
            else:
                risk = "SAFE"

            worker_details.append({
                "worker_id": p.worker_id,
                "box": p.box,
                "bottom_center": matching_w.bottom_center if matching_w else [0, 0],
                "in_zone": in_zone,
                "helmet_status": p.helmet_status,
                "vest_status": p.vest_status,
                "violations": p.violations,
                "detected_items": p.detected_items,
                "risk": risk
            })

        metrics = {
            "frame_idx": self.frame_count,
            "worker_count": len(tracked_workers),
            "zone_status": zone_status,
            "ppe_summary": ppe_summary,
            "detection_count": len(detections),
            "detections": detections,
            "workers": worker_details
        }

        return annotated_bgr, metrics
