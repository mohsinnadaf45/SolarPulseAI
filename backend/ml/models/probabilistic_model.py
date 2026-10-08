"""
Probabilistic forecasting model using quantile regression (P10, P50, P90).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
import pandas as pd

from backend.ml.models.base_model import BaseForecaster

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


class ProbabilisticForecaster(BaseForecaster):
    """
    Quantile regression forecaster producing P10, P50, and P90 uncertainty bands.
    P10: 10% probability that actual generation is below this value (conservative baseline)
    P50: Median generation forecast
    P90: 90% probability that actual generation is below this value (optimistic upper bound)
    """

    QUANTILES = [0.10, 0.50, 0.90]

    def __init__(
        self,
        base_params: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        zero_nighttime: bool = True
    ):
        super().__init__(version=version)
        self.zero_nighttime = zero_nighttime
        self.base_params = {
            "boosting_type": "gbdt",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": 6,
            "n_estimators": 400,
            "n_jobs": -1,
            "device_type": "cpu",   # Explicit CPU execution
            "verbose": -1,
            "random_state": 42,
            **(base_params or {})
        }
        self.models: Dict[str, Any] = {}

    def fit(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        X_val: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        y_val: Optional[Union[pd.Series, np.ndarray]] = None,
        **kwargs
    ) -> "ProbabilisticForecaster":
        """
        Fits 3 distinct quantile regressors (alpha=0.10, 0.50, 0.90).
        """
        if not HAS_LIGHTGBM:
            raise ImportError(
                "LightGBM is not installed. Please install it via 'pip install lightgbm'."
            )

        if isinstance(X_train, pd.DataFrame):
            self.feature_names_ = list(X_train.columns)
        else:
            self.feature_names_ = [f"feature_{i}" for i in range(X_train.shape[1])]

        quantile_keys = ["p10", "p50", "p90"]
        for q, key in zip(self.QUANTILES, quantile_keys):
            params = {
                **self.base_params,
                "objective": "quantile",
                "alpha": q,
            }
            model = lgb.LGBMRegressor(**params)
            eval_set = [(X_val, y_val)] if (X_val is not None and y_val is not None) else None
            model.fit(X_train, y_train, eval_set=eval_set)
            self.models[key] = model

        self.is_fitted = True
        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Default predict returns the median forecast (P50).
        """
        quantiles = self.predict_quantiles(X)
        return quantiles["p50"].values

    def predict_quantiles(self, X: Union[pd.DataFrame, np.ndarray]) -> pd.DataFrame:
        """
        Produces P10, P50, and P90 quantile estimates with monotonicity enforcement:
        p10 <= p50 <= p90.
        """
        if not self.is_fitted:
            raise RuntimeError("ProbabilisticForecaster has not been fitted or loaded.")

        index = X.index if isinstance(X, pd.DataFrame) else None
        preds: Dict[str, np.ndarray] = {}

        for key in ["p10", "p50", "p90"]:
            p = self.models[key].predict(X)
            preds[key] = np.clip(p, 0.0, None)

        p10 = preds["p10"]
        p50 = preds["p50"]
        p90 = preds["p90"]

        # Enforce quantile monotonicity: p10 <= p50 <= p90
        p50 = np.maximum(p10, p50)
        p90 = np.maximum(p50, p90)

        # Enforce zero nighttime if physical indicators are zero
        if self.zero_nighttime and isinstance(X, pd.DataFrame):
            if "poa_global" in X.columns:
                night_mask = X["poa_global"].values <= 1.0
                p10[night_mask] = 0.0
                p50[night_mask] = 0.0
                p90[night_mask] = 0.0
            elif "solar_elevation" in X.columns:
                night_mask = X["solar_elevation"].values <= 0.0
                p10[night_mask] = 0.0
                p50[night_mask] = 0.0
                p90[night_mask] = 0.0

        return pd.DataFrame({"p10": p10, "p50": p50, "p90": p90}, index=index)

    def explain(self, X: Union[pd.DataFrame, np.ndarray]) -> pd.DataFrame:
        """
        Feature importances from the median (P50) model.
        """
        if not self.is_fitted or "p50" not in self.models:
            raise RuntimeError("Model has not been fitted.")

        importances = self.models["p50"].booster_.feature_importance(importance_type="gain")
        total = np.sum(importances)
        return pd.DataFrame({
            "feature": self.feature_names_,
            "importance_gain": importances,
            "relative_importance": importances / (total if total > 0 else 1.0)
        }).sort_values(by="importance_gain", ascending=False)

    def save(self, path: Union[str, Path]) -> None:
        """Serializes probabilistic model artifacts."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "models": self.models,
            "base_params": self.base_params,
            "version": self.version,
            "feature_names": self.feature_names_,
            "is_fitted": self.is_fitted,
            "zero_nighttime": self.zero_nighttime,
        }
        joblib.dump(artifact, path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ProbabilisticForecaster":
        """Loads serialized probabilistic model artifacts."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {path}")

        artifact = joblib.load(path)
        instance = cls(
            base_params=artifact.get("base_params"),
            version=artifact.get("version", "1.0.0"),
            zero_nighttime=artifact.get("zero_nighttime", True)
        )
        instance.models = artifact.get("models", {})
        instance.feature_names_ = artifact.get("feature_names", [])
        instance.is_fitted = artifact.get("is_fitted", True)
        return instance
