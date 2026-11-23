"""
Safety Incidents & Audit Log Management Router.
"""
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd
import io

from database.db import get_safety_events, get_event_by_id, update_event_status, delete_event
from safety.regulations import get_regulation_for_event

router = APIRouter()

class StatusUpdatePayload(BaseModel):
    status: str  # Open, Acknowledged, Resolved

@router.get("")
def list_incidents(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    hazard: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 150
) -> List[Dict[str, Any]]:
    """Retrieves filtered list of safety events."""
    events = get_safety_events(status=status, priority=priority, hazard=hazard, limit=limit)
    if search:
        q = search.lower()
        events = [
            e for e in events
            if q in e["event_id"].lower() or q in e["description"].lower() or q in e["site_zone"].lower()
        ]
    return events

@router.get("/{event_id}")
def get_incident(event_id: str) -> Dict[str, Any]:
    """Retrieves full incident details including OSHA regulatory guidance."""
    event = get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Incident not found")

    reg = get_regulation_for_event(event["event_type"])
    return {
        "event": event,
        "regulation": {
            "code": reg.code,
            "title": reg.title,
            "summary": reg.summary,
            "measures": reg.required_measures,
            "action": reg.recommended_action,
            "official_url": reg.official_url
        } if reg else None
    }

@router.patch("/{event_id}/status")
def change_incident_status(event_id: str, payload: StatusUpdatePayload):
    """Updates incident lifecycle state (Open -> Acknowledged -> Resolved)."""
    valid = ["Open", "Acknowledged", "Resolved"]
    if payload.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")

    success = update_event_status(event_id, payload.status)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "ok", "event_id": event_id, "new_status": payload.status}

@router.delete("/{event_id}")
def remove_incident(event_id: str):
    """Deletes an incident by ID."""
    success = delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "ok", "deleted": event_id}

@router.get("/export/csv")
def export_incidents_csv():
    """Exports all incidents as an official EHS audit CSV file."""
    events = get_safety_events(limit=1000)
    df = pd.DataFrame(events)

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    csv_bytes = stream.getvalue().encode('utf-8')

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=smartsite_incident_audit.csv"}
    )
