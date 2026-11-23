"""
SmartSite Safety Intelligence Event Engine.
Handles ingestion, validation, de-duplication, enrichment, and storage of safety events.
"""
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List

from database.models import SafetyEvent
from database.db import insert_safety_event
from safety.risk_engine import RiskEngine
from safety.regulations import get_regulation_for_event

class SafetyEventEngine:
    """Central engine for processing, debouncing, and persisting safety events."""

    def __init__(self, debounce_seconds: float = 30.0):
        self.debounce_seconds = debounce_seconds
        # Key: (event_type, site_zone) -> float (timestamp)
        self._last_event_timestamps: Dict[tuple, float] = {}
        self._listeners: List[Callable[[SafetyEvent], None]] = []

    def register_listener(self, callback: Callable[[SafetyEvent], None]):
        """Register a callback for real-time event notifications."""
        self._listeners.append(callback)

    def is_debounced(self, event_type: str, site_zone: str) -> bool:
        """Returns True if the event occurred recently and should be suppressed."""
        key = (event_type, site_zone)
        now = time.time()
        last_time = self._last_event_timestamps.get(key, 0.0)
        if (now - last_time) < self.debounce_seconds:
            return True
        self._last_event_timestamps[key] = now
        return False

    def emit_event(
        self,
        event_type: str,
        source: str,
        site_zone: str,
        description: str,
        confidence: Optional[float] = None,
        evidence_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[SafetyEvent]:
        """
        Processes and stores an incoming safety event.
        Returns the SafetyEvent if created, or None if suppressed by debounce.
        """
        if not force and self.is_debounced(event_type, site_zone):
            return None

        # Determine hazard category & priority
        hazard_cat = RiskEngine.categorize_hazard(event_type)
        priority = RiskEngine.evaluate_priority(event_type, context)

        # Retrieve OSHA reference
        osha_reg = get_regulation_for_event(event_type)
        osha_code = osha_reg.code if osha_reg else "29 CFR 1926 Subpart E"

        # Generate unique readable Event ID
        timestamp_dt = datetime.now()
        timestamp_str = timestamp_dt.isoformat()
        unique_suffix = int(timestamp_dt.timestamp() * 1000) % 10000
        event_id = f"EVT-{timestamp_dt.strftime('%Y%m%d-%H%M%S')}-{unique_suffix:04d}"

        # If evidence image path is provided, ensure it's recorded
        event = SafetyEvent(
            event_id=event_id,
            event_type=event_type,
            source=source,
            hazard_category=hazard_cat,
            priority=priority,
            confidence=round(confidence, 3) if confidence is not None else None,
            timestamp=timestamp_str,
            site_zone=site_zone,
            evidence_path=evidence_path,
            description=description,
            status="Open",
            osha_ref=osha_code
        )

        # Store in local SQLite
        insert_safety_event(event)

        # Notify active listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

        return event

# Global singleton engine instance for the application session
_global_event_engine: Optional[SafetyEventEngine] = None

def get_event_engine(debounce_seconds: float = 25.0) -> SafetyEventEngine:
    global _global_event_engine
    if _global_event_engine is None:
        _global_event_engine = SafetyEventEngine(debounce_seconds=debounce_seconds)
    return _global_event_engine
