"""
Optuna hyperparameter search configuration for LightGBM CPU model tuning.
"""

from typing import Any, Callable, Dict, Optional, Union
import numpy as np
import pandas as pd
from sklearn.metrics import root_mean_squared_error

from backend.ml.training.cross_validate import PurgedTimeSeriesSplit

try:
    import optuna
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


def sample_hyperparameters(trial: Any) -> Dict[str, Any]:
    """
    Defines search distributions for LightGBM hyperparameters on CPU.
    """
    return {
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "device_type": "cpu",
        "n_jobs": -1,
        "verbose": -1,
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 63),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 80),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 150, 600, step=50),
        "random_state": 42,
    }


def create_objective(
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    cv: Optional[PurgedTimeSeriesSplit] = None
) -> Callable[[Any], float]:
    """
    Creates an Optuna objective function evaluating out-of-fold RMSE across CV splits.
    """
    if not HAS_LIGHTGBM:
        raise ImportError("LightGBM must be installed to run optimization.")

    splitter = cv or PurgedTimeSeriesSplit(n_splits=3, purge_gap_steps=24)
    X_arr = np.asarray(X)
    y_arr = np.asarray(y)

    def objective(trial: Any) -> float:
        params = sample_hyperparameters(trial)
        fold_rmses = []

        for train_idx, val_idx in splitter.split(X_arr, y_arr):
            X_tr, y_tr = X_arr[train_idx], y_arr[train_idx]
            X_va, y_va = X_arr[val_idx], y_arr[val_idx]

            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_tr,
                y_tr,
                eval_set=[(X_va, y_va)],
                callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
            )

            preds = model.predict(X_va)
            rmse = root_mean_squared_error(y_va, preds)
            fold_rmses.append(rmse)

        return float(np.mean(fold_rmses))

    return objective


def run_hyperparameter_optimization(
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    n_trials: int = 50,
    timeout: Optional[int] = 300
) -> Dict[str, Any]:
    """
    Executes hyperparameter tuning using Optuna.
    """
    if not HAS_OPTUNA:
        raise ImportError("Optuna is not installed. Run 'pip install optuna' to enable.")

    study = optuna.create_study(direction="minimize")
    objective = create_objective(X, y)
    study.optimize(objective, n_trials=n_trials, timeout=timeout)
    return study.best_params
