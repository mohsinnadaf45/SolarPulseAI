"""
Time-series cross-validation without lookahead bias, including purge gap support.
"""

from typing import Any, Generator, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class PurgedTimeSeriesSplit:
    """
    Time-series cross-validation splitter with purge gap to prevent lookahead leakage
    from autoregressive lag features (e.g. 24h SCADA power lags).

    Splits dataset chronologically into n_splits contiguous folds with expanding or rolling window.
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge_gap_steps: int = 24,    # 24 steps = 24 hours for hourly data
        expanding_window: bool = True,
        min_train_steps: Optional[int] = None
    ):
        if n_splits < 2:
            raise ValueError("n_splits must be at least 2.")
        self.n_splits = n_splits
        self.purge_gap_steps = purge_gap_steps
        self.expanding_window = expanding_window
        self.min_train_steps = min_train_steps

    def get_n_splits(self) -> int:
        return self.n_splits

    def split(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
        groups: Optional[Any] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yields (train_indices, test_indices) for each fold.
        """
        n_samples = len(X)
        indices = np.arange(n_samples)

        # Allocate test fold size
        # Total available space = min_train + n_splits * test_size + (n_splits * gap)
        # Approximate test size per split:
        test_size = n_samples // (self.n_splits + 1)
        min_train = self.min_train_steps or test_size

        for fold in range(self.n_splits):
            test_start = min_train + fold * test_size + self.purge_gap_steps
            test_end = min(test_start + test_size, n_samples)

            if test_start >= n_samples:
                break

            train_end = test_start - self.purge_gap_steps

            if self.expanding_window:
                train_start = 0
            else:
                train_start = max(0, train_end - min_train)

            train_idx = indices[train_start:train_end]
            test_idx = indices[test_start:test_end]

            if len(train_idx) == 0 or len(test_idx) == 0:
                continue

            yield train_idx, test_idx
