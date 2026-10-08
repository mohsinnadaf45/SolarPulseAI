"""
Meteorological feature normalization, cyclical time encodings, and SCADA lag features.
"""

from typing import Optional, Union
import numpy as np
import pandas as pd


def compute_weather_features(
    df: pd.DataFrame,
    scada_history: Optional[Union[pd.DataFrame, pd.Series]] = None
) -> pd.DataFrame:
    """
    Computes temporal cyclical encodings, normalized weather features,
    and historical SCADA lag features.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame indexed by DatetimeIndex containing weather forecast data:
          - 'ghi_nwp' (Global Horizontal Irradiance, W/m^2)
          - 'dni_nwp' (Direct Normal Irradiance, W/m^2)
          - 'dhi_nwp' (Diffuse Horizontal Irradiance, W/m^2)
          - 'temp_ambient_nwp' (Ambient Temperature, °C)
          - 'wind_speed_nwp' (Wind Speed, m/s)
          - 'cloud_cover_pct' (Total Cloud Cover, 0 - 100%)
    scada_history : Optional[Union[pd.DataFrame, pd.Series]]
        Historical SCADA telemetry for computing autoregressive lag features
        (1h, 2h, 24h). If not provided or missing, lags are filled with forward/backward
        values or zeroes.

    Returns
    -------
    pd.DataFrame
        DataFrame containing normalized weather and cyclical temporal features.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a pandas DatetimeIndex.")

    times = df.index
    result = pd.DataFrame(index=times)

    # 1. Cyclical Time Features
    hour_of_day = times.hour + times.minute / 60.0
    day_of_year = times.dayofyear

    result["hour_of_day"] = hour_of_day
    result["day_of_year"] = day_of_year
    result["sin_hour"] = np.sin(2.0 * np.pi * hour_of_day / 24.0)
    result["cos_hour"] = np.cos(2.0 * np.pi * hour_of_day / 24.0)
    result["sin_doy"] = np.sin(2.0 * np.pi * day_of_year / 365.25)
    result["cos_doy"] = np.cos(2.0 * np.pi * day_of_year / 365.25)

    # 2. Weather Variables Normalization & Bounds Check
    result["ghi_nwp"] = df.get("ghi_nwp", df.get("ghi", 0.0)).fillna(0.0).clip(lower=0.0)
    result["dni_nwp"] = df.get("dni_nwp", df.get("dni", 0.0)).fillna(0.0).clip(lower=0.0)
    result["dhi_nwp"] = df.get("dhi_nwp", df.get("dhi", 0.0)).fillna(0.0).clip(lower=0.0)
    result["temp_ambient_nwp"] = df.get("temp_ambient_nwp", df.get("temp_air", 25.0)).fillna(25.0)
    result["wind_speed_nwp"] = df.get("wind_speed_nwp", df.get("wind_speed", 1.5)).fillna(1.5).clip(lower=0.0)
    result["cloud_cover_pct"] = df.get("cloud_cover_pct", 0.0).fillna(0.0).clip(lower=0.0, upper=100.0)

    # 3. Autoregressive SCADA Lag Features
    power_series = None
    if scada_history is not None:
        if isinstance(scada_history, pd.DataFrame):
            # Try finding power column
            for col in ["active_power_kw", "power_kw", "gross_dc_power_kw", "power"]:
                if col in scada_history.columns:
                    power_series = scada_history[col]
                    break
            if power_series is None and not scada_history.empty:
                power_series = scada_history.iloc[:, 0]
        elif isinstance(scada_history, pd.Series):
            power_series = scada_history

    if power_series is not None and not power_series.empty:
        # Align series to current index or reindex
        combined_idx = power_series.index.union(times).sort_values()
        full_power = power_series.reindex(combined_idx)

        # Assuming hourly or regular spacing, use time-based shift or index shift
        lag_1h = full_power.shift(1).reindex(times)
        lag_2h = full_power.shift(2).reindex(times)
        lag_24h = full_power.shift(24).reindex(times)

        result["lag_power_1h"] = lag_1h.fillna(0.0).clip(lower=0.0)
        result["lag_power_2h"] = lag_2h.fillna(0.0).clip(lower=0.0)
        result["lag_power_24h"] = lag_24h.fillna(0.0).clip(lower=0.0)
    else:
        # Default zero lags when no prior SCADA reading is attached
        result["lag_power_1h"] = 0.0
        result["lag_power_2h"] = 0.0
        result["lag_power_24h"] = 0.0

    return result
