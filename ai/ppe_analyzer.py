"""
SmartSite PPE Analyzer Module.
Associates PPE detections with corresponding workers and categorizes:
1. Compliant PPE (protective gear detected)
2. Detected Missing PPE (explicit 'no_helmet' / 'no_vest' class detected)
3. Uncertain / Unobservable (not occluded into false violation)
"""
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from ai.detector import Detection
from ai.tracker import TrackedWorker
from safety.event_engine import get_event_engine

class WorkerPPEProfile:
    def __init__(self, worker_id: int, box: Tuple[int, int, int, int]):
        self.worker_id = worker_id
        self.box = box
        # Statuses: 'Compliant', 'Missing', 'Unobservable'
        self.helmet_status: str = "Unobservable"
        self.vest_status: str = "Unobservable"
        self.boots_status: str = "Unobservable"
        self.gloves_status: str = "Unobservable"
        self.goggles_status: str = "Unobservable"
        self.detected_items: List[str] = []
        self.violations: List[str] = []

    @property
    def is_fully_compliant(self) -> bool:
        """Returns True if worker has no detected missing PPE."""
        return len(self.violations) == 0

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

class PPEAnalyzer:
    """Analyzes detection spatial topology to associate equipment with workers."""

    @staticmethod
    def _box_contains_or_overlaps(container_box, item_box, min_overlap: float = 0.4) -> bool:
        """Checks if item_box largely falls inside container_box."""
        cx1, cy1, cx2, cy2 = container_box
        ix1, iy1, ix2, iy2 = item_box

        # Calculate intersection
        inter_x1 = max(cx1, ix1)
        inter_y1 = max(cy1, iy1)
        inter_x2 = min(cx2, ix2)
        inter_y2 = min(cy2, iy2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return False

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        item_area = (ix2 - ix1) * (iy2 - iy1)
        if item_area == 0:
            return False

        return (inter_area / item_area) >= min_overlap

    @classmethod
    def analyze(
        cls,
        workers: List[TrackedWorker],
        all_detections: List[Detection],
        is_custom_model: bool = True,
        emit_events: bool = True,
        site_zone: str = "Main Operational Area",
        evidence_frame_bgr: Optional[np.ndarray] = None,
        evidence_save_fn = None
    ) -> Dict[str, Any]:
        """
        Associates PPE detections with tracked workers and computes compliance statistics.
        """
        profiles: List[WorkerPPEProfile] = []

        # Separate PPE and violation detections
        ppe_items = [d for d in all_detections if d.is_ppe or d.is_violation]

        for worker in workers:
            profile = WorkerPPEProfile(worker.track_id, worker.box)
            wx1, wy1, wx2, wy2 = worker.box
            w_height = max(1, wy2 - wy1)

            # Define body sub-regions
            head_zone = (wx1, wy1, wx2, int(wy1 + 0.35 * w_height))
            torso_zone = (wx1, int(wy1 + 0.20 * w_height), wx2, int(wy1 + 0.80 * w_height))

            # Match items to worker
            for item in ppe_items:
                c_name = item.class_name.lower()

                # Helmet check (head zone or general worker containment)
                if "helmet" in c_name:
                    if cls._box_contains_or_overlaps(head_zone, item.box, 0.3) or cls._box_contains_or_overlaps(worker.box, item.box, 0.4):
                        if "no_helmet" in c_name:
                            profile.helmet_status = "Missing"
                            profile.violations.append("no_helmet")
                        else:
                            profile.helmet_status = "Compliant"
                        profile.detected_items.append(item.class_name)

                # Vest check (torso zone)
                elif "vest" in c_name:
                    if cls._box_contains_or_overlaps(torso_zone, item.box, 0.3) or cls._box_contains_or_overlaps(worker.box, item.box, 0.4):
                        if "no_vest" in c_name:
                            profile.vest_status = "Missing"
                            profile.violations.append("no_vest")
                        else:
                            profile.vest_status = "Compliant"
                        profile.detected_items.append(item.class_name)

                # Goggles
                elif "goggle" in c_name:
                    if cls._box_contains_or_overlaps(head_zone, item.box, 0.3):
                        if "no_goggle" in c_name:
                            profile.goggles_status = "Missing"
                            profile.violations.append("no_goggle")
                        else:
                            profile.goggles_status = "Compliant"
                        profile.detected_items.append(item.class_name)

                # Gloves
                elif "glove" in c_name:
                    if cls._box_contains_or_overlaps(worker.box, item.box, 0.4):
                        if "no_glove" in c_name:
                            profile.gloves_status = "Missing"
                            profile.violations.append("no_gloves")
                        else:
                            profile.gloves_status = "Compliant"
                        profile.detected_items.append(item.class_name)

                # Boots
                elif "boot" in c_name:
                    feet_zone = (wx1, int(wy1 + 0.70 * w_height), wx2, wy2)
                    if cls._box_contains_or_overlaps(feet_zone, item.box, 0.3) or cls._box_contains_or_overlaps(worker.box, item.box, 0.4):
                        if "no_boot" in c_name:
                            profile.boots_status = "Missing"
                            profile.violations.append("no_boots")
                        else:
                            profile.boots_status = "Compliant"
                        profile.detected_items.append(item.class_name)

            # Sync with tracked worker object
            worker.helmet_status = profile.helmet_status
            worker.vest_status = profile.vest_status
            profiles.append(profile)

        # Calculate statistics
        total_workers = len(profiles)
        violating_workers = [p for p in profiles if p.has_violations]
        compliant_workers = [p for p in profiles if not p.has_violations]

        # Compliance rate computation
        if total_workers > 0:
            compliance_rate = round((len(compliant_workers) / total_workers) * 100.0, 1)
        else:
            compliance_rate = 100.0

        # Emit safety events if violations detected
        if emit_events and violating_workers:
            engine = get_event_engine()
            for v_profile in violating_workers:
                for v in v_profile.violations:
                    event_type = f"PPE_VIOLATION_{v.upper()}"
                    desc = f"Worker #{v_profile.worker_id} detected with missing mandatory PPE: {v}."

                    # Check debounce before saving evidence image to avoid disk I/O thrashing
                    if not engine.is_debounced(event_type, site_zone):
                        evidence_path = None
                        if evidence_save_fn is not None and evidence_frame_bgr is not None:
                            evidence_path = evidence_save_fn(evidence_frame_bgr, f"ppe_violation_w{v_profile.worker_id}")

                        engine.emit_event(
                            event_type=event_type,
                            source="AI_CAMERA",
                            site_zone=site_zone,
                            description=desc,
                            confidence=0.88,
                            evidence_path=evidence_path,
                            context={"worker_id": v_profile.worker_id},
                            force=True
                        )

        return {
            "total_workers": total_workers,
            "compliant_workers": len(compliant_workers),
            "violating_workers": len(violating_workers),
            "compliance_rate": compliance_rate,
            "profiles": profiles
        }
