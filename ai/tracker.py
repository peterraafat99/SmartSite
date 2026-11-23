"""
SmartSite Centroid and IoU Worker Tracker.
Maintains worker identity and tracks consecutive frames inside restricted zones.
"""
from typing import List, Tuple, Dict, Any
import numpy as np

def compute_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Calculates Intersection over Union between two boxes (x1, y1, x2, y2)."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection == 0:
        return 0.0

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0

class TrackedWorker:
    def __init__(self, track_id: int, box: Tuple[int, int, int, int]):
        self.track_id = track_id
        self.box = box
        self.missed_frames = 0
        self.consecutive_zone_frames = 0
        self.in_zone = False
        self.helmet_status = "Uncertain"  # Compliant, Missing, Uncertain
        self.vest_status = "Uncertain"

    @property
    def bottom_center(self) -> Tuple[int, int]:
        """Calculates (x_center, y_bottom) representing worker's ground contact point."""
        x1, y1, x2, y2 = self.box
        return int((x1 + x2) / 2), int(y2)

class WorkerTracker:
    def __init__(self, max_missed_frames: int = 15, iou_threshold: float = 0.25):
        self.max_missed_frames = max_missed_frames
        self.iou_threshold = iou_threshold
        self.tracks: Dict[int, TrackedWorker] = {}
        self.next_id = 1

    def update(self, detected_person_boxes: List[Tuple[int, int, int, int]]) -> List[TrackedWorker]:
        """Updates tracks with newly detected person bounding boxes."""
        current_tracks = list(self.tracks.values())
        unmatched_detections = list(range(len(detected_person_boxes)))
        matched_track_ids = set()

        if current_tracks and detected_person_boxes:
            # Build cost matrix based on IoU
            iou_matrix = np.zeros((len(current_tracks), len(detected_person_boxes)))
            for i, track in enumerate(current_tracks):
                for j, box in enumerate(detected_person_boxes):
                    iou_matrix[i, j] = compute_iou(track.box, box)

            # Greedy matching
            while True:
                max_iou = np.max(iou_matrix) if iou_matrix.size > 0 else 0
                if max_iou < self.iou_threshold:
                    break
                row, col = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                track = current_tracks[row]
                box = detected_person_boxes[col]

                track.box = box
                track.missed_frames = 0
                matched_track_ids.add(track.track_id)
                if col in unmatched_detections:
                    unmatched_detections.remove(col)

                # Invalidate matched row and col
                iou_matrix[row, :] = -1
                iou_matrix[:, col] = -1

        # Mark missed frames for unmatched existing tracks
        for track in current_tracks:
            if track.track_id not in matched_track_ids:
                track.missed_frames += 1

        # Remove dead tracks
        self.tracks = {
            t_id: track for t_id, track in self.tracks.items()
            if track.missed_frames <= self.max_missed_frames
        }

        # Create new tracks for unmatched new detections
        for det_idx in unmatched_detections:
            new_worker = TrackedWorker(self.next_id, detected_person_boxes[det_idx])
            self.tracks[self.next_id] = new_worker
            self.next_id += 1

        return list(self.tracks.values())
