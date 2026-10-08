"""
Unit tests for dynamic soiling accumulation and precipitation washing.
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.postprocessing.soiling import (
    calculate_dynamic_soiling,
    apply_soiling_loss,
    calculate_soiling_metrics,
)


def test_soiling_accumulation_dry_period():
    """Verifies that soiling loss factor accumulates during dry days."""
    times = pd.date_range("2024-01-01", periods=10, freq="1D")
    precip = np.zeros(10)  # Dry period
    rate = 0.005  # 0.5% per day

    soiling = calculate_dynamic_soiling(
        times, precip, soiling_rate_per_day=rate, initial_soiling_loss=0.0
    )

    # After 9 day steps, soiling should be ~ 9 * 0.005 = 0.045
    assert pytest.approx(soiling.iloc[-1], rel=1e-3) == 0.045
    # Non-decreasing throughout dry spell
    assert (np.diff(soiling.values) >= 0).all()


def test_soiling_full_wash():
    """Verifies complete cleansing when rain exceeds full_wash_threshold."""
    times = pd.date_range("2024-01-01", periods=3, freq="1D")
    precip = np.array([0.0, 15.0, 0.0])  # Day 2 has 15mm heavy rain (full wash)

    soiling = calculate_dynamic_soiling(
        times,
        precip,
        soiling_rate_per_day=0.01,
        full_wash_threshold_mm=10.0,
        initial_soiling_loss=0.05
    )

    assert soiling.iloc[1] == 0.0  # Fully cleaned on rain day


def test_apply_soiling_loss():
    """Verifies deliverable generation after deducting soiling loss."""
    clipped_power = 800.0
    soiling_factor = 0.05  # 5% soiling loss
    deliverable = apply_soiling_loss(clipped_power, soiling_factor)
    assert deliverable == 800.0 * 0.95


def test_soiling_metrics():
    """Verifies calculation of soiling energy loss metrics."""
    clipped = np.array([500.0, 500.0])
    deliverable = np.array([475.0, 475.0])  # 25 kW loss per hour
    metrics = calculate_soiling_metrics(clipped, deliverable, timestep_hours=1.0)

    assert metrics["total_clipped_kwh"] == 1000.0
    assert metrics["deliverable_kwh"] == 950.0
    assert metrics["soiling_loss_kwh"] == 50.0
    assert pytest.approx(metrics["soiling_loss_pct"], 0.01) == 5.0
