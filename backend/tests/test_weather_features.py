"""
Unit tests for weather feature extraction and cyclical time encoding.
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.features.weather_features import compute_weather_features


def test_compute_weather_features(sample_weather_df: pd.DataFrame, sample_scada_history: pd.Series):
    """Verifies weather and lag features calculation."""
    features = compute_weather_features(sample_weather_df, scada_history=sample_scada_history)

    assert "hour_of_day" in features.columns
    assert "day_of_year" in features.columns
    assert "sin_hour" in features.columns
    assert "cos_hour" in features.columns
    assert "sin_doy" in features.columns
    assert "cos_doy" in features.columns
    assert "lag_power_1h" in features.columns
    assert "lag_power_2h" in features.columns
    assert "lag_power_24h" in features.columns

    # Cyclical bounds check: sin^2 + cos^2 == 1
    trig_identity = features["sin_hour"] ** 2 + features["cos_hour"] ** 2
    assert np.allclose(trig_identity, 1.0, atol=1e-5)


def test_weather_features_without_scada(sample_weather_df: pd.DataFrame):
    """Verifies fallback to zero lags when no prior SCADA history is provided."""
    features = compute_weather_features(sample_weather_df, scada_history=None)
    assert np.all(features["lag_power_1h"] == 0.0)
    assert np.all(features["lag_power_2h"] == 0.0)
    assert np.all(features["lag_power_24h"] == 0.0)
