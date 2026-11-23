"""Database module for SmartSite."""
from database.db import (
    init_db,
    get_connection,
    insert_safety_event,
    get_safety_events,
    get_all_registered_workers,
    get_worker_by_code,
    insert_registered_worker,
    delete_registered_worker,
    insert_access_log,
    get_access_logs,
    get_active_on_site_workers
)
from database.models import SafetyEvent, SensorReading, RestrictedZoneConfig, RegisteredWorker, AccessLog

__all__ = [
    "init_db",
    "get_connection",
    "insert_safety_event",
    "get_safety_events",
    "get_all_registered_workers",
    "get_worker_by_code",
    "insert_registered_worker",
    "delete_registered_worker",
    "insert_access_log",
    "get_access_logs",
    "get_active_on_site_workers",
    "SafetyEvent",
    "SensorReading",
    "RestrictedZoneConfig",
    "RegisteredWorker",
    "AccessLog"
]
