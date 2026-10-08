"""
End-to-end solar feature pipeline combining pvlib physics and meteorological encodings.
"""

from typing import List, Optional, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from backend.ml.config import PlantConfig
from backend.ml.features.pvlib_features import compute_pvlib_features
from backend.ml.features.weather_features import compute_weather_features


# Exact canonical feature column ordering specified in ARCHITECTURE.md
CANONICAL_FEATURE_COLUMNS: List[str] = [
    "poa_global",
    "cell_temp",
    "solar_zenith",
    "solar_azimuth",
    "airmass_relative",
    "clearsky_index",
    "ghi_nwp",
    "dni_nwp",
    "dhi_nwp",
    "temp_ambient_nwp",
    "wind_speed_nwp",
    "cloud_cover_pct",
    "hour_of_day",
    "day_of_year",
    "sin_hour",
    "cos_hour",
    "sin_doy",
    "cos_doy",
    "lag_power_1h",
    "lag_power_2h",
    "lag_power_24h",
]


class SolarFeaturePipeline(BaseEstimator, TransformerMixin):
    """
    Sklearn-compatible feature pipeline for solar PV forecasting.
    Orchestrates physical modeling via pvlib with meteorological normalization
    and temporal cyclical encoding.
    """

    def __init__(self, plant_config: Optional[PlantConfig] = None):
        self.plant_config = plant_config or PlantConfig(plant_id="default")
        self.feature_names: List[str] = CANONICAL_FEATURE_COLUMNS

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None):
        """Fit method (stateless transformer)."""
        return self

    def transform(
        self,
        X: pd.DataFrame,
        scada_history: Optional[Union[pd.DataFrame, pd.Series]] = None
    ) -> pd.DataFrame:
        """
        Transforms raw NWP weather inputs and plant parameters into model-ready
        physical + meteorological feature matrix.

        Parameters
        ----------
        X : pd.DataFrame
            Weather forecast dataframe indexed by DatetimeIndex.
        scada_history : Optional[Union[pd.DataFrame, pd.Series]]
            Historical SCADA records for computing lag features.

        Returns
        -------
        pd.DataFrame
            Matrix containing the 21 canonical features.
        """
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X must be a pandas DataFrame.")
        if not isinstance(X.index, pd.DatetimeIndex):
            raise ValueError("Input X must have a DatetimeIndex.")

        # 1. Compute pvlib physics features
        pvlib_df = compute_pvlib_features(X, self.plant_config)

        # 2. Compute meteorological and cyclical time features
        weather_df = compute_weather_features(X, scada_history=scada_history)

        # 3. Concatenate and align columns
        combined_df = pd.concat([pvlib_df, weather_df], axis=1)

        # Deduplicate overlapping column names if any
        combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]

        # Ensure all canonical columns exist
        for col in self.feature_names:
            if col not in combined_df.columns:
                combined_df[col] = 0.0

        # Return strictly in canonical order
        return combined_df[self.feature_names].astype(np.float64)

    def get_feature_names_out(self, input_features=None) -> List[str]:
        """Returns feature names list."""
        return list(self.feature_names)
