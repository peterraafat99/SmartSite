"""
SmartSite Local SQLite Database Management Module.
Thread-safe local database access with automatic schema initialization.
"""
import os
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import random

from database.models import SafetyEvent, SensorReading, RestrictedZoneConfig, RegisteredWorker, AccessLog

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "smartsite.db")

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DB_PATH):
    """Initializes tables and indexes in SQLite."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS safety_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        source TEXT NOT NULL,
        hazard_category TEXT NOT NULL,
        priority TEXT NOT NULL,
        confidence REAL,
        timestamp TEXT NOT NULL,
        site_zone TEXT NOT NULL,
        evidence_path TEXT,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open',
        osha_ref TEXT
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_events_timestamp ON safety_events (timestamp DESC);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_events_status ON safety_events (status);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_events_priority ON safety_events (priority);
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        dust REAL NOT NULL,
        gas REAL NOT NULL,
        noise REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Normal'
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_readings (timestamp DESC);
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS restricted_zones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_name TEXT NOT NULL,
        x1 REAL NOT NULL,
        y1 REAL NOT NULL,
        x2 REAL NOT NULL,
        y2 REAL NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        min_frames_confirmation INTEGER NOT NULL DEFAULT 3
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS registered_workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        osha_cert TEXT NOT NULL,
        authorized_zones TEXT NOT NULL,
        embedding_json TEXT,
        photo_path TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_id TEXT UNIQUE NOT NULL,
        worker_code TEXT NOT NULL,
        worker_name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        gate_name TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence REAL,
        snapshot_path TEXT,
        notes TEXT
    )
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_access_timestamp ON access_logs (timestamp DESC);
    """)

    conn.commit()

    # Seed default zone if none exists
    cur.execute("SELECT COUNT(*) FROM restricted_zones")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO restricted_zones (zone_name, x1, y1, x2, y2, is_active, min_frames_confirmation)
        VALUES ('Excavation Danger Zone (Pit A)', 0.55, 0.40, 0.95, 0.90, 1, 3)
        """)
        conn.commit()

    # Seed initial demo events if table is completely empty
    cur.execute("SELECT COUNT(*) FROM safety_events")
    if cur.fetchone()[0] == 0:
        seed_demo_data(conn)

    conn.close()

def seed_demo_data(conn: sqlite3.Connection):
    """Seed initial representative safety events and sensor readings for prototype demo."""
    now = datetime.now()
    demo_events = [
        (
            f"EVT-{(now - timedelta(hours=3)).strftime('%Y%m%d-%H%M%S')}-001",
            "PPE_VIOLATION_NO_HELMET",
            "AI_CAMERA",
            "Head Protection",
            "High",
            0.89,
            (now - timedelta(hours=3)).isoformat(),
            "Zone 1 - Main Perimeter",
            None,
            "Worker detected without required protective hard hat near crane swing radius.",
            "Open",
            "29 CFR 1926.100"
        ),
        (
            f"EVT-{(now - timedelta(hours=2)).strftime('%Y%m%d-%H%M%S')}-002",
            "ZONE_INTRUSION",
            "AI_CAMERA",
            "Restricted Zone",
            "Critical",
            0.94,
            (now - timedelta(hours=2)).isoformat(),
            "Excavation Danger Zone (Pit A)",
            None,
            "Unauthorized worker entered active trench excavation zone without spotter.",
            "Acknowledged",
            "29 CFR 1926 Subpart P"
        ),
        (
            f"EVT-{(now - timedelta(hours=1)).strftime('%Y%m%d-%H%M%S')}-003",
            "IOT_GAS_ALERT",
            "IOT_SENSOR",
            "Hazardous Atmosphere",
            "High",
            0.98,
            (now - timedelta(hours=1)).isoformat(),
            "Basement Sector B",
            None,
            "SIMULATED: Carbon Monoxide reading exceeded demo threshold (42.0 ppm > 35.0 ppm limit).",
            "Open",
            "29 CFR 1926 Subpart E"
        ),
        (
            f"EVT-{(now - timedelta(minutes=25)).strftime('%Y%m%d-%H%M%S')}-004",
            "PPE_VIOLATION_NO_VEST",
            "AI_CAMERA",
            "High-Visibility Vest",
            "Medium",
            0.84,
            (now - timedelta(minutes=25)).isoformat(),
            "Vehicle Loading Bay",
            None,
            "Worker without high-visibility safety vest operating near forklift traffic lane.",
            "Resolved",
            "29 CFR 1926.201"
        )
    ]

    cur = conn.cursor()
    cur.executemany("""
    INSERT INTO safety_events 
    (event_id, event_type, source, hazard_category, priority, confidence, timestamp, site_zone, evidence_path, description, status, osha_ref)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, demo_events)

    # Seed 30 minutes of historical simulated sensor readings
    sensor_rows = []
    base_time = now - timedelta(minutes=45)
    for i in range(45):
        t = base_time + timedelta(minutes=i)
        temp = 24.0 + 3.0 * random.random()
        humidity = 48.0 + 5.0 * random.random()
        dust = 35.0 + 15.0 * random.random()
        gas = 8.0 + 4.0 * random.random()
        noise = 72.0 + 6.0 * random.random()
        status = "Normal"
        sensor_rows.append((t.isoformat(), temp, humidity, dust, gas, noise, status))

    cur.executemany("""
    INSERT INTO sensor_readings (timestamp, temperature, humidity, dust, gas, noise, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sensor_rows)

    conn.commit()

# --- Safety Events API ---

def insert_safety_event(event: SafetyEvent, db_path: str = DB_PATH) -> bool:
    """Insert a new safety event if event_id does not already exist."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO safety_events 
        (event_id, event_type, source, hazard_category, priority, confidence, timestamp, site_zone, evidence_path, description, status, osha_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.event_type,
            event.source,
            event.hazard_category,
            event.priority,
            event.confidence,
            event.timestamp,
            event.site_zone,
            event.evidence_path,
            event.description,
            event.status,
            event.osha_ref
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_safety_events(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    hazard: Optional[str] = None,
    limit: int = 200,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """Retrieve filtered list of safety events."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    query = "SELECT * FROM safety_events WHERE 1=1"
    params = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if priority and priority != "All":
        query += " AND priority = ?"
        params.append(priority)
    if hazard and hazard != "All":
        query += " AND hazard_category = ?"
        params.append(hazard)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def get_event_by_id(event_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve single event by event_id."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM safety_events WHERE event_id = ?", (event_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_event_status(event_id: str, new_status: str, db_path: str = DB_PATH) -> bool:
    """Update status of a safety event (Open, Acknowledged, Resolved)."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE safety_events SET status = ? WHERE event_id = ?", (new_status, event_id))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def delete_event(event_id: str, db_path: str = DB_PATH) -> bool:
    """Delete an event by ID."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM safety_events WHERE event_id = ?", (event_id,))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected

# --- Sensor Readings API ---

def insert_sensor_reading(reading: SensorReading, db_path: str = DB_PATH) -> int:
    """Insert a new environmental sensor reading."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO sensor_readings (timestamp, temperature, humidity, dust, gas, noise, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        reading.timestamp,
        reading.temperature,
        reading.humidity,
        reading.dust,
        reading.gas,
        reading.noise,
        reading.status
    ))
    last_id = cur.lastrowid
    conn.commit()
    conn.close()
    return last_id

