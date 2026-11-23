"""
SmartSite Facial Recognition & Site Access Verification Engine.
Powered by InsightFace (ArcFace 512-d embeddings + RetinaFace detection),
with Cosine Similarity matching against registered worker profiles.
Derived from the architecture used in the Seba project.
"""
import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import cv2
import numpy as np

from database.db import get_all_registered_workers, update_worker_embedding, insert_access_log
from database.models import AccessLog
from safety.event_engine import get_event_engine

logger = logging.getLogger(__name__)

class FaceMatchResult:
    def __init__(
        self,
        bbox: Tuple[int, int, int, int],  # x1, y1, x2, y2
        is_recognized: bool,
        worker_code: str,
        full_name: str,
        role: str,
        osha_cert: str,
        authorized_zones: str,
        similarity: float,
        det_score: float
    ):
        self.bbox = bbox
        self.is_recognized = is_recognized
        self.worker_code = worker_code
        self.full_name = full_name
        self.role = role
        self.osha_cert = osha_cert
        self.authorized_zones = authorized_zones
        self.similarity = round(similarity, 3)
        self.det_score = round(det_score, 3)

    def to_dict(self):
        return {
            "bbox": self.bbox,
            "is_recognized": self.is_recognized,
            "access_status": "Granted" if self.is_recognized else "Denied - Unregistered",
            "worker_code": self.worker_code,
            "matched_worker_code": self.worker_code,
            "full_name": self.full_name,
            "matched_worker_name": self.full_name,
            "role": self.role,
            "osha_cert": self.osha_cert,
            "authorized_zones": self.authorized_zones,
            "similarity": self.similarity,
            "confidence": self.similarity,
            "det_score": self.det_score
        }

