"""
backend/ml/postprocessing/ramp_risk.py

Ramp rate analysis, cloud-passage detection, and probabilistic risk quantification
for solar PV plants and BESS (Battery Energy Storage System) reserve dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class RampDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class RampRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RampPointMetrics:
    """Ramp and risk metrics for a single forecast time step."""
    forecast_time: str
    p10_kw: float
    p50_kw: float
    p90_kw: float
    uncertainty_band_kw: float
    relative_uncertainty_pct: float
    ramp_rate_kw_per_min: float
    ramp_rate_pct_per_min: float
    ramp_direction: RampDirection
    ramp_risk_level: RampRiskLevel
    cloud_impact_factor: float
    bess_reserve_recommendation_kw: float
    reserve_action: str


@dataclass
class RampRiskSummary:
    """Aggregated risk overview across the entire forecast horizon."""
    max_ramp_rate_kw_per_min: float
    max_ramp_down_kw_per_min: float
    max_ramp_up_kw_per_min: float
    ramp_risk_score: float  # 0 to 100
    highest_risk_level: RampRiskLevel
    high_risk_event_count: int
    critical_risk_event_count: int
    avg_uncertainty_band_kw: float
    recommended_bess_capacity_kw: float
    primary_action_advisory: str


def classify_ramp_risk(
    abs_ramp_rate_pct_per_min: float,
    relative_uncertainty_pct: float,
    cloud_impact_factor: float,
    is_downward: bool,
) -> RampRiskLevel:
    """
    Classifies ramp severity based on rate of change relative to plant capacity,
    forecast uncertainty band, and cloud passage impact factor.
    Downside ramps have higher operational sensitivity for grid stability.
    """
    # Downward ramp penalty multiplier
    down_multiplier = 1.25 if is_downward else 1.0
    effective_rate = abs_ramp_rate_pct_per_min * down_multiplier

    if effective_rate >= 5.0 or (effective_rate >= 3.5 and cloud_impact_factor > 0.6):
        return RampRiskLevel.CRITICAL
    elif effective_rate >= 2.5 or (effective_rate >= 1.5 and relative_uncertainty_pct >= 40.0):
        return RampRiskLevel.HIGH
    elif effective_rate >= 1.0 or relative_uncertainty_pct >= 25.0 or cloud_impact_factor >= 0.35:
        return RampRiskLevel.MEDIUM
    else:
        return RampRiskLevel.LOW


def calculate_bess_reserve_recommendation(
    capacity_kw: float,
    ramp_rate_kw_per_min: float,
    ramp_direction: RampDirection,
    uncertainty_band_kw: float,
    interval_minutes: float,
) -> Tuple[float, str]:
    """
    Calculates battery energy storage system (BESS) or spinning reserve allocation
    and generates actionable dispatch recommendations.
    """
    if interval_minutes <= 0:
        interval_minutes = 15.0

    step_delta_kw = abs(ramp_rate_kw_per_min) * interval_minutes

    if ramp_direction == RampDirection.DOWN:
        # Need fast discharge headroom to buffer the solar drop
        required_headroom = min(capacity_kw, step_delta_kw + 0.35 * uncertainty_band_kw)
        if required_headroom > 0.3 * capacity_kw:
            action = f"Prep fast BESS discharge buffer ({required_headroom:.1f} kW) for steep cloud drop"
        elif required_headroom > 0.1 * capacity_kw:
            action = f"Maintain spinning reserve discharge ({required_headroom:.1f} kW)"
        else:
            action = "Nominal grid-following discharge buffer"
        return round(required_headroom, 2), action

    elif ramp_direction == RampDirection.UP:
        # Cloud clears rapidly; need charging absorption or curtailment headroom
        required_absorption = min(capacity_kw, step_delta_kw * 0.8)
        if required_absorption > 0.25 * capacity_kw:
            action = f"Reserve BESS charge headroom ({required_absorption:.1f} kW) to prevent over-frequency"
        else:
            action = "Stable absorption headroom available"
        return round(required_absorption, 2), action

    else:
        # Stable; modest buffer for uncertainty
        baseline = min(capacity_kw * 0.05, 0.2 * uncertainty_band_kw)
        return round(baseline, 2), "Quiescent profile - standard reserve margin"


def compute_ramp_risk_profile(
    df: pd.DataFrame,
    capacity_kw: float,
    interval_minutes: float = 15.0,
) -> Tuple[List[RampPointMetrics], RampRiskSummary]:
    """
    Processes time-series with 'p10', 'p50', 'p90' columns (and optional 'cloud_cover' / 'time').
    Returns point-by-point ramp metrics and aggregated risk summary.
    """
    if df.empty:
        raise ValueError("DataFrame for ramp risk profile calculation is empty.")

    p10 = df["p10"].to_numpy(dtype=float)
    p50 = df["p50"].to_numpy(dtype=float)
    p90 = df["p90"].to_numpy(dtype=float)
    n = len(df)

    # Cloud impact factor: derived from cloud_cover column if present, or quantile spread ratio
    if "cloud_cover" in df.columns:
        cloud_factor = np.clip(df["cloud_cover"].to_numpy(dtype=float) / 100.0, 0.0, 1.0)
    else:
        # Proxy from normalized quantile spread (P90 - P10) relative to maximum potential
        spread = np.clip(p90 - p10, 0.0, None)
        cloud_factor = np.clip(spread / max(capacity_kw * 0.7, 1.0), 0.0, 1.0)

    # Calculate ramp rate based on P50 deltas
    p50_deltas = np.zeros(n)
    if n > 1:
        p50_deltas[1:] = p50[1:] - p50[:-1]

    # Rates per minute
    ramp_rates_kw_min = p50_deltas / max(interval_minutes, 1.0)
    ramp_rates_pct_min = (ramp_rates_kw_min / max(capacity_kw, 1.0)) * 100.0

    point_metrics: List[RampPointMetrics] = []
    max_ramp_rate = 0.0
    max_ramp_down = 0.0
    max_ramp_up = 0.0
    high_count = 0
    critical_count = 0
    uncertainty_bands: List[float] = []
    bess_recommendations: List[float] = []

    # Get timestamps or string indices
    timestamps = [
        str(t) for t in (df.index if isinstance(df.index, pd.DatetimeIndex) else df.get("forecast_time", range(n)))
    ]

    for i in range(n):
        u_band = max(0.0, float(p90[i] - p10[i]))
        uncertainty_bands.append(u_band)

        rel_unc = (u_band / max(float(p50[i]), capacity_kw * 0.05, 1.0)) * 100.0
        rel_unc = min(rel_unc, 100.0)

        rate_kw = float(ramp_rates_kw_min[i])
        rate_pct = float(ramp_rates_pct_min[i])
        abs_rate_pct = abs(rate_pct)

        abs_rate_kw = abs(rate_kw)
        max_ramp_rate = max(max_ramp_rate, abs_rate_kw)
        if rate_kw < 0:
            max_ramp_down = max(max_ramp_down, abs_rate_kw)
        elif rate_kw > 0:
            max_ramp_up = max(max_ramp_up, rate_kw)

        # Determine direction
        if abs(rate_pct) < 0.3:
            direction = RampDirection.STABLE
        elif rate_kw > 0:
            direction = RampDirection.UP
        else:
            direction = RampDirection.DOWN

        risk_level = classify_ramp_risk(
            abs_ramp_rate_pct_per_min=abs_rate_pct,
            relative_uncertainty_pct=rel_unc,
            cloud_impact_factor=float(cloud_factor[i]),
            is_downward=(direction == RampDirection.DOWN),
        )

        if risk_level == RampRiskLevel.HIGH:
            high_count += 1
        elif risk_level == RampRiskLevel.CRITICAL:
            critical_count += 1

        bess_rec, action_desc = calculate_bess_reserve_recommendation(
            capacity_kw=capacity_kw,
            ramp_rate_kw_per_min=rate_kw,
            ramp_direction=direction,
            uncertainty_band_kw=u_band,
            interval_minutes=interval_minutes,
        )
        bess_recommendations.append(bess_rec)

        point_metrics.append(
            RampPointMetrics(
                forecast_time=timestamps[i],
                p10_kw=round(float(p10[i]), 2),
                p50_kw=round(float(p50[i]), 2),
                p90_kw=round(float(p90[i]), 2),
                uncertainty_band_kw=round(u_band, 2),
                relative_uncertainty_pct=round(rel_unc, 1),
                ramp_rate_kw_per_min=round(rate_kw, 3),
                ramp_rate_pct_per_min=round(rate_pct, 3),
                ramp_direction=direction,
                ramp_risk_level=risk_level,
                cloud_impact_factor=round(float(cloud_factor[i]), 3),
                bess_reserve_recommendation_kw=round(bess_rec, 2),
                reserve_action=action_desc,
            )
        )

    # Aggregate risk scoring
    # Risk score 0-100 derived from max ramp rate, critical events, and average uncertainty
    avg_band = float(np.mean(uncertainty_bands)) if uncertainty_bands else 0.0
    rec_bess_cap = float(np.max(bess_recommendations)) if bess_recommendations else 0.0

    score = min(
        100.0,
        (max_ramp_rate / max(capacity_kw * 0.05, 1.0)) * 35.0
        + critical_count * 20.0
        + high_count * 10.0
        + (avg_band / max(capacity_kw, 1.0)) * 25.0
    )
    score = round(max(0.0, score), 1)

    if critical_count > 0 or score >= 75.0:
        highest_level = RampRiskLevel.CRITICAL
        primary_advisory = (
            f"CRITICAL: Rapid cloud passage detected ({max_ramp_down:.1f} kW/min max drop). "
            f"Reserve {rec_bess_cap:.1f} kW BESS capacity immediately."
        )
    elif high_count > 0 or score >= 45.0:
        highest_level = RampRiskLevel.HIGH
        primary_advisory = (
            f"HIGH: Significant cloud-induced ramp variability. "
            f"Maintain {rec_bess_cap:.1f} kW operational reserve buffer."
        )
    elif score >= 20.0:
        highest_level = RampRiskLevel.MEDIUM
        primary_advisory = "MODERATE: Fleeting cloud cover transitions expected; standard spinning reserve."
    else:
        highest_level = RampRiskLevel.LOW
        primary_advisory = "NOMINAL: Stable irradiance profile with low ramp volatility."

    summary = RampRiskSummary(
        max_ramp_rate_kw_per_min=round(max_ramp_rate, 3),
        max_ramp_down_kw_per_min=round(max_ramp_down, 3),
        max_ramp_up_kw_per_min=round(max_ramp_up, 3),
        ramp_risk_score=score,
        highest_risk_level=highest_level,
        high_risk_event_count=high_count,
        critical_risk_event_count=critical_count,
        avg_uncertainty_band_kw=round(avg_band, 2),
        recommended_bess_capacity_kw=round(rec_bess_cap, 2),
        primary_action_advisory=primary_advisory,
    )

    return point_metrics, summary
