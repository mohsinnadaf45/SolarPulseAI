"""
Inverter clipping module. Caps gross DC generation at the plant AC export capacity.
"""

from typing import Dict, Tuple, Union
import numpy as np
import pandas as pd


def apply_clipping(
    gross_power_kw: Union[float, np.ndarray, pd.Series],
    ac_export_limit_kw: float
) -> Union[float, np.ndarray, pd.Series]:
    """
    Applies AC inverter export ceiling.

    Parameters
    ----------
    gross_power_kw : Union[float, np.ndarray, pd.Series]
        Gross DC generation estimate (kW).
    ac_export_limit_kw : float
        Plant AC inverter limit / grid interconnect ceiling (kW).

    Returns
    -------
    Union[float, np.ndarray, pd.Series]
        Exportable power capped at ac_export_limit_kw.
    """
    if ac_export_limit_kw <= 0:
        raise ValueError("ac_export_limit_kw must be positive.")

    if isinstance(gross_power_kw, (pd.Series, pd.DataFrame)):
        return gross_power_kw.clip(upper=ac_export_limit_kw)
    elif isinstance(gross_power_kw, np.ndarray):
        return np.minimum(gross_power_kw, ac_export_limit_kw)
    elif isinstance(gross_power_kw, (int, float)):
        return min(float(gross_power_kw), float(ac_export_limit_kw))
    else:
        raise TypeError(f"Unsupported type for gross_power_kw: {type(gross_power_kw)}")


def calculate_clipping_metrics(
    gross_power_kw: Union[np.ndarray, pd.Series],
    ac_export_limit_kw: float,
    timestep_hours: float = 1.0
) -> Dict[str, float]:
    """
    Computes diagnostic metrics for inverter clipping.

    Returns
    -------
    Dict[str, float]
        Dictionary with:
          - 'total_gross_kwh': Total potential gross energy
          - 'total_clipped_export_kwh': Total delivered AC energy after cap
          - 'clipping_loss_kwh': Energy discarded due to inverter sizing
          - 'clipping_loss_pct': Percentage of gross generation clipped
          - 'hours_clipped': Total hours where generation exceeded inverter cap
    """
    gross_arr = np.asarray(gross_power_kw, dtype=np.float64)
    clipped_arr = np.minimum(gross_arr, ac_export_limit_kw)
    loss_arr = np.maximum(gross_arr - ac_export_limit_kw, 0.0)

    total_gross = float(np.sum(gross_arr) * timestep_hours)
    total_clipped = float(np.sum(clipped_arr) * timestep_hours)
    total_loss = float(np.sum(loss_arr) * timestep_hours)
    loss_pct = (total_loss / total_gross * 100.0) if total_gross > 0 else 0.0
    hours_clipped = float(np.sum(gross_arr > ac_export_limit_kw) * timestep_hours)

    return {
        "total_gross_kwh": total_gross,
        "total_clipped_export_kwh": total_clipped,
        "clipping_loss_kwh": total_loss,
        "clipping_loss_pct": loss_pct,
        "hours_clipped": hours_clipped,
    }
