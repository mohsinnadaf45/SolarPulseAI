"""
Unit tests for ModelRegistry caching and retrieval logic.
"""

from pathlib import Path
import numpy as np
import pytest

from backend.ml.models.base_model import BaseForecaster
from backend.ml.serving.model_registry import ModelRegistry


class DummyForecaster(BaseForecaster):
    """Minimal dummy forecaster for testing registry serialization and caching."""
    def fit(self, X_train, y_train, **kwargs):
        self.is_fitted = True
        return self

    def predict(self, X):
        return np.ones(len(X)) * 500.0

    def explain(self, X):
        return None

    def save(self, path):
        import joblib
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"version": self.version, "is_fitted": self.is_fitted}, path)

    @classmethod
    def load(cls, path):
        import joblib
        data = joblib.load(path)
        inst = cls(version=data.get("version", "1.0.0"))
        inst.is_fitted = data.get("is_fitted", True)
        return inst


def test_model_registry_caching(tmp_path: Path, monkeypatch):
    registry = ModelRegistry(artifact_dir=tmp_path)

    # Save a dummy model
    dummy = DummyForecaster(version="1.0.0")
    dummy.fit(np.zeros((5, 2)), np.zeros(5))
    dummy.save(tmp_path / "lgbm_P01_v1.0.0.pkl")
    dummy.save(tmp_path / "lgbm_latest.pkl")

    # Monkeypatch LightGBMForecaster.load to use DummyForecaster.load for test
    from backend.ml.models import lightgbm_model
    monkeypatch.setattr(lightgbm_model.LightGBMForecaster, "load", DummyForecaster.load)

    # 1. Fetch model
    model1 = registry.get_model(plant_id="P01", version="1.0.0")
    assert model1.is_fitted is True

    # 2. Fetch again - must come from cache
    model2 = registry.get_model(plant_id="P01", version="1.0.0")
    assert model1 is model2  # Exact same cached instance

    # 3. Clear cache and re-fetch
    registry.clear_cache()
    assert len(registry._cache) == 0

    # 4. List available models
    models = registry.list_available_models()
    assert len(models) >= 2
    filenames = [m["filename"] for m in models]
    assert "lgbm_latest.pkl" in filenames
