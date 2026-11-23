"""
Simulated IoT Environmental Sensor Gateway Router.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from iot.simulator import get_sensor_gateway
from database.db import get_recent_sensor_readings

router = APIRouter()

class PresetPayload(BaseModel):
    preset_name: Optional[str] = None
    preset: Optional[str] = None

    @property
    def target_name(self) -> str:
        return self.preset_name or self.preset or "Normal Conditions"

class ManualSensorPayload(BaseModel):
    temperature: float
    humidity: float
    dust: float
    gas: float
    noise: float

@router.get("/current")
def get_current_sensor_values() -> Dict[str, Any]:
    """Returns current real-time environmental telemetry and status."""
    gw = get_sensor_gateway()
    # Step simulation if auto drift active
    if gw.is_auto_simulating:
        gw.step_simulation()
    alerts = gw.check_and_emit_alerts()

    return {
        "values": gw.read_current_values(),
        "status": gw.evaluate_status(),
        "preset": gw.current_preset,
        "is_auto": gw.is_auto_simulating,
        "recent_alerts": alerts
    }

@router.post("/preset")
def set_preset(payload: PresetPayload):
    """Applies a predefined environmental operational scenario."""
    gw = get_sensor_gateway()
    name = payload.target_name
    if name not in gw.PRESETS:
        raise HTTPException(status_code=400, detail=f"Invalid preset. Available: {list(gw.PRESETS.keys())}")

    gw.apply_preset(name)
    alerts = gw.check_and_emit_alerts()
    return {"status": "ok", "preset": name, "values": gw.read_current_values(), "alerts": alerts}

@router.post("/manual")
def set_manual(payload: ManualSensorPayload):
    """Applies manual sensor slider adjustments."""
    gw = get_sensor_gateway()
    gw.set_manual_values(
        temp=payload.temperature,
        humidity=payload.humidity,
        dust=payload.dust,
        gas=payload.gas,
        noise=payload.noise
    )
    alerts = gw.check_and_emit_alerts()
    return {"status": "ok", "values": gw.read_current_values(), "status_level": gw.evaluate_status(), "alerts": alerts}

@router.get("/history")
def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves chronological sensor history for Chart.js graphing."""
    return get_recent_sensor_readings(limit=limit)
