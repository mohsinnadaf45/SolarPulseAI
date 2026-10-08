"""
Evaluation metrics and diagnostic reporting for solar generation forecasting.
Computes MAPE, RMSE, normalized RMSE (nRMSE), MAE, and Mean Bias Error (MBE).
"""

from typing import Any, Dict, Optional, Union
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def mean_bias_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Computes Mean Bias Error (MBE).
    Positive indicates average over-prediction; negative indicates under-prediction.
    """
    return float(np.mean(y_pred - y_true))


def masked_mape(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    min_threshold_kw: float = 10.0
) -> float:
    """
    Computes Mean Absolute Percentage Error (MAPE) masked by a minimum generation threshold.
    Crucial for solar energy to avoid dividing by 0 or micro-values during dawn/dusk/night.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth generation.
    y_pred : np.ndarray
        Predicted generation.
    min_threshold_kw : float
        Generation cutoff below which timesteps are excluded from MAPE calculation.
    """
    mask = y_true >= min_threshold_kw
    if not np.any(mask):
        return 0.0
    abs_pct_errors = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])
    return float(np.mean(abs_pct_errors) * 100.0)


def normalized_rmse(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    capacity_kw: Optional[float] = None
) -> float:
    """
    Computes Normalized Root Mean Squared Error (nRMSE).
    Normalized by plant DC/AC capacity if provided, or by mean true generation.
    """
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    normalizer = capacity_kw if (capacity_kw and capacity_kw > 0) else np.mean(y_true)
    if normalizer == 0:
        return 0.0
    return float((rmse / normalizer) * 100.0)


def evaluate_forecast(
    y_true: Union[pd.Series, np.ndarray],
    y_pred: Union[pd.Series, np.ndarray],
    capacity_kw: Optional[float] = None,
    daylight_only: bool = True
) -> Dict[str, float]:
    """
    Generates a full operational evaluation report comparing forecast with ground truth.

    Parameters
    ----------
    y_true : Union[pd.Series, np.ndarray]
        Actual observed power (kW).
    y_pred : Union[pd.Series, np.ndarray]
        Forecasted power (kW).
    capacity_kw : Optional[float]
        Rated capacity of the facility for nRMSE normalization.
    daylight_only : bool
        If True, also reports metrics filtered to timesteps where y_true > 1 kW.

    Returns
    -------
    Dict[str, float]
        Dictionary with all core solar forecasting metrics.
    """
    y_t = np.asarray(y_true, dtype=np.float64)
    y_p = np.asarray(y_pred, dtype=np.float64)

    if len(y_t) != len(y_p):
        raise ValueError(f"Length mismatch: y_true ({len(y_t)}) vs y_pred ({len(y_p)})")

    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    mae = float(mean_absolute_error(y_t, y_p))
    mbe = float(mean_bias_error(y_t, y_p))
    r2 = float(r2_score(y_t, y_p))
    nrmse = normalized_rmse(y_t, y_p, capacity_kw=capacity_kw)
    mape = masked_mape(y_t, y_p, min_threshold_kw=10.0)

    report = {
        "sample_count": len(y_t),
        "rmse_kw": round(rmse, 3),
        "mae_kw": round(mae, 3),
        "mbe_kw": round(mbe, 3),
        "r2_score": round(r2, 4),
        "nrmse_pct": round(nrmse, 2),
        "mape_pct": round(mape, 2),
    }

    if daylight_only:
        day_mask = y_t > 5.0
        if np.any(day_mask):
            day_t = y_t[day_mask]
            day_p = y_p[day_mask]
            report["daylight_samples"] = int(np.sum(day_mask))
            report["daylight_rmse_kw"] = round(float(np.sqrt(mean_squared_error(day_t, day_p))), 3)
            report["daylight_mae_kw"] = round(float(mean_absolute_error(day_t, day_p)), 3)
            report["daylight_mape_pct"] = round(masked_mape(day_t, day_p, min_threshold_kw=10.0), 2)

    return report
