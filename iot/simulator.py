"""
SmartSite Simulated IoT Environmental Sensor Gateway.
Modular sensor interface allowing seamless swap between simulated readings and physical MQTT / Modbus sensors.
All readings are labeled as SIMULATED (DEMO).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
import random

from database.models import SensorReading
from database.db import insert_sensor_reading
from safety.event_engine import get_event_engine

@dataclass
class SensorThresholds:
    temp_warn: float = 35.0      # °C
    temp_crit: float = 40.0      # °C
    dust_warn: float = 100.0     # µg/m³
    dust_crit: float = 150.0     # µg/m³
    gas_warn: float = 25.0       # ppm (CO equivalent)
    gas_crit: float = 50.0       # ppm
    noise_warn: float = 85.0     # dBA
    noise_crit: float = 95.0     # dBA
    humidity_min: float = 20.0   # %
    humidity_max: float = 85.0   # %

class BaseSensorGateway(ABC):
    """Abstract interface for IoT Environmental Sensor Gateways."""

    @abstractmethod
    def read_current_values(self) -> Dict[str, float]:
        """Returns mapping of sensor parameter names to float values."""
        pass

    @abstractmethod
    def evaluate_status(self) -> str:
        """Returns overall status: 'Normal', 'Warning', or 'Critical'."""
        pass

class SimulatedSensorGateway(BaseSensorGateway):
    """
    Simulated IoT environmental sensor gateway with scenario presets,
    continuous realistic noise drift, and automated event triggers.
    """

    PRESETS = {
        "Normal Conditions": {
            "temp": 24.5, "humidity": 48.0, "dust": 28.0, "gas": 6.5, "noise": 72.0,
            "description": "Typical ambient conditions on an active construction perimeter."
        },
        "High-Temperature (Heat Stress)": {
            "temp": 41.2, "humidity": 42.0, "dust": 45.0, "gas": 9.0, "noise": 75.0,
            "description": "Extreme solar radiation; triggers thermal stress alert."
        },
        "High-Dust (Demolition / Cutting)": {
            "temp": 26.0, "humidity": 38.0, "dust": 178.5, "gas": 12.0, "noise": 88.0,
            "description": "Heavy airborne particulate matter from masonry demolition."
        },
        "Gas Warning (Confined Space / Trench)": {
            "temp": 25.0, "humidity": 55.0, "dust": 35.0, "gas": 58.2, "noise": 70.0,
            "description": "Hazardous toxic / combustible gas accumulation."
        },
        "High-Noise (Piling / Heavy Drilling)": {
            "temp": 23.5, "humidity": 50.0, "dust": 52.0, "gas": 8.0, "noise": 99.4,
            "description": "Excessive acoustic exposure above permissible 85 dBA action level."
        }
    }

    def __init__(self, thresholds: Optional[SensorThresholds] = None):
        self.thresholds = thresholds or SensorThresholds()
        self.current_preset = "Normal Conditions"
        # Current baseline readings
        preset_vals = self.PRESETS[self.current_preset]
        self.temperature = preset_vals["temp"]
        self.humidity = preset_vals["humidity"]
        self.dust = preset_vals["dust"]
        self.gas = preset_vals["gas"]
        self.noise = preset_vals["noise"]
        self.is_auto_simulating = True

    def apply_preset(self, preset_name: str):
        """Switches current values to a predefined operational scenario."""
        if preset_name in self.PRESETS:
            self.current_preset = preset_name
            vals = self.PRESETS[preset_name]
            self.temperature = vals["temp"]
            self.humidity = vals["humidity"]
            self.dust = vals["dust"]
            self.gas = vals["gas"]
            self.noise = vals["noise"]

    def set_manual_values(self, temp: float, humidity: float, dust: float, gas: float, noise: float):
        """Allows direct manual adjustments from UI sliders."""
        self.temperature = float(temp)
        self.humidity = float(humidity)
        self.dust = float(dust)
        self.gas = float(gas)
        self.noise = float(noise)

    def step_simulation(self) -> Dict[str, float]:
        """
        Applies a small Gaussian drift to simulate realistic sensor fluctuation.
        """
        if self.is_auto_simulating:
            self.temperature = max(10.0, min(55.0, self.temperature + random.uniform(-0.3, 0.3)))
            self.humidity = max(10.0, min(95.0, self.humidity + random.uniform(-0.5, 0.5)))
            self.dust = max(5.0, min(350.0, self.dust + random.uniform(-2.5, 2.5)))
            self.gas = max(1.0, min(120.0, self.gas + random.uniform(-1.0, 1.0)))
            self.noise = max(50.0, min(120.0, self.noise + random.uniform(-1.2, 1.2)))

        return self.read_current_values()

    def read_current_values(self) -> Dict[str, float]:
        return {
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
            "dust": round(self.dust, 1),
            "gas": round(self.gas, 1),
            "noise": round(self.noise, 1)
        }

    def evaluate_status(self) -> str:
        """Determines if any sensor reading violates warning or critical thresholds."""
        t = self.thresholds
        if (
            self.temperature >= t.temp_crit or
            self.dust >= t.dust_crit or
            self.gas >= t.gas_crit or
            self.noise >= t.noise_crit
        ):
            return "Critical"
        elif (
            self.temperature >= t.temp_warn or
            self.dust >= t.dust_warn or
            self.gas >= t.gas_warn or
            self.noise >= t.noise_warn
        ):
            return "Warning"
        return "Normal"

    def check_and_emit_alerts(self, site_zone: str = "Zone 2 - Environmental Station") -> List[str]:
        """
        Evaluates thresholds against current readings and emits safety events if thresholds are exceeded.
        Returns list of triggered alert descriptions.
        """
        engine = get_event_engine()
        t = self.thresholds
        alerts = []
        now_iso = datetime.now().isoformat()

        # Check Gas (Highest severity)
        if self.gas >= t.gas_crit:
            msg = f"SIMULATED: Critical gas reading detected ({self.gas:.1f} ppm >= {t.gas_crit} ppm critical limit)."
            engine.emit_event(
                event_type="IOT_GAS_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.99,
                context={"gas_value": self.gas}
            )
            alerts.append(msg)
        elif self.gas >= t.gas_warn:
            msg = f"SIMULATED: Elevated gas warning detected ({self.gas:.1f} ppm >= {t.gas_warn} ppm warning limit)."
            engine.emit_event(
                event_type="IOT_GAS_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.95,
                context={"gas_value": self.gas}
            )
            alerts.append(msg)

        # Check Dust (PM2.5/PM10)
        if self.dust >= t.dust_crit:
            msg = f"SIMULATED: Critical airborne particulate matter ({self.dust:.1f} µg/m³ >= {t.dust_crit} µg/m³ limit)."
            engine.emit_event(
                event_type="IOT_DUST_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.97,
                context={"dust_value": self.dust}
            )
            alerts.append(msg)
        elif self.dust >= t.dust_warn:
            msg = f"SIMULATED: Elevated dust concentration ({self.dust:.1f} µg/m³ >= {t.dust_warn} µg/m³ limit)."
            engine.emit_event(
                event_type="IOT_DUST_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.93,
                context={"dust_value": self.dust}
            )
            alerts.append(msg)

        # Check Noise
        if self.noise >= t.noise_crit:
            msg = f"SIMULATED: Excessive noise level detected ({self.noise:.1f} dBA >= {t.noise_crit} dBA maximum threshold)."
            engine.emit_event(
                event_type="IOT_NOISE_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.98,
                context={"noise_value": self.noise}
            )
            alerts.append(msg)
        elif self.noise >= t.noise_warn:
            msg = f"SIMULATED: Noise over permissible action level ({self.noise:.1f} dBA >= {t.noise_warn} dBA)."
            engine.emit_event(
                event_type="IOT_NOISE_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.94,
                context={"noise_value": self.noise}
            )
            alerts.append(msg)

        # Check Temperature
        if self.temperature >= t.temp_crit:
            msg = f"SIMULATED: High thermal heat stress condition ({self.temperature:.1f} °C >= {t.temp_crit} °C)."
            engine.emit_event(
                event_type="IOT_TEMP_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.99,
                context={"temp_value": self.temperature}
            )
            alerts.append(msg)
        elif self.temperature >= t.temp_warn:
            msg = f"SIMULATED: Elevated temperature threshold reached ({self.temperature:.1f} °C >= {t.temp_warn} °C)."
            engine.emit_event(
                event_type="IOT_TEMP_ALERT",
                source="IOT_SENSOR",
                site_zone=site_zone,
                description=msg,
                confidence=0.92,
                context={"temp_value": self.temperature}
            )
            alerts.append(msg)

        # Record sensor reading in SQLite
        status = self.evaluate_status()
        reading = SensorReading(
            timestamp=now_iso,
            temperature=round(self.temperature, 1),
            humidity=round(self.humidity, 1),
            dust=round(self.dust, 1),
            gas=round(self.gas, 1),
            noise=round(self.noise, 1),
            status=status
        )
        insert_sensor_reading(reading)

        return alerts

# Singleton sensor instance
_global_sensor_gateway: Optional[SimulatedSensorGateway] = None

def get_sensor_gateway() -> SimulatedSensorGateway:
    global _global_sensor_gateway
    if _global_sensor_gateway is None:
        _global_sensor_gateway = SimulatedSensorGateway()
    return _global_sensor_gateway
