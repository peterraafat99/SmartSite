"""
SmartSite Risk Assessment Engine.
Evaluates severity, hazard level, and assigns prioritized risk categories.
NOTE: Risk classifications are prototype illustrative priorities and not official OSHA severity categories.
"""
from typing import Dict, Any

class RiskEngine:
    """Evaluates safety event risk level based on hazard type, confidence, and environmental context."""

    DEFAULT_PRIORITY_RULES = {
        "ZONE_INTRUSION": "Critical",
        "SECURITY_UNAUTHORIZED_ENTRY": "Critical",
        "UNAUTHORIZED_ZONE_ENTRY": "High",
        "IOT_GAS_ALERT": "High",
        "PPE_VIOLATION_NO_HELMET": "High",
        "PPE_VIOLATION_NO_VEST": "Medium",
        "IOT_DUST_ALERT": "Medium",
        "IOT_NOISE_ALERT": "Medium",
        "IOT_TEMP_ALERT": "Medium",
        "PPE_VIOLATION_NO_BOOTS": "Medium",
        "PPE_VIOLATION_NO_GLOVES": "Low",
        "PPE_VIOLATION_NO_GOGGLE": "Low",
    }

    @classmethod
    def evaluate_priority(cls, event_type: str, context: Dict[str, Any] = None) -> str:
        """
        Determines priority (Critical, High, Medium, Low) using rule matrix and dynamic context.
        """
        context = context or {}
        base_priority = cls.DEFAULT_PRIORITY_RULES.get(event_type, "Medium")

        # Escalate zone intrusion if multiple workers or high-danger zone
        if event_type == "ZONE_INTRUSION":
            zone_name = context.get("zone_name", "").lower()
            worker_count = context.get("worker_count", 1)
            if "trench" in zone_name or "crane" in zone_name or "pit" in zone_name or worker_count > 1:
                return "Critical"
            return "High"

        # Escalate gas alerts if value is significantly higher than critical threshold
        if event_type == "IOT_GAS_ALERT":
            gas_value = context.get("gas_value", 0)
            if gas_value >= 50.0:  # e.g., > 50 ppm CO
                return "Critical"
            return "High"

        # Escalate temperature if extreme heat stress (> 40°C)
        if event_type == "IOT_TEMP_ALERT":
            temp_value = context.get("temp_value", 0)
            if temp_value >= 40.0:
                return "High"
            return "Medium"

        return base_priority

    @classmethod
    def categorize_hazard(cls, event_type: str) -> str:
        """Maps event types to human-readable hazard categories."""
        hazard_map = {
            "PPE_VIOLATION_NO_HELMET": "Head Protection",
            "PPE_VIOLATION_NO_VEST": "High-Visibility Vest",
            "PPE_VIOLATION_NO_BOOTS": "Footwear Protection",
            "PPE_VIOLATION_NO_GLOVES": "Hand Protection",
            "PPE_VIOLATION_NO_GOGGLE": "Eye & Face Protection",
            "ZONE_INTRUSION": "Restricted Zone Entry",
            "SECURITY_UNAUTHORIZED_ENTRY": "Perimeter Access & Identity Breach",
            "UNAUTHORIZED_ZONE_ENTRY": "Uncertified Personnel in Danger Zone",
            "IOT_GAS_ALERT": "Hazardous Atmosphere",
            "IOT_DUST_ALERT": "Particulate Matter / Dust",
            "IOT_TEMP_ALERT": "Thermal Stress Hazard",
            "IOT_NOISE_ALERT": "Acoustic Overexposure"
        }
        return hazard_map.get(event_type, "General Safety Hazard")
