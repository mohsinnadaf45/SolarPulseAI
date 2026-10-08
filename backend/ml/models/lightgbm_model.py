"""
LightGBM regression model wrapper for solar DC power forecasting.
Configured for high-performance CPU training and inference.
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

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


class LightGBMForecaster(BaseForecaster):
    """
    LightGBM Gradient Boosted Decision Tree forecaster for solar generation.
    Predicts gross DC generation (kW) prior to clipping and operational losses.
    """

    DEFAULT_PARAMS: Dict[str, Any] = {
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": 6,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "n_estimators": 500,
        "n_jobs": -1,
        "device_type": "cpu",   # Explicit CPU execution (no GPU required)
        "verbose": -1,
        "random_state": 42,
    }

    def __init__(
        self,
        params: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        zero_nighttime: bool = True
    ):
        super().__init__(version=version)
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.zero_nighttime = zero_nighttime
        self.model: Optional[Any] = None
        self._explainer: Optional[Any] = None

    def fit(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        X_val: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        y_val: Optional[Union[pd.Series, np.ndarray]] = None,
        early_stopping_rounds: int = 30,
        verbose: bool = False,
        **kwargs
    ) -> "LightGBMForecaster":
        """
        Fits the LightGBM booster on training data with optional early stopping.
        """
        if not HAS_LIGHTGBM:
            raise ImportError(
                "LightGBM is not installed. Please install it via 'pip install lightgbm'."
            )

        # Record feature names if DataFrame
        if isinstance(X_train, pd.DataFrame):
            self.feature_names_ = list(X_train.columns)
        else:
            self.feature_names_ = [f"feature_{i}" for i in range(X_train.shape[1])]

        callbacks = []
        if X_val is not None and y_val is not None and early_stopping_rounds > 0:
            callbacks.append(lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=verbose))
            eval_set = [(X_val, y_val)]
        else:
            eval_set = None

        self.model = lgb.LGBMRegressor(**self.params)
        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            callbacks=callbacks if callbacks else None,
        )

        self.is_fitted = True
        self.metadata["best_iteration"] = getattr(self.model, "best_iteration_", self.params["n_estimators"])
        self.metadata["best_score"] = getattr(self.model, "best_score_", None)
        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Generates DC power predictions. Guarantees non-negative values and
        zeros out predictions when physical daylight indicators are non-positive.
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted yet or loaded from disk.")

        preds = self.model.predict(X)
        preds = np.clip(preds, 0.0, None)

        # Enforce zero generation when physical daylight is zero
        if self.zero_nighttime and isinstance(X, pd.DataFrame):
            if "poa_global" in X.columns:
                night_mask = X["poa_global"].values <= 1.0
                preds[night_mask] = 0.0
            elif "solar_elevation" in X.columns:
                night_mask = X["solar_elevation"].values <= 0.0
                preds[night_mask] = 0.0

        return preds

    def explain(self, X: Union[pd.DataFrame, np.ndarray]) -> pd.DataFrame:
        """
        Calculates feature attributions using SHAP TreeExplainer if available,
        or LightGBM gain-based feature importance as fallback.
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted yet.")

        if HAS_SHAP:
            if self._explainer is None:
                self._explainer = shap.TreeExplainer(self.model.booster_)
            shap_values = self._explainer.shap_values(X)
            return pd.DataFrame(
                shap_values,
                columns=self.feature_names_,
                index=X.index if isinstance(X, pd.DataFrame) else None
            )

        # Fallback to feature importance
        importances = self.model.booster_.feature_importance(importance_type="gain")
        total = np.sum(importances)
        norm_importance = importances / (total if total > 0 else 1.0)
        return pd.DataFrame({
            "feature": self.feature_names_,
            "importance_gain": importances,
            "relative_importance": norm_importance
        }).sort_values(by="importance_gain", ascending=False)

    def save(self, path: Union[str, Path]) -> None:
        """Serializes forecaster instance and metadata."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model": self.model,
            "params": self.params,
            "version": self.version,
            "feature_names": self.feature_names_,
            "is_fitted": self.is_fitted,
            "metadata": self.metadata,
            "zero_nighttime": self.zero_nighttime,
        }
        joblib.dump(artifact, path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "LightGBMForecaster":
        """Loads serialized forecaster instance from disk."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {path}")

        artifact = joblib.load(path)
        instance = cls(
            params=artifact.get("params"),
            version=artifact.get("version", "1.0.0"),
            zero_nighttime=artifact.get("zero_nighttime", True)
        )
        instance.model = artifact.get("model")
        instance.feature_names_ = artifact.get("feature_names", [])
        instance.is_fitted = artifact.get("is_fitted", True)
        instance.metadata = artifact.get("metadata", {})
        return instance
