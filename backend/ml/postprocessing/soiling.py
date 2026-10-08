"""
Dynamic soiling loss estimator based on precipitation proxy and dry-spell accumulation.
"""

from typing import Dict, Tuple, Union
import numpy as np
import pandas as pd


def calculate_dynamic_soiling(
    timestamps: pd.DatetimeIndex,
    precipitation_mm: Union[pd.Series, np.ndarray],
    soiling_rate_per_day: float = 0.002,      # 0.2% efficiency loss / day dry period
    rain_wash_threshold_mm: float = 3.0,     # Rain required for partial wash
    full_wash_threshold_mm: float = 12.0,    # Rain required for complete wash
    max_soiling_loss: float = 0.25,          # Maximum capped soiling loss (25%)
    initial_soiling_loss: float = 0.0
) -> pd.Series:
    """
    Simulates cumulative panel soiling loss percentage across a time series.

    Dust and particulate matter accumulate linearly during dry periods.
    Rain events trigger partial or complete surface cleansing.

    Parameters
    ----------
    timestamps : pd.DatetimeIndex
        Time index of the series.
    precipitation_mm : Union[pd.Series, np.ndarray]
        Rainfall in mm corresponding to each timestep.
    soiling_rate_per_day : float
        Fractional efficiency loss per dry day (e.g. 0.002 = 0.2%/day).
    rain_wash_threshold_mm : float
        Minimum rainfall required to trigger partial cleaning.
    full_wash_threshold_mm : float
        Rainfall required for complete 100% wash restoration.
    max_soiling_loss : float
        Upper bound on cumulative soiling degradation.
    initial_soiling_loss : float
        Starting soiling loss fraction at t=0.

    Returns
    -------
    pd.Series
        Fractional soiling loss factor (0.0 to 1.0) for each timestep.
    """
    precip_arr = np.asarray(precipitation_mm, dtype=np.float64)
    n = len(timestamps)
    soiling_factors = np.zeros(n, dtype=np.float64)
    current_soiling = float(initial_soiling_loss)

    # Calculate step size in fractional days
    for i in range(n):
        if i > 0:
            dt_seconds = (timestamps[i] - timestamps[i - 1]).total_seconds()
            dt_days = max(dt_seconds / 86400.0, 0.0)
        else:
            dt_days = 0.0

        rain = max(float(precip_arr[i]), 0.0)

        if rain >= full_wash_threshold_mm:
            # Full wash cleans the panel completely
            current_soiling = 0.0
        elif rain >= rain_wash_threshold_mm:
            # Partial wash recovery proportional to rain depth
            recovery_fraction = (rain - rain_wash_threshold_mm) / (
                full_wash_threshold_mm - rain_wash_threshold_mm
            )
            recovery_fraction = np.clip(recovery_fraction, 0.0, 1.0)
            current_soiling *= (1.0 - recovery_fraction)
        else:
            # Dry period or insignificant rain: accumulate dust
            current_soiling += soiling_rate_per_day * dt_days

        # Cap at maximum allowable soiling loss
        current_soiling = float(np.clip(current_soiling, 0.0, max_soiling_loss))
        soiling_factors[i] = current_soiling

    return pd.Series(soiling_factors, index=timestamps, name="soiling_loss_factor")


def apply_soiling_loss(
    clipped_power_kw: Union[float, np.ndarray, pd.Series],
    soiling_loss_factor: Union[float, np.ndarray, pd.Series]
) -> Union[float, np.ndarray, pd.Series]:
    """
    Deducts dynamic soiling loss from clipped AC power to yield deliverable generation.

    deliverable_kw = clipped_kw * (1.0 - soiling_loss_factor)

    Parameters
    ----------
    clipped_power_kw : Union[float, np.ndarray, pd.Series]
        Inverter-capped generation (kW).
    soiling_loss_factor : Union[float, np.ndarray, pd.Series]
        Fractional soiling loss factor (e.g. 0.03 for 3% loss).

    Returns
    -------
    Union[float, np.ndarray, pd.Series]
        Final deliverable AC power after soiling derate.
    """
    clean_fraction = 1.0 - np.clip(soiling_loss_factor, 0.0, 1.0)
    deliverable = clipped_power_kw * clean_fraction

    if isinstance(deliverable, (pd.Series, pd.DataFrame)):
        return deliverable.clip(lower=0.0)
    elif isinstance(deliverable, np.ndarray):
        return np.maximum(deliverable, 0.0)
    else:
        return max(float(deliverable), 0.0)


def calculate_soiling_metrics(
    clipped_power_kw: Union[np.ndarray, pd.Series],
    deliverable_power_kw: Union[np.ndarray, pd.Series],
    timestep_hours: float = 1.0
) -> Dict[str, float]:
    """
    Computes diagnostic metrics for soiling losses.
    """
    clipped_arr = np.asarray(clipped_power_kw, dtype=np.float64)
    deliv_arr = np.asarray(deliverable_power_kw, dtype=np.float64)
    loss_arr = np.maximum(clipped_arr - deliv_arr, 0.0)

    total_clipped_kwh = float(np.sum(clipped_arr) * timestep_hours)
    total_deliv_kwh = float(np.sum(deliv_arr) * timestep_hours)
    total_soiling_loss_kwh = float(np.sum(loss_arr) * timestep_hours)
    loss_pct = (
        (total_soiling_loss_kwh / total_clipped_kwh * 100.0)
        if total_clipped_kwh > 0
        else 0.0
    )

    return {
        "total_clipped_kwh": total_clipped_kwh,
        "deliverable_kwh": total_deliv_kwh,
        "soiling_loss_kwh": total_soiling_loss_kwh,
        "soiling_loss_pct": loss_pct,
    }
