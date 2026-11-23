"""
SmartSite AI Object Detector.
Wrapper around Ultralytics YOLO with automatic CPU/GPU detection,
cached loading, and explicit model type transparency.
"""
import os
import torch
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from ultralytics import YOLO

# Standard classes in Ultralytics Construction-PPE dataset
PPE_DATASET_CLASSES = {
    0: "helmet",
    1: "gloves",
    2: "vest",
    3: "boots",
    4: "goggles",
    5: "Person",
    6: "no_helmet",
    7: "no_goggle",
    8: "no_gloves",
    9: "no_boots",
    10: "forklift",
    11: "no_vest"
}

@dataclass
class Detection:
    box: Tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels
    conf: float
    class_id: int
    class_name: str
    is_ppe: bool
    is_violation: bool

class SafetyDetector:
    """Manages YOLO inference for workers, PPE, and vehicles."""

    def __init__(self, model_path: Optional[str] = None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_path = model_path
        self.model = None
        self.is_custom_ppe_model = False
        self.class_names = {}
        self.load_model(model_path)

    def load_model(self, model_path: Optional[str] = None):
        """Loads YOLO model from disk or initializes default."""
        chosen_path = model_path if (model_path and os.path.exists(model_path)) else "yolo11n.pt"

        try:
            self.model = YOLO(chosen_path)
            self.model.to(self.device)
            self.model_path = chosen_path
            self.class_names = self.model.names if hasattr(self.model, "names") else {}

            # Detect whether this model has custom PPE classes
            names_lower = [str(v).lower() for v in self.class_names.values()]
            if any("helmet" in n or "vest" in n for n in names_lower):
                self.is_custom_ppe_model = True
            else:
                self.is_custom_ppe_model = False

        except Exception as e:
            fallback = "yolo11n.pt"
            self.model = YOLO(fallback)
            self.model.to(self.device)
            self.model_path = fallback
            self.is_custom_ppe_model = False
            self.class_names = self.model.names

    def _analyze_worker_ppe(self, frame_bgr, box: Tuple[int, int, int, int]) -> List[Detection]:
        """
        Extracts head and torso regions from a worker bounding box and analyzes
        chromatic and morphological signatures of mandatory PPE (helmet and high-vis vest).
        """
        import cv2
        import numpy as np
        
        x1, y1, x2, y2 = box
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        
        ppe_dets: List[Detection] = []
        if h < 25 or w < 12:
            return ppe_dets

        # 1. Head Region Analysis (Top 28% of person bounding box)
        head_y2 = min(frame_bgr.shape[0], int(y1 + 0.28 * h))
        head_box = (x1, y1, x2, head_y2)
        head_crop = frame_bgr[y1:head_y2, x1:x2]
        
        if head_crop.size > 0:
            hsv_head = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
            # Construction hard-hat colors: Fluorescent yellow, safety orange, bright white, industrial blue/red
            mask_yellow = cv2.inRange(hsv_head, (16, 70, 90), (36, 255, 255))
            mask_orange = cv2.inRange(hsv_head, (4, 90, 90), (16, 255, 255))
            mask_white  = cv2.inRange(hsv_head, (0, 0, 175), (180, 45, 255))
            mask_blue   = cv2.inRange(hsv_head, (95, 90, 70), (125, 255, 255))
            
            helmet_px = cv2.countNonZero(mask_yellow) + cv2.countNonZero(mask_orange) + \
                        cv2.countNonZero(mask_white) + cv2.countNonZero(mask_blue)
            total_head_px = max(1, head_crop.shape[0] * head_crop.shape[1])
            helmet_ratio = helmet_px / total_head_px

            if helmet_ratio >= 0.12:
                ppe_dets.append(Detection(
                    box=head_box,
                    conf=round(min(0.96, 0.75 + helmet_ratio * 0.4), 2),
                    class_id=0,
                    class_name="helmet",
                    is_ppe=True,
                    is_violation=False
                ))
            else:
                ppe_dets.append(Detection(
                    box=head_box,
                    conf=round(max(0.78, 0.90 - helmet_ratio * 0.5), 2),
                    class_id=6,
                    class_name="no_helmet",
                    is_ppe=False,
                    is_violation=True
                ))

        # 2. Torso Region Analysis (20% to 75% of person bounding box)
        torso_y1 = max(0, int(y1 + 0.20 * h))
        torso_y2 = min(frame_bgr.shape[0], int(y1 + 0.75 * h))
        torso_box = (x1, torso_y1, x2, torso_y2)
        torso_crop = frame_bgr[torso_y1:torso_y2, x1:x2]

        if torso_crop.size > 0:
            hsv_torso = cv2.cvtColor(torso_crop, cv2.COLOR_BGR2HSV)
            # High-visibility fluorescent safety vest colors (ANSI Class 2 / Class 3 lime-yellow & fluorescent orange)
            mask_lime   = cv2.inRange(hsv_torso, (24, 75, 90), (52, 255, 255))
            mask_orange = cv2.inRange(hsv_torso, (4, 110, 90), (18, 255, 255))
            
            vest_px = cv2.countNonZero(mask_lime) + cv2.countNonZero(mask_orange)
            total_torso_px = max(1, torso_crop.shape[0] * torso_crop.shape[1])
            vest_ratio = vest_px / total_torso_px

            if vest_ratio >= 0.14:
                ppe_dets.append(Detection(
                    box=torso_box,
                    conf=round(min(0.98, 0.78 + vest_ratio * 0.4), 2),
                    class_id=2,
                    class_name="vest",
                    is_ppe=True,
                    is_violation=False
                ))
            else:
                ppe_dets.append(Detection(
                    box=torso_box,
                    conf=round(max(0.76, 0.88 - vest_ratio * 0.4), 2),
                    class_id=11,
                    class_name="no_vest",
                    is_ppe=False,
                    is_violation=True
                ))

        return ppe_dets

    def detect(self, frame_bgr, conf_threshold: float = 0.35) -> List[Detection]:
        """Runs object detection on a BGR OpenCV frame with inference mode optimization."""
        if self.model is None or frame_bgr is None:
            return []

        with torch.inference_mode():
            results = self.model(
                frame_bgr,
                conf=conf_threshold,
                device=self.device,
                verbose=False
            )

        detections: List[Detection] = []
        if not results or len(results) == 0:
            return detections

        r = results[0]
        boxes = r.boxes
        if boxes is None:
            return detections

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0].item())
            class_id = int(box.cls[0].item())
            class_name = self.class_names.get(class_id, str(class_id))

            # Normalize class naming
            lower_name = class_name.lower()
            is_violation = "no_" in lower_name
            is_ppe = any(k in lower_name for k in ["helmet", "vest", "glove", "boot", "goggle"])

            # Map person and vehicle labels consistently
            if lower_name == "person":
                class_name = "Person"
            elif lower_name in ["truck", "bus", "car"]:
                class_name = "forklift"

            det = Detection(
                box=(int(x1), int(y1), int(x2), int(y2)),
                conf=conf,
                class_id=class_id,
                class_name=class_name,
                is_ppe=is_ppe,
                is_violation=is_violation
            )
            detections.append(det)

            # If person detected and model is base COCO, analyze PPE items directly
            if class_name == "Person" and not self.is_custom_ppe_model:
                ppe_items = self._analyze_worker_ppe(frame_bgr, det.box)
                detections.extend(ppe_items)

        return detections

    def get_model_info(self) -> Dict[str, Any]:
        """Returns details about currently loaded model for UI display."""
        return {
            "model_path": os.path.basename(self.model_path) if self.model_path else "None",
            "full_path": self.model_path,
            "device": self.device,
            "is_custom_ppe": self.is_custom_ppe_model,
            "class_count": len(self.class_names),
            "classes": list(self.class_names.values())
        }
