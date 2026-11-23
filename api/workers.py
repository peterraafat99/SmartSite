"""
Personnel Registry & Biometric Access Router.
"""
import os
import json
import cv2
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import config
from database.db import (
    get_all_registered_workers,
    get_worker_by_code,
    insert_registered_worker,
    delete_registered_worker,
    get_active_on_site_workers,
    get_access_logs,
    RegisteredWorker
)
from core.camera_streamer import camera_service

router = APIRouter()

@router.get("")
def list_workers() -> List[Dict[str, Any]]:
    """Returns all registered site personnel."""
    return get_all_registered_workers()

@router.get("/active")
@router.get("/on_site")
def get_active_workers() -> List[Dict[str, Any]]:
    """Returns workers currently checked in on site."""
    return get_active_on_site_workers()

@router.get("/access_logs")
def list_access_logs(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Returns turnstile gate access logs."""
    return get_access_logs(limit=limit, status=status)

@router.post("/enroll")
async def enroll_worker(
    worker_code: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    osha_cert: str = Form(...),
    authorized_zones: str = Form(...),
    photo: UploadFile = File(...)
):
    """
    Registers a new worker, extracts 512-d ArcFace facial biometric vector,
    and stores their credential profile.
    """
    # Check if worker already exists
    existing = get_worker_by_code(worker_code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Worker with code '{worker_code}' already exists.")

    # Save photo
    filename = f"{worker_code.lower().replace('-', '_')}_{full_name.split()[0].lower()}.jpg"
    save_path = os.path.join(config.FACES_DIR, filename)

    content = await photo.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # Compute ArcFace embedding
    img_bgr = cv2.imread(save_path)
    emb = camera_service.face_recognizer.extract_embedding(img_bgr)
    emb_json = json.dumps(emb.tolist()) if emb is not None else None

    worker = RegisteredWorker(
        worker_code=worker_code,
        full_name=full_name,
        role=role,
        osha_cert=osha_cert,
        authorized_zones=authorized_zones,
        embedding_json=emb_json,
        photo_path=save_path.replace("\\", "/")
    )

    success = insert_registered_worker(worker)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save worker record.")

    # Refresh cached embeddings in recognizer
    camera_service.face_recognizer.sync_registered_embeddings()

    return {
        "status": "ok",
        "worker_code": worker_code,
        "full_name": full_name,
        "has_biometric": emb is not None
    }

@router.delete("/{worker_code}")
def remove_worker(worker_code: str):
    """Deletes a worker from the biometric registry."""
    w = get_worker_by_code(worker_code)
    if w and w.get("photo_path") and os.path.exists(w["photo_path"]):
        try:
            os.remove(w["photo_path"])
        except Exception:
            pass
    success = delete_registered_worker(worker_code)
    if not success:
        raise HTTPException(status_code=404, detail="Worker not found")
    camera_service.face_recognizer.sync_registered_embeddings()
    return {"status": "ok", "deleted": worker_code}