def get_recent_sensor_readings(limit: int = 100, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Get the most recent sensor readings ordered chronologically for plotting."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT * FROM (
        SELECT * FROM sensor_readings ORDER BY id DESC LIMIT ?
    ) ORDER BY id ASC
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def get_latest_sensor_reading(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Get single most recent sensor reading."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Restricted Zones API ---

def get_active_zone(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve active restricted zone."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM restricted_zones WHERE is_active = 1 LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def save_restricted_zone(zone: RestrictedZoneConfig, db_path: str = DB_PATH) -> int:
    """Save or update the active restricted zone."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    # Check if existing zone
    cur.execute("SELECT id FROM restricted_zones LIMIT 1")
    existing = cur.fetchone()
    if existing:
        cur.execute("""
        UPDATE restricted_zones 
        SET zone_name = ?, x1 = ?, y1 = ?, x2 = ?, y2 = ?, is_active = ?, min_frames_confirmation = ?
        WHERE id = ?
        """, (
            zone.zone_name,
            zone.x1,
            zone.y1,
            zone.x2,
            zone.y2,
            1 if zone.is_active else 0,
            zone.min_frames_confirmation,
            existing["id"]
        ))
        zid = existing["id"]
    else:
        cur.execute("""
        INSERT INTO restricted_zones (zone_name, x1, y1, x2, y2, is_active, min_frames_confirmation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            zone.zone_name,
            zone.x1,
            zone.y1,
            zone.x2,
            zone.y2,
            1 if zone.is_active else 0,
            zone.min_frames_confirmation
        ))
        zid = cur.lastrowid
    conn.commit()
    conn.close()
    return zid

# --- Overview Statistics API ---

def get_dashboard_kpis(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Calculates summary KPIs for the Overview dashboard."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    # Active (Open) events count
    cur.execute("SELECT COUNT(*) FROM safety_events WHERE status = 'Open'")
    open_events = cur.fetchone()[0]

    # Critical events count
    cur.execute("SELECT COUNT(*) FROM safety_events WHERE priority = 'Critical' AND status = 'Open'")
    critical_open = cur.fetchone()[0]

    # Total recorded events
    cur.execute("SELECT COUNT(*) FROM safety_events")
    total_events = cur.fetchone()[0]

    # Resolved events
    cur.execute("SELECT COUNT(*) FROM safety_events WHERE status = 'Resolved'")
    resolved_events = cur.fetchone()[0]

    # Events breakdown by category
    cur.execute("""
    SELECT hazard_category, COUNT(*) as count 
    FROM safety_events 
    GROUP BY hazard_category
    """)
    category_counts = {row["hazard_category"]: row["count"] for row in cur.fetchall()}

    # Events breakdown by priority
    cur.execute("""
    SELECT priority, COUNT(*) as count 
    FROM safety_events 
    GROUP BY priority
    """)
    priority_counts = {row["priority"]: row["count"] for row in cur.fetchall()}

    # Recent 5 events
    cur.execute("SELECT * FROM safety_events ORDER BY timestamp DESC LIMIT 5")
    recent_events = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        "open_events": open_events,
        "critical_open": critical_open,
        "total_events": total_events,
        "resolved_events": resolved_events,
        "category_counts": category_counts,
        "priority_counts": priority_counts,
        "recent_events": recent_events
    }

# --- Site Access Control & Worker Registry API ---

def seed_demo_workers(conn: sqlite3.Connection):
    """Placeholder - demo faces removed as requested. Personnel are registered dynamically."""
    pass

def insert_registered_worker(worker: RegisteredWorker, db_path: str = DB_PATH) -> bool:
    """Register a new worker with photo and optional face embedding."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO registered_workers
        (worker_code, full_name, role, osha_cert, authorized_zones, embedding_json, photo_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            worker.worker_code,
            worker.full_name,
            worker.role,
            worker.osha_cert,
            worker.authorized_zones,
            worker.embedding_json,
            worker.photo_path,
            worker.created_at or datetime.now().isoformat()
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_worker_embedding(worker_code: str, embedding_json: str, db_path: str = DB_PATH) -> bool:
    """Updates stored facial embedding vector for a worker."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE registered_workers SET embedding_json = ? WHERE worker_code = ?", (embedding_json, worker_code))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def get_all_registered_workers(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve list of all registered site workers."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM registered_workers ORDER BY id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_worker_by_code(worker_code: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve specific worker by worker_code."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM registered_workers WHERE worker_code = ?", (worker_code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_registered_worker(worker_code: str, db_path: str = DB_PATH) -> bool:
    """Remove a worker from registration database."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM registered_workers WHERE worker_code = ?", (worker_code,))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def insert_access_log(log: AccessLog, db_path: str = DB_PATH) -> bool:
    """Record an access control turnstile entry/exit event."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO access_logs
        (log_id, worker_code, worker_name, timestamp, gate_name, status, confidence, snapshot_path, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log.log_id,
            log.worker_code,
            log.worker_name,
            log.timestamp,
            log.gate_name,
            log.status,
            log.confidence,
            log.snapshot_path,
            log.notes
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_access_logs(limit: int = 100, status: Optional[str] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Get recent gate access logs."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    query = "SELECT * FROM access_logs WHERE 1=1"
    params = []
    if status and status != "All":
        query += " AND status LIKE ?"
        params.append(f"%{status}%")
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_active_on_site_workers(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Returns unique workers whose latest gate entry is Granted (currently on site)."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT al.worker_code, al.worker_name, al.timestamp, al.gate_name, rw.role, rw.osha_cert, rw.authorized_zones, rw.photo_path
    FROM access_logs al
    JOIN registered_workers rw ON al.worker_code = rw.worker_code
    WHERE al.status = 'Granted'
    GROUP BY al.worker_code
    ORDER BY al.timestamp DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

