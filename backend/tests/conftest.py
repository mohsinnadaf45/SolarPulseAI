"""
Pytest configuration and shared fixtures for SolarPulse ML unit tests.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# Ensure repository root and backend directory are on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

for path in [str(REPO_ROOT), str(BACKEND_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.ml.config import PlantConfig


@pytest.fixture
def sample_plant_config() -> PlantConfig:
    """Standard test solar plant configuration."""
    return PlantConfig(
        plant_id="test_plant_01",
        name="Test Solar Array",
        latitude=28.6139,
        longitude=77.2090,
        altitude=216.0,
        tilt_deg=25.0,
        azimuth_deg=180.0,
        capacity_dc_kw=1000.0,
        ac_export_limit_kw=800.0,
        soiling_rate_per_day=0.002,
        rain_wash_threshold_mm=3.0,
        full_wash_threshold_mm=12.0,
        max_soiling_loss=0.25,
    )


@pytest.fixture
def sample_weather_df() -> pd.DataFrame:
    """48 hours of synthetic weather time-series data."""
    times = pd.date_range("2024-06-01 00:00:00", periods=48, freq="1h", tz="UTC")
    hours = times.hour.values
    daylight = (hours >= 6) & (hours <= 18)

    # Realistic solar diurnal curve
    ghi = np.zeros(len(times))
    ghi[daylight] = 850.0 * np.sin(np.pi * (hours[daylight] - 6) / 12.0)
    dni = np.where(ghi > 50, ghi * 1.1, 0.0)
    dhi = np.where(ghi > 50, ghi * 0.25, 0.0)

    return pd.DataFrame({
        "ghi_nwp": ghi,
        "dni_nwp": dni,
        "dhi_nwp": dhi,
        "temp_ambient_nwp": 22.0 + 10.0 * (ghi / 850.0),
        "wind_speed_nwp": np.full(48, 2.5),
        "cloud_cover_pct": np.full(48, 15.0),
    }, index=times)


@pytest.fixture
def sample_scada_history(sample_weather_df: pd.DataFrame) -> pd.Series:
    """Matching synthetic SCADA historical active power."""
    ghi = sample_weather_df["ghi_nwp"].values
    power = (ghi / 1000.0) * 1000.0 * 0.85
    return pd.Series(power, index=sample_weather_df.index, name="active_power_kw")
