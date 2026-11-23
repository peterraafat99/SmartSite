"""
Restricted Zones Configuration Router.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional

from database.db import get_active_zone, save_restricted_zone
from database.models import RestrictedZoneConfig
from core.camera_streamer import camera_service

router = APIRouter()

class ZoneUpdatePayload(BaseModel):
    zone_name: str
    x1: float
    y1: float
    x2: float
    y2: float
    min_frames_confirmation: int = 3
    is_active: bool = True

@router.get("/active")
def get_zone() -> Dict[str, Any]:
    """Retrieves current active restricted zone."""
    zone = get_active_zone()
    if not zone:
        return {
            "zone_name": "Excavation Danger Zone (Pit A)",
            "x1": 0.55, "y1": 0.35, "x2": 0.95, "y2": 0.90,
            "min_frames_confirmation": 3, "is_active": True
        }
    return dict(zone)

@router.post("/active")
@router.post("/update")
def update_zone(payload: ZoneUpdatePayload):
    """Updates active restricted zone coordinates in DB and live stream."""
    zone = RestrictedZoneConfig(
        zone_name=payload.zone_name,
        x1=min(payload.x1, payload.x2),
        y1=min(payload.y1, payload.y2),
        x2=max(payload.x1, payload.x2),
        y2=max(payload.y1, payload.y2),
        is_active=payload.is_active,
        min_frames_confirmation=payload.min_frames_confirmation
    )
    save_restricted_zone(zone)

    # Immediately update live camera stream without restarting
    camera_service.update_zone_boundaries(zone.x1, zone.y1, zone.x2, zone.y2, name=zone.zone_name)

    return {"status": "ok", "zone": zone.to_dict()}
