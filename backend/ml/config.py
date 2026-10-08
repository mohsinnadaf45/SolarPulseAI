"""
SolarPulse AI - Machine Learning & Physics Pipeline Configuration.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PlantConfig:
    """Configuration metadata for a solar power plant."""
    plant_id: str
    name: str = "Solar Plant"
    latitude: float = 28.6139      # Default example: New Delhi
    longitude: float = 77.2090
    altitude: float = 216.0        # Meters above sea level
    tilt_deg: float = 28.0         # Module tilt angle in degrees
    azimuth_deg: float = 180.0     # 180 = South-facing in Northern hemisphere
    capacity_dc_kw: float = 1000.0 # Installed DC capacity (kW)
    ac_export_limit_kw: float = 850.0 # Inverter AC export ceiling (kW)
    soiling_rate_per_day: float = 0.002  # 0.2% efficiency loss per day without rain
    rain_wash_threshold_mm: float = 3.0  # Precipitation threshold (mm) for partial wash
    full_wash_threshold_mm: float = 10.0 # Precipitation threshold (mm) for full wash
    max_soiling_loss: float = 0.25       # Maximum cumulative soiling loss cap (25%)
    tracking: str = "fixed"              # "fixed", "single_axis"
