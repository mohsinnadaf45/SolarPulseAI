"""
Unit tests for pvlib physical feature extraction.
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.config import PlantConfig
from backend.ml.features.pvlib_features import compute_pvlib_features


def test_compute_pvlib_features_columns(sample_weather_df: pd.DataFrame, sample_plant_config: PlantConfig):
    """Verifies that all required physics columns are generated."""
    features = compute_pvlib_features(sample_weather_df, sample_plant_config)

    expected_cols = [
        "solar_zenith",
        "solar_azimuth",
        "solar_elevation",
        "airmass_relative",
        "clearsky_ghi",
        "clearsky_dni",
        "clearsky_dhi",
        "poa_global",
        "poa_direct",
        "poa_diffuse",
        "cell_temp",
        "clearsky_index",
    ]
    for col in expected_cols:
        assert col in features.columns, f"Missing feature column: {col}"
    assert len(features) == len(sample_weather_df)


def test_pvlib_physical_bounds(sample_weather_df: pd.DataFrame, sample_plant_config: PlantConfig):
    """Verifies physical invariants (non-negative irradiance, valid angles)."""
    features = compute_pvlib_features(sample_weather_df, sample_plant_config)

    # Zenith between 0 and 180 degrees
    assert np.all(features["solar_zenith"] >= 0.0)
    assert np.all(features["solar_zenith"] <= 180.0)

    # Elevation = 90 - Zenith
    assert np.allclose(features["solar_elevation"] + features["solar_zenith"], 90.0, atol=1e-3)

    # Irradiance non-negative
    assert np.all(features["poa_global"] >= 0.0)
    assert np.all(features["clearsky_ghi"] >= 0.0)

    # Nighttime POA should be 0
    night_idx = features["solar_elevation"] <= 0
    if np.any(night_idx):
        assert np.all(features.loc[night_idx, "poa_global"] == 0.0)


def test_invalid_index_raises():
    """Verifies that an error is raised if index is not DatetimeIndex."""
    bad_df = pd.DataFrame({"ghi_nwp": [100, 200]})
    plant = PlantConfig(plant_id="p1")
    with pytest.raises(ValueError, match="DatetimeIndex"):
        compute_pvlib_features(bad_df, plant)
