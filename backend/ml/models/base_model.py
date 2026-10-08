"""
Abstract base class definition for solar power forecasting models.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


class BaseForecaster(ABC):
    """
    Abstract base class for all solar generation forecasting models.
    Defines fit, predict, explain, save, and load contracts.
    """

    def __init__(self, version: str = "1.0.0", **kwargs):
        self.version = version
        self.feature_names_: List[str] = []
        self.is_fitted: bool = False
        self.metadata: Dict[str, Any] = {"version": version}

    @abstractmethod
    def fit(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        X_val: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        y_val: Optional[Union[pd.Series, np.ndarray]] = None,
        **kwargs
    ) -> "BaseForecaster":
        """
        Fit model on training set with optional validation set.
        """
        pass

    @abstractmethod
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Produce generation forecast estimates (gross DC kW).
        """
        pass

    @abstractmethod
    def explain(self, X: Union[pd.DataFrame, np.ndarray]) -> pd.DataFrame:
        """
        Compute feature attribution/importance (e.g., SHAP values or gain).
        """
        pass

    @abstractmethod
    def save(self, path: Union[str, Path]) -> None:
        """
        Serialize model artifact to disk.
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls, path: Union[str, Path]) -> "BaseForecaster":
        """
        Load serialized model artifact from disk.
        """
        pass
