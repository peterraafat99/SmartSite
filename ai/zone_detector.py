"""
SmartSite Geometric Dangerous-Zone Monitoring Module.
Detects worker entry into user-configured restricted zones using bottom-center (feet) coordinates.
Includes consecutive-frame debouncing to eliminate false positive flicker.
"""
from typing import List, Tuple, Dict, Any, Optional
import cv2
import numpy as np

from ai.tracker import TrackedWorker
from safety.event_engine import get_event_engine

class ZoneDetector:
    """Manages geometric ROI restricted zones and breach verification."""

    def __init__(
        self,
        name: str = "Excavation Danger Zone",
        x1_norm: float = 0.55,
        y1_norm: float = 0.35,
        x2_norm: float = 0.95,
        y2_norm: float = 0.90,
        min_consecutive_frames: int = 3
    ):
        self.name = name
        self.x1_norm = max(0.0, min(1.0, x1_norm))
        self.y1_norm = max(0.0, min(1.0, y1_norm))
        self.x2_norm = max(0.0, min(1.0, x2_norm))
        self.y2_norm = max(0.0, min(1.0, y2_norm))
        self.min_consecutive_frames = min_consecutive_frames

    def update_zone(self, x1_norm: float, y1_norm: float, x2_norm: float, y2_norm: float, name: Optional[str] = None):
        """Updates zone boundaries in normalized coordinates (0.0 to 1.0)."""
        self.x1_norm = min(x1_norm, x2_norm)
        self.y1_norm = min(y1_norm, y2_norm)
        self.x2_norm = max(x1_norm, x2_norm)
        self.y2_norm = max(y1_norm, y2_norm)
        if name:
            self.name = name

    def get_pixel_coords(self, frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
        """Converts normalized coordinates to absolute pixel coordinates."""
        px1 = int(self.x1_norm * frame_w)
        py1 = int(self.y1_norm * frame_h)
        px2 = int(self.x2_norm * frame_w)
        py2 = int(self.y2_norm * frame_h)
        return px1, py1, px2, py2

    def is_point_in_zone(self, pt: Tuple[int, int], frame_w: int, frame_h: int) -> bool:
        """Checks if a (x, y) point is inside the zone."""
        px1, py1, px2, py2 = self.get_pixel_coords(frame_w, frame_h)
        x, y = pt
        return px1 <= x <= px2 and py1 <= y <= py2

    def evaluate_workers(
        self,
        workers: List[TrackedWorker],
        frame_w: int,
        frame_h: int,
        emit_events: bool = True,
        evidence_frame_bgr: Optional[np.ndarray] = None,
        evidence_save_fn = None,
        single_frame_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates worker positions against the restricted zone.
        Updates consecutive frame counts and emits confirmed breach events.
        In single_frame_mode, any worker present inside the zone triggers an immediate confirmed breach.
        """
        breaching_workers = []
        all_in_zone_workers = []

        for worker in workers:
            bc = worker.bottom_center
            in_zone = self.is_point_in_zone(bc, frame_w, frame_h)
            worker.in_zone = in_zone

            if in_zone:
                worker.consecutive_zone_frames += 1
                all_in_zone_workers.append(worker)

                # Check if threshold reached or in single-frame inspection mode
                if single_frame_mode or worker.consecutive_zone_frames >= self.min_consecutive_frames:
                    breaching_workers.append(worker)
            else:
                worker.consecutive_zone_frames = 0

        # In single-frame mode, every worker in the zone is considered breaching
        if single_frame_mode and all_in_zone_workers:
            breaching_workers = all_in_zone_workers

        # Trigger event if confirmed breach
        if emit_events and breaching_workers:
            engine = get_event_engine()
            # Check debounce before incurring image save overhead
            if not engine.is_debounced("ZONE_INTRUSION", self.name):
                evidence_path = None
                if evidence_save_fn is not None and evidence_frame_bgr is not None:
                    evidence_path = evidence_save_fn(evidence_frame_bgr, "zone_breach")

                worker_ids_str = ", ".join([f"#{w.track_id}" for w in breaching_workers])
                desc = (
                    f"Unauthorized worker entry detected in restricted zone '{self.name}'. "
                    f"Workers confirmed inside: {worker_ids_str}."
                )

                engine.emit_event(
                    event_type="ZONE_INTRUSION",
                    source="AI_CAMERA",
                    site_zone=self.name,
                    description=desc,
                    confidence=0.95,
                    evidence_path=evidence_path,
                    context={"zone_name": self.name, "worker_count": len(breaching_workers)},
                    force=True
                )

        return {
            "workers_in_zone": len(all_in_zone_workers),
            "confirmed_breaches": len(breaching_workers),
            "breach_active": len(breaching_workers) > 0,
            "breaching_worker_ids": [w.track_id for w in breaching_workers]
        }

    def render_overlay(self, frame_bgr: np.ndarray, zone_status: Dict[str, Any]) -> np.ndarray:
        """
        Draws semi-transparent restricted zone overlay and status badges onto the frame.
        Optimized to blend only the subregion in-place to prevent memory thrashing.
        """
        h, w = frame_bgr.shape[:2]
        px1, py1, px2, py2 = self.get_pixel_coords(w, h)

        is_breach = zone_status.get("breach_active", False)
        in_zone_count = zone_status.get("workers_in_zone", 0)

        # Color: Crimson Red for Breach, Amber for Alert, Emerald Green for Safe
        if is_breach:
            color = (0, 0, 220)  # Red (BGR)
            fill_color = (0, 0, 200)
            status_text = f"RESTRICTED ZONE BREACH ({in_zone_count} WORKER{'S' if in_zone_count > 1 else ''})"
        elif in_zone_count > 0:
            color = (0, 165, 255)  # Orange/Amber (BGR)
            fill_color = (0, 140, 230)
            status_text = f"ZONE ENTRY DETECTED - VERIFYING ({in_zone_count})"
        else:
            color = (0, 200, 100)  # Green (BGR)
            fill_color = (0, 180, 80)
            status_text = "ZONE CLEAR"

        # Blend semi-transparent overlay strictly inside the bounding box subregion
        cx1, cy1 = max(0, px1), max(0, py1)
        cx2, cy2 = min(w, px2), min(h, py2)
        if cx2 > cx1 and cy2 > cy1:
            alpha = 0.22 if not is_breach else 0.35
            sub = frame_bgr[cy1:cy2, cx1:cx2]
            color_rect = np.full_like(sub, fill_color)
            cv2.addWeighted(color_rect, alpha, sub, 1.0 - alpha, 0, sub)

        # Draw border
        thickness = 3 if is_breach else 2
        cv2.rectangle(frame_bgr, (px1, py1), (px2, py2), color, thickness)

        # Draw zone header label box
        label_text = f" [!] {self.name.upper()}: {status_text} "
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        font_thick = 2
        (tw, th), baseline = cv2.getTextSize(label_text, font, font_scale, font_thick)

        label_y1 = max(0, py1 - th - 10)
        label_y2 = py1
        cv2.rectangle(frame_bgr, (px1, label_y1), (px1 + tw + 10, label_y2), color, -1)
        cv2.putText(frame_bgr, label_text, (px1 + 5, py1 - 5), font, font_scale, (255, 255, 255), font_thick, cv2.LINE_AA)

        return frame_bgr
