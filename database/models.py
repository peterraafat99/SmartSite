"""
SmartSite Database Models and Schema Definitions.
"""
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

@dataclass
class SafetyEvent:
    event_id: str
    event_type: str
    source: str  # AI_CAMERA, IOT_SENSOR, MANUAL
    hazard_category: str
    priority: str  # Critical, High, Medium, Low
    confidence: Optional[float]
    timestamp: str
    site_zone: str
    evidence_path: Optional[str]
    description: str
    status: str = "Open"  # Open, Acknowledged, Resolved
    osha_ref: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class SensorReading:
    timestamp: str
    temperature: float  # °C
    humidity: float     # %
    dust: float         # µg/m³
    gas: float          # ppm
    noise: float        # dBA
    status: str = "Normal"  # Normal, Warning, Critical
    id: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class RestrictedZoneConfig:
    zone_name: str
    x1: float  # Normalized 0.0 - 1.0
    y1: float  # Normalized 0.0 - 1.0
    x2: float  # Normalized 0.0 - 1.0
    y2: float  # Normalized 0.0 - 1.0
    is_active: bool = True
    min_frames_confirmation: int = 3
    id: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class RegisteredWorker:
    worker_code: str  # e.g., WRK-101
    full_name: str
    role: str         # e.g., Crane Operator, Electrician, Safety Officer
    osha_cert: str    # e.g., OSHA 30, OSHA 10, Site Induction
    authorized_zones: str  # Comma-separated zones, e.g., "Main Perimeter, Pit A"
    embedding_json: Optional[str] = None  # JSON string of 512-d normalized embedding
    photo_path: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class AccessLog:
    log_id: str
    worker_code: str
    worker_name: str
    timestamp: str
    gate_name: str
    status: str       # Granted, Denied - Unregistered, Denied - Unauthorized Zone
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self):
        return asdict(self)

