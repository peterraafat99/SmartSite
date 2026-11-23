"""
Dashboard Statistics & Telemetry Router.
"""
from fastapi import APIRouter
from typing import Dict, Any
import pandas as pd

from database.db import get_dashboard_kpis, get_recent_sensor_readings, get_active_on_site_workers
from iot.simulator import get_sensor_gateway
from core.camera_streamer import camera_service

router = APIRouter()

@router.get("/stats")
def get_stats() -> Dict[str, Any]:
    """Returns top-level industrial EHS KPI statistics."""
    kpis = get_dashboard_kpis()
    gateway = get_sensor_gateway()
    env_status = gateway.evaluate_status()
    active_workers = get_active_on_site_workers()
    
    # Get latest optical tracking metrics from live camera service
    cam_metrics = camera_service.latest_metrics

    return {
        "optical_workers_count": cam_metrics.get("worker_count", 2),
        "biometric_checked_in_count": len(active_workers),
        "ppe_compliance_rate": cam_metrics.get("compliance_rate", 87.5),
        "open_incidents_count": kpis.get("open_events", 0),
        "critical_alerts_count": kpis.get("critical_open", 0),
        "environmental_status": env_status,
        "is_zone_breach": cam_metrics.get("is_breach", False),
        "active_zone_breaches": cam_metrics.get("confirmed_breaches", 0),
        "total_recorded_incidents": kpis.get("total_events", 0)
    }

@router.get("/charts")
def get_charts_data() -> Dict[str, Any]:
    """Returns data formatted for Chart.js rendering."""
    kpis = get_dashboard_kpis()
    sensor_history = get_recent_sensor_readings(limit=40)

    category_counts = kpis.get("category_counts", {})
    priority_counts = kpis.get("priority_counts", {})

    # Sensor time series
    sensor_labels = []
    temps = []
    dusts = []
    gases = []
    noises = []

    for idx, r in enumerate(sensor_history):
        t_label = r["timestamp"][11:19] if "timestamp" in r else f"#{idx+1}"
        sensor_labels.append(t_label)
        temps.append(r.get("temperature", 0))
        dusts.append(r.get("dust", 0))
        gases.append(r.get("gas", 0))
        noises.append(r.get("noise", 0))

    return {
        "categories": {
            "labels": list(category_counts.keys()),
            "values": list(category_counts.values())
        },
        "priorities": {
            "labels": list(priority_counts.keys()),
            "values": list(priority_counts.values())
        },
        "sensor_trends": {
            "labels": sensor_labels,
            "temperature": temps,
            "dust": dusts,
            "gas": gases,
            "noise": noises
        }
    }
