"""
Live Video Streaming & Computer Vision Inference Router.
Provides low-latency MJPEG video streaming and biometric turnstile endpoints.
"""
import os
import cv2
import base64
import tempfile
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from core.camera_streamer import camera_service
from database.db import get_worker_by_code
import config

router = APIRouter()

class StreamControlPayload(BaseModel):
    action: str  # play, pause, stop

class StreamSourcePayload(BaseModel):
    source_type: str  # sample, webcam, file
    source_path: Optional[str] = None

@router.get("/ppe")
def stream_ppe_video():
    """Returns low-latency MJPEG stream with YOLO & restricted zone annotations."""
    if not camera_service.is_running:
        camera_service.start()

    return StreamingResponse(
        camera_service.get_ppe_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.get("/metrics")
def get_stream_metrics() -> Dict[str, Any]:
    """Returns real-time telemetry from latest processed frame."""
    return {
        "is_running": camera_service.is_running,
        "is_paused": camera_service.is_paused,
        "source": os.path.basename(camera_service.source_path),
        "metrics": camera_service.latest_metrics,
        "model_info": camera_service.detector.get_model_info()
    }

@router.post("/controls")
def control_stream(payload: StreamControlPayload):
    """Controls stream state: play, pause, stop."""
    action = payload.action.lower()
    if action == "play":
        if not camera_service.is_running:
            camera_service.start()
        camera_service.is_paused = False
    elif action == "pause":
        camera_service.is_paused = True
    elif action == "stop":
        camera_service.stop()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    return {"status": "ok", "action": action}

@router.post("/source")
def set_stream_source(payload: StreamSourcePayload):
    """Switches camera source between demo video, uploaded footage, and webcam."""
    stype = payload.source_type.lower()
    if stype == "sample":
        src = config.SAMPLE_VIDEO_PATH
    elif stype == "webcam":
        src = "0"
    elif stype == "file" and payload.source_path and os.path.exists(payload.source_path):
        src = payload.source_path
    else:
        raise HTTPException(status_code=400, detail="Invalid source path or type")

    camera_service.start(src)
    return {"status": "ok", "source": src}

@router.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    """Uploads custom video file (MP4, AVI) and sets it as the active stream source."""
    suffix = os.path.splitext(file.filename)[1] or ".mp4"
    save_path = os.path.join(config.VIDEOS_DIR, f"uploaded_{file.filename}")

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    camera_service.start(save_path)
    return {"status": "ok", "filename": file.filename, "path": save_path}

@router.post("/gate_verify")
async def verify_gate_biometric(
    file: Optional[UploadFile] = File(None),
    worker_code: Optional[str] = Form(None),
    demo_worker_code: Optional[str] = Form(None),
    gate_name: str = Form("Gate 1 - Main Turnstile")
):
    """
    Runs ArcFace biometric identity verification on a turnstile ingress image.
    Supports either an uploaded photo or an enrolled worker code.
    """
    image_bgr = None

    if file:
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        target_code = worker_code or demo_worker_code
        if target_code:
            w = get_worker_by_code(target_code)
            if w and w.get("photo_path") and os.path.exists(w["photo_path"]):
                image_bgr = cv2.imread(w["photo_path"])

    if image_bgr is None:
        raise HTTPException(status_code=400, detail="No valid face image provided for biometric verification")

    # Run face recognition
    annotated_bgr, matches = camera_service.face_recognizer.process_access_gate_frame(
        image_bgr, gate_name=gate_name, emit_events=True
    )

    # Encode annotated frame to JPEG base64 for browser display
    _, buf = cv2.imencode('.jpg', annotated_bgr)
    b64_img = base64.b64encode(buf).decode('utf-8')

    return {
        "status": "ok",
        "matches": [m.to_dict() for m in matches],
        "annotated_image": f"data:image/jpeg;base64,{b64_img}"
    }

@router.post("/analyze_image")
async def analyze_single_image(
    file: Optional[UploadFile] = File(None),
    dataset_image: Optional[str] = Form(None),
    conf_threshold: float = Form(0.25),
    enable_zone: bool = Form(True),
    zone_x1: Optional[float] = Form(None),
    zone_y1: Optional[float] = Form(None),
    zone_x2: Optional[float] = Form(None),
    zone_y2: Optional[float] = Form(None),
    zone_name: Optional[str] = Form(None)
):
    """
    Runs YOLO PPE detection and danger zone analysis on a submitted single image.
    Supports uploaded custom site photos or authentic Construction-PPE dataset scenes.
    """
    image_bgr = None
    if file:
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif dataset_image:
        dataset_dir = os.path.join(config.DATA_DIR, "datasets", "construction-ppe", "images", "train")
        img_path = os.path.join(dataset_dir, os.path.basename(dataset_image))
        if os.path.exists(img_path):
            image_bgr = cv2.imread(img_path)

    if image_bgr is None:
        raise HTTPException(status_code=400, detail="No valid image provided for AI vision analysis.")

    # Update danger zone if enabled and specified in request
    if enable_zone and zone_x1 is not None and zone_x2 is not None and zone_y1 is not None and zone_y2 is not None:
        camera_service.zone_detector.update_zone(
            x1_norm=zone_x1,
            y1_norm=zone_y1,
            x2_norm=zone_x2,
            y2_norm=zone_y2,
            name=zone_name or "Restricted Danger Zone"
        )

    # Run detection with specified confidence and single-frame immediate breach evaluation
    prev_conf = camera_service.processor.conf_threshold
    camera_service.processor.conf_threshold = conf_threshold
    annotated_bgr, metrics = camera_service.processor.process_frame(
        image_bgr,
        emit_events=True,
        resize=False,
        single_frame_mode=True,
        enable_zone=enable_zone
    )
    camera_service.processor.conf_threshold = prev_conf
    detections = metrics.get("detections", [])
    workers = metrics.get("workers", [])

    # Encode annotated image
    _, buf = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_img = base64.b64encode(buf).decode('utf-8')

    return {
        "status": "ok",
        "worker_count": metrics["worker_count"],
        "compliance_rate": metrics["ppe_summary"]["compliance_rate"],
        "zone_status": metrics["zone_status"],
        "zone_name": camera_service.zone_detector.name,
        "workers": workers,
        "detections": [
            {
                "class_name": d.class_name,
                "confidence": round(d.conf, 2),
                "box": d.box,
                "is_violation": d.is_violation,
                "is_ppe": d.is_ppe
            }
            for d in detections
        ],
        "annotated_image": f"data:image/jpeg;base64,{b64_img}"
    }

@router.get("/sample_images")
def get_sample_dataset_images():
    """Returns curated authentic construction scenes with metadata and recommended danger zones."""
    dataset_dir = os.path.join(config.DATA_DIR, "datasets", "construction-ppe", "images", "train")
    if not os.path.exists(dataset_dir):
        return {"samples": []}

    curated = [
        {
            "id": "source-32b77e88696e2ba988310ec62da94f16.jpg",
            "title": "Excavation Pit & Heavy Machinery",
            "category": "Deep Excavation Zone",
            "description": "Active earthwork pit with tracked excavator and ground personnel. Tests restricted pit intrusion.",
            "recommended_zone": {"x1": 0.55, "y1": 0.35, "x2": 0.95, "y2": 0.92, "name": "Pit B Excavation Area"},
            "tag": "High Risk"
        },
        {
            "id": "source-cc3e6e8b453515c1824fa91042214b71.jpg",
            "title": "Scaffolding & Structural Framework",
            "category": "Working at Heights",
            "description": "Multi-tier structural scaffold with workers at elevation. PPE head and fall protection inspection.",
            "recommended_zone": {"x1": 0.20, "y1": 0.25, "x2": 0.85, "y2": 0.88, "name": "Scaffold Drop Zone Perimeter"},
            "tag": "Fall Hazard"
        },
        {
            "id": "source-4c8b02d254dd8190897f4ce0e54ef9f7.jpg",
            "title": "Material Staging & Ground Crew",
            "category": "Staging Sector",
            "description": "Ground crew handling building materials. High-vis vest and mandatory hard hat compliance.",
            "recommended_zone": {"x1": 0.45, "y1": 0.30, "x2": 0.90, "y2": 0.90, "name": "Material Staging Exclusion Zone"},
            "tag": "PPE Audit"
        },
        {
            "id": "source-ba3aa5d1715142e5e962c3376ceca1a6.jpg",
            "title": "Overhead Crane & Steel Assembly",
            "category": "Crane Operations",
            "description": "Ironworkers working beneath overhead steel framework. Tests crane swing radius exclusion.",
            "recommended_zone": {"x1": 0.25, "y1": 0.20, "x2": 0.75, "y2": 0.75, "name": "Crane Swing Radius Exclusion"},
            "tag": "Overhead Hazard"
        },
        {
            "id": "source-012007571544d108ad62099e53b8a827.jpg",
            "title": "High-Density Workforce Deployment",
            "category": "Field Inspection",
            "description": "Multiple workers in close proximity for bulk PPE classification and zone contact verification.",
            "recommended_zone": {"x1": 0.40, "y1": 0.20, "x2": 0.85, "y2": 0.85, "name": "Restricted Pit Zone"},
            "tag": "Bulk Crew"
        },
        {
            "id": "source-f4532be7ff670b1a99ec14fdae4b0557.jpg",
            "title": "Perimeter Gate Access Corridor",
            "category": "Transit Route",
            "description": "Access road and pedestrian walkway separation. Tests pedestrian intrusion into vehicle corridors.",
            "recommended_zone": {"x1": 0.15, "y1": 0.40, "x2": 0.65, "y2": 0.95, "name": "Vehicle Transit Corridor"},
            "tag": "Separation Zone"
        }
    ]

    # Filter to files that actually exist
    available = []
    for c in curated:
        if os.path.exists(os.path.join(dataset_dir, c["id"])):
            c["thumbnail"] = f"/dataset_images/{c['id']}"
            available.append(c)

    return {
        "samples": available,
        "images": [c["id"] for c in available]
    }
