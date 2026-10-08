"""
Unit tests for the end-to-end SolarFeaturePipeline.
"""

import pandas as pd
import pytest

from backend.ml.config import PlantConfig
from backend.ml.features.feature_pipeline import (
    SolarFeaturePipeline,
    CANONICAL_FEATURE_COLUMNS,
)


def test_feature_pipeline_canonical_columns(sample_weather_df: pd.DataFrame, sample_plant_config: PlantConfig):
    """Verifies that the pipeline produces all 21 canonical features in order."""
    pipeline = SolarFeaturePipeline(plant_config=sample_plant_config)
    X = pipeline.transform(sample_weather_df)

    assert list(X.columns) == CANONICAL_FEATURE_COLUMNS
    assert len(X) == len(sample_weather_df)
    assert not X.isnull().values.any()
