"""
Unit tests for evaluation metrics and purged time-series cross-validation.
"""

import numpy as np
import pytest

from backend.ml.training.evaluate import (
    evaluate_forecast,
    mean_bias_error,
    masked_mape,
    normalized_rmse,
)
from backend.ml.training.cross_validate import PurgedTimeSeriesSplit


def test_mean_bias_error():
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 210.0, 310.0])  # Over-prediction by +10
    assert mean_bias_error(y_true, y_pred) == 10.0


def test_masked_mape_zeros():
    """Verifies that night / zero-generation values don't cause zero division."""
    y_true = np.array([0.0, 0.0, 100.0, 200.0])
    y_pred = np.array([0.0, 5.0, 110.0, 180.0])
    mape = masked_mape(y_true, y_pred, min_threshold_kw=10.0)
    # Evaluates only on 100.0 and 200.0: |10/100| = 10%, |-20/200| = 10% -> 10%
    assert pytest.approx(mape, 0.01) == 10.0


def test_purged_time_series_split():
    """Verifies that train and test indices have no lookahead and respect purge gap."""
    n_samples = 200
    purge_gap = 10
    cv = PurgedTimeSeriesSplit(n_splits=3, purge_gap_steps=purge_gap)
    X = np.arange(n_samples)

    for train_idx, test_idx in cv.split(X):
        # Strict temporal ordering: max train index + purge_gap <= min test index
        assert np.max(train_idx) + purge_gap <= np.min(test_idx)
        # Test fold is non-empty
        assert len(test_idx) > 0
        assert len(train_idx) > 0