class FaceRecognizer:
    """Manages face detection, 512-d ArcFace feature extraction, and identity matching."""

    def __init__(self, model_name: str = "buffalo_l", similarity_threshold: float = 0.45):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.app = None
        self._is_ready = False
        self._cached_embeddings: Dict[str, Dict[str, Any]] = {}
        self.load_engine()

    def load_engine(self):
        """Initializes InsightFace FaceAnalysis engine."""
        try:
            import insightface
            self.app = insightface.app.FaceAnalysis(
                name=self.model_name,
                providers=['CPUExecutionProvider']
            )
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            self._is_ready = True
            logger.info("InsightFace FaceAnalysis engine loaded successfully.")
            self.sync_registered_embeddings()
        except Exception as e:
            logger.warning(f"Could not initialize InsightFace: {e}. Face recognition will use fallback mode.")
            self._is_ready = False

    def sync_registered_embeddings(self):
        """Preloads and computes embeddings for all registered workers."""
        workers = get_all_registered_workers()
        self._cached_embeddings = {}

        for w in workers:
            w_code = w["worker_code"]
            emb = None

            # Check if embedding already in DB
            if w.get("embedding_json"):
                try:
                    emb = np.array(json.loads(w["embedding_json"]), dtype=np.float32)
                except Exception:
                    emb = None

            # Compute from photo if missing
            if emb is None and w.get("photo_path") and os.path.exists(w["photo_path"]) and self._is_ready:
                img = cv2.imread(w["photo_path"])
                if img is not None:
                    emb = self.extract_embedding(img)
                    if emb is not None:
                        # Save embedding back to DB
                        update_worker_embedding(w_code, json.dumps(emb.tolist()))

            if emb is not None:
                # Ensure L2 normalized
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                self._cached_embeddings[w_code] = {
                    "worker": w,
                    "embedding": emb
                }

    def extract_embedding(self, face_img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """Extracts 512-d ArcFace embedding from an image containing a face."""
        if not self._is_ready or self.app is None or face_img_bgr is None:
            return None

        try:
            faces = self.app.get(face_img_bgr)
            if not faces:
                return None
            # Return embedding of largest detected face
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            if hasattr(largest_face, 'normed_embedding') and largest_face.normed_embedding is not None:
                return largest_face.normed_embedding.astype(np.float32)
            elif hasattr(largest_face, 'embedding') and largest_face.embedding is not None:
                emb = largest_face.embedding.astype(np.float32)
                norm = np.linalg.norm(emb)
                return emb / norm if norm > 0 else emb
        except Exception as e:
            logger.error(f"Error extracting face embedding: {e}")
        return None

    def recognize_faces_in_frame(
        self,
        frame_bgr: np.ndarray,
        threshold: Optional[float] = None
    ) -> List[FaceMatchResult]:
        """
        Detects all faces in frame, computes embeddings, and matches against registered database.
        """
        thresh = threshold or self.similarity_threshold
        results: List[FaceMatchResult] = []

        if not self._is_ready or self.app is None:
            # Fallback face detection if insightface not loaded
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces_detected = face_cascade.detectMultiScale(gray, 1.2, 5)
            for (x, y, w, h) in faces_detected:
                results.append(FaceMatchResult(
                    bbox=(x, y, x + w, y + h),
                    is_recognized=False,
                    worker_code="UNKNOWN",
                    full_name="Unregistered Visitor",
                    role="Visitor",
                    osha_cert="None",
                    authorized_zones="None",
                    similarity=0.0,
                    det_score=0.75
                ))
            return results

        try:
            detected_faces = self.app.get(frame_bgr)
            if not detected_faces:
                return results

            for face in detected_faces:
                x1, y1, x2, y2 = [int(v) for v in face.bbox]
                det_score = float(face.det_score)
                query_emb = getattr(face, 'normed_embedding', None)
                if query_emb is None and hasattr(face, 'embedding'):
                    q_norm = np.linalg.norm(face.embedding)
                    query_emb = face.embedding / q_norm if q_norm > 0 else face.embedding

                best_sim = -1.0
                best_worker = None

                if query_emb is not None and self._cached_embeddings:
                    # Compute cosine similarity across all enrolled profiles
                    for w_code, data in self._cached_embeddings.items():
                        ref_emb = data["embedding"]
                        sim = float(np.dot(query_emb, ref_emb))
                        if sim > best_sim:
                            best_sim = sim
                            best_worker = data["worker"]

                if best_worker and best_sim >= thresh:
                    results.append(FaceMatchResult(
                        bbox=(x1, y1, x2, y2),
                        is_recognized=True,
                        worker_code=best_worker["worker_code"],
                        full_name=best_worker["full_name"],
                        role=best_worker["role"],
                        osha_cert=best_worker["osha_cert"],
                        authorized_zones=best_worker["authorized_zones"],
                        similarity=best_sim,
                        det_score=det_score
                    ))
                else:
                    results.append(FaceMatchResult(
                        bbox=(x1, y1, x2, y2),
                        is_recognized=False,
                        worker_code="UNKNOWN",
                        full_name="Unidentified Person",
                        role="Unknown Visitor",
                        osha_cert="Unverified",
                        authorized_zones="None",
                        similarity=max(0.0, best_sim),
                        det_score=det_score
                    ))

        except Exception as e:
            logger.error(f"Error during face recognition: {e}")

        return results

    def process_access_gate_frame(
        self,
        frame_bgr: np.ndarray,
        gate_name: str = "Gate 1 - Main Turnstile",
        emit_events: bool = True
    ) -> Tuple[np.ndarray, List[FaceMatchResult]]:
        """
        Runs face recognition, renders turnstile badges, and records access logs.
        """
        annotated = frame_bgr.copy()
        matches = self.recognize_faces_in_frame(annotated)
        engine = get_event_engine()
        now_dt = datetime.now()

        for match in matches:
            x1, y1, x2, y2 = match.bbox

            if match.is_recognized:
                # Green border for authorized
                color = (0, 210, 100)
                status_text = f"GRANTED: {match.full_name} ({match.worker_code})"
                sub_text = f"Role: {match.role} | Cert: {match.osha_cert}"
                access_status = "Granted"
            else:
                # Crimson Red for denied / unknown
                color = (0, 0, 230)
                status_text = "ACCESS DENIED: UNREGISTERED"
                sub_text = "Unknown visitor - Turnstile locked"
                access_status = "Denied - Unregistered"

                # Emit security safety event
                if emit_events:
                    engine.emit_event(
                        event_type="SECURITY_UNAUTHORIZED_ENTRY",
                        source="ACCESS_CONTROL",
                        site_zone=gate_name,
                        description=f"Unregistered individual attempted entry at {gate_name}. Facial biometric not matched.",
                        confidence=match.det_score,
                        context={"gate_name": gate_name}
                    )

            # Draw face box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw tag box
            (tw, th), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 24)), (x1 + max(tw, 280) + 10, y1), color, -1)
            cv2.putText(annotated, status_text, (x1 + 5, max(14, y1 - 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(annotated, sub_text, (x1 + 5, max(26, y1 - 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (30, 30, 30), 1, cv2.LINE_AA)

            # Record access log
            log_id = f"ACC-{now_dt.strftime('%Y%m%d-%H%M%S')}-{int(now_dt.timestamp()*1000)%1000:03d}"
            log = AccessLog(
                log_id=log_id,
                worker_code=match.worker_code,
                worker_name=match.full_name,
                timestamp=now_dt.isoformat(),
                gate_name=gate_name,
                status=access_status,
                confidence=match.similarity if match.is_recognized else match.det_score,
                snapshot_path=None,
                notes=f"Biometric similarity: {match.similarity*100:.1f}%"
            )
            insert_access_log(log)

        # Top banner on gate camera
        h, w = annotated.shape[:2]
        cv2.rectangle(annotated, (0, 0), (w, 32), (15, 23, 42), -1)
        gate_banner = f"TURNSTILE GATE CAMERA: {gate_name.upper()}  |  FACIAL ACCESS CONTROL ACTIVE"
        cv2.putText(annotated, gate_banner, (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (56, 189, 248), 1, cv2.LINE_AA)

        return annotated, matches

# Singleton face recognizer
_global_face_recognizer: Optional[FaceRecognizer] = None

def get_face_recognizer() -> FaceRecognizer:
    global _global_face_recognizer
    if _global_face_recognizer is None:
        _global_face_recognizer = FaceRecognizer()
    return _global_face_recognizer
