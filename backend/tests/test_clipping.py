"""
Unit tests for inverter clipping post-processing logic and metrics.
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.postprocessing.clipping import (
    apply_clipping,
    calculate_clipping_metrics,
)


def test_apply_clipping_scalar():
    """Tests capping on scalar values."""
    assert apply_clipping(500.0, 800.0) == 500.0
    assert apply_clipping(950.0, 800.0) == 800.0


def test_apply_clipping_array():
    """Tests capping on numpy array."""
    gross = np.array([0.0, 300.0, 800.0, 950.0, 1100.0])
    limit = 800.0
    clipped = apply_clipping(gross, limit)

    expected = np.array([0.0, 300.0, 800.0, 800.0, 800.0])
    assert np.allclose(clipped, expected)


def test_clipping_metrics():
    """Tests clipping loss metrics calculations."""
    gross = np.array([600.0, 1000.0])  # total gross = 1600 kWh
    limit = 800.0                       # clipped: 600, 800 = 1400 kWh, loss = 200 kWh
    metrics = calculate_clipping_metrics(gross, limit, timestep_hours=1.0)

    assert metrics["total_gross_kwh"] == 1600.0
    assert metrics["total_clipped_export_kwh"] == 1400.0
    assert metrics["clipping_loss_kwh"] == 200.0
    assert pytest.approx(metrics["clipping_loss_pct"], 0.01) == 12.5
    assert metrics["hours_clipped"] == 1.0
