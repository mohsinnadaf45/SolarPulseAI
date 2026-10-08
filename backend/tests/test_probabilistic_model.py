"""
backend/tests/test_probabilistic_model.py

Unit tests for ProbabilisticForecaster quantile inference and monotonicity.
"""

from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from backend.ml.models.probabilistic_model import ProbabilisticForecaster


def test_probabilistic_forecaster_monotonicity_and_nighttime():
    """Verify p10 <= p50 <= p90 monotonicity and zero nighttime enforcement."""
    forecaster = ProbabilisticForecaster(zero_nighttime=True)
    forecaster.is_fitted = True
    forecaster.feature_names_ = ["poa_global", "temp"]

    # Mock inner models returning arbitrary/crossing values to test monotonicity correction
    mock_p10 = MagicMock()
    mock_p50 = MagicMock()
    mock_p90 = MagicMock()

    # Step 0: crossing (p10=500, p50=400, p90=300) -> monotonicity should enforce 500, 500, 500
    # Step 1: normal daytime (p10=200, p50=450, p90=600)
    # Step 2: nighttime (poa_global = 0) -> all should be 0.0
    mock_p10.predict.return_value = np.array([500.0, 200.0, 50.0])
    mock_p50.predict.return_value = np.array([400.0, 450.0, 100.0])
    mock_p90.predict.return_value = np.array([300.0, 600.0, 150.0])

    forecaster.models = {
        "p10": mock_p10,
        "p50": mock_p50,
        "p90": mock_p90,
    }

    X = pd.DataFrame({
        "poa_global": [800.0, 600.0, 0.0],
        "temp": [25.0, 28.0, 15.0],
    })

    quantiles = forecaster.predict_quantiles(X)

    # Monotonicity checks
    assert (quantiles["p10"] <= quantiles["p50"]).all()
    assert (quantiles["p50"] <= quantiles["p90"]).all()

    # Step 0 crossed quantiles resolved
    assert quantiles.loc[0, "p10"] == 500.0
    assert quantiles.loc[0, "p50"] == 500.0
    assert quantiles.loc[0, "p90"] == 500.0

    # Step 1 ordered correctly
    assert quantiles.loc[1, "p10"] == 200.0
    assert quantiles.loc[1, "p50"] == 450.0
    assert quantiles.loc[1, "p90"] == 600.0

    # Step 2 nighttime clamped to 0.0
    assert quantiles.loc[2, "p10"] == 0.0
    assert quantiles.loc[2, "p50"] == 0.0
    assert quantiles.loc[2, "p90"] == 0.0

    # Test default predict returns p50
    p50_vals = forecaster.predict(X)
    assert np.allclose(p50_vals, quantiles["p50"].values)
