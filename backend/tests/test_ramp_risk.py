"""
backend/tests/test_ramp_risk.py

Unit tests for ramp rate calculation, cloud-passage detection,
and BESS reserve risk metrics.
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.postprocessing.ramp_risk import (
    RampDirection,
    RampRiskLevel,
    classify_ramp_risk,
    calculate_bess_reserve_recommendation,
    compute_ramp_risk_profile,
)


def test_classify_ramp_risk_levels():
    """Verify classification thresholds for low, medium, high, and critical ramp risks."""
    # Low risk: small ramp, low uncertainty
    assert classify_ramp_risk(0.2, 10.0, 0.1, is_downward=False) == RampRiskLevel.LOW

    # Medium risk: moderate ramp or elevated uncertainty
    assert classify_ramp_risk(1.2, 20.0, 0.2, is_downward=False) == RampRiskLevel.MEDIUM
    assert classify_ramp_risk(0.4, 30.0, 0.1, is_downward=False) == RampRiskLevel.MEDIUM

    # High risk: steep ramp rate or high cloud impact
    assert classify_ramp_risk(2.8, 30.0, 0.3, is_downward=False) == RampRiskLevel.HIGH
    assert classify_ramp_risk(1.8, 45.0, 0.4, is_downward=False) == RampRiskLevel.HIGH

    # Critical risk: extreme ramp rate (e.g. > 5%/min) or rapid downward cloud drop
    assert classify_ramp_risk(5.5, 50.0, 0.5, is_downward=False) == RampRiskLevel.CRITICAL

    # Downward ramp penalty: 4.2% downward with cloud > 0.6 qualifies for CRITICAL
    assert classify_ramp_risk(4.0, 30.0, 0.7, is_downward=True) == RampRiskLevel.CRITICAL


def test_calculate_bess_reserve_recommendation():
    """Verify BESS sizing and advisory strings for up, down, and stable profiles."""
    capacity_kw = 1000.0

    # Downward ramp (sudden cloud shading) -> discharge reserve
    bess_down, action_down = calculate_bess_reserve_recommendation(
        capacity_kw=capacity_kw,
        ramp_rate_kw_per_min=-25.0,  # 375 kW drop in 15 min
        ramp_direction=RampDirection.DOWN,
        uncertainty_band_kw=100.0,
        interval_minutes=15.0,
    )
    assert bess_down > 300.0
    assert "discharge" in action_down.lower()

    # Upward ramp (cloud clearing) -> absorption reserve
    bess_up, action_up = calculate_bess_reserve_recommendation(
        capacity_kw=capacity_kw,
        ramp_rate_kw_per_min=20.0,
        ramp_direction=RampDirection.UP,
        uncertainty_band_kw=80.0,
        interval_minutes=15.0,
    )
    assert bess_up > 200.0
    assert "charge" in action_up.lower() or "absorption" in action_up.lower()

    # Stable profile -> minimal baseline buffer
    bess_stable, action_stable = calculate_bess_reserve_recommendation(
        capacity_kw=capacity_kw,
        ramp_rate_kw_per_min=0.1,
        ramp_direction=RampDirection.STABLE,
        uncertainty_band_kw=20.0,
        interval_minutes=15.0,
    )
    assert bess_stable <= 50.0
    assert "quiescent" in action_stable.lower() or "standard" in action_stable.lower()


def test_compute_ramp_risk_profile_synthetic_cloud_passage():
    """Verify ramp analysis over a synthetic cloud passage time series."""
    times = pd.date_range("2025-06-15 11:00:00", periods=5, freq="15min", tz="UTC")
    capacity_kw = 1000.0

    # Simulate sunny -> sudden cloud drop -> partial recovery
    df = pd.DataFrame({
        "forecast_time": times.astype(str),
        "p10": [700.0, 200.0, 150.0, 500.0, 650.0],
        "p50": [800.0, 300.0, 250.0, 600.0, 750.0],
        "p90": [900.0, 450.0, 400.0, 700.0, 850.0],
        "cloud_cover": [10.0, 85.0, 90.0, 35.0, 15.0],
    }, index=times)

    points, summary = compute_ramp_risk_profile(df, capacity_kw=capacity_kw, interval_minutes=15.0)

    assert len(points) == 5

    # Check first step (step 0: delta = 0)
    assert points[0].ramp_direction == RampDirection.STABLE
    assert points[0].ramp_rate_kw_per_min == 0.0

    # Step 1: drop from 800 to 300 kW over 15 min (-500 kW / 15 min = -33.33 kW/min)
    assert points[1].ramp_direction == RampDirection.DOWN
    assert points[1].ramp_rate_kw_per_min < -30.0
    assert points[1].ramp_risk_level in [RampRiskLevel.HIGH, RampRiskLevel.CRITICAL]

    # Step 3: rise from 250 to 600 kW (+350 kW / 15 min = +23.33 kW/min)
    assert points[3].ramp_direction == RampDirection.UP
    assert points[3].ramp_rate_kw_per_min > 20.0

    # Summary checks
    assert summary.max_ramp_rate_kw_per_min > 30.0
    assert summary.max_ramp_down_kw_per_min > 30.0
    assert summary.max_ramp_up_kw_per_min > 20.0
    assert summary.ramp_risk_score > 30.0
    assert summary.highest_risk_level in [RampRiskLevel.HIGH, RampRiskLevel.CRITICAL]
    assert summary.recommended_bess_capacity_kw > 200.0
    assert "advisory" in summary.__dict__["primary_action_advisory"].lower() or len(summary.primary_action_advisory) > 0


def test_compute_ramp_risk_empty_dataframe():
    """Verify error raised on empty inputs."""
    with pytest.raises(ValueError):
        compute_ramp_risk_profile(pd.DataFrame(), capacity_kw=1000.0)
