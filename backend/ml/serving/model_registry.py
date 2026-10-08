"""
Model registry for loading, caching, and serving trained forecaster artifacts.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import joblib

from backend.ml.models.base_model import BaseForecaster
from backend.ml.models.lightgbm_model import LightGBMForecaster
from backend.ml.models.probabilistic_model import ProbabilisticForecaster

logger = logging.getLogger("solarpulse.registry")


class ModelRegistry:
    """
    In-memory registry and cache for model artifacts stored on disk.
    Avoids redundant file I/O during real-time API inference and background worker tasks.
    """

    def __init__(self, artifact_dir: Optional[Union[str, Path]] = None):
        if artifact_dir is None:
            self.artifact_dir = (
                Path(__file__).resolve().parent.parent / "artifacts" / "models"
            )
        else:
            self.artifact_dir = Path(artifact_dir)

        self._cache: Dict[str, BaseForecaster] = {}

    def get_model(
        self,
        plant_id: str = "default",
        version: Optional[str] = None,
        probabilistic: bool = False
    ) -> BaseForecaster:
        """
        Retrieves a cached model instance or loads it from disk.

        Parameters
        ----------
        plant_id : str
            Identifier for the solar plant.
        version : Optional[str]
            Specific model version (e.g. "1.0.0"). If None, resolves latest model.
        probabilistic : bool
            If True, loads quantile probabilistic forecaster instead of point forecaster.

        Returns
        -------
        BaseForecaster
            Fitted forecaster ready for inference.
        """
        prefix = "prob" if probabilistic else "lgbm"
        cache_key = f"{prefix}_{plant_id}_{version or 'latest'}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        model_path = self._resolve_model_path(
            plant_id=plant_id,
            version=version,
            prefix=prefix
        )

        logger.info("Loading model artifact from %s", model_path)
        if probabilistic:
            model = ProbabilisticForecaster.load(model_path)
        else:
            model = LightGBMForecaster.load(model_path)

        self._cache[cache_key] = model
        return model

    def _resolve_model_path(
        self,
        plant_id: str,
        version: Optional[str],
        prefix: str
    ) -> Path:
        """
        Locates the appropriate model artifact path on disk.
        """
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        # 1. Check versioned file for specific plant
        if version:
            candidate = self.artifact_dir / f"{prefix}_{plant_id}_v{version}.pkl"
            if candidate.exists():
                return candidate

        # 2. Check plant-specific latest
        plant_latest = self.artifact_dir / f"{prefix}_{plant_id}_latest.pkl"
        if plant_latest.exists():
            return plant_latest

        # 3. Check generic latest
        generic_latest = self.artifact_dir / f"{prefix}_latest.pkl"
        if generic_latest.exists():
            return generic_latest

        # 4. Search any matching prefix artifact
        matches = list(self.artifact_dir.glob(f"{prefix}*.pkl"))
        if matches:
            # Pick latest modified
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]

        raise FileNotFoundError(
            f"No model artifact found for prefix '{prefix}', plant '{plant_id}', "
            f"in {self.artifact_dir}"
        )

    def list_available_models(self) -> List[Dict[str, str]]:
        """
        Lists all serialized model files in the artifact directory.
        """
        if not self.artifact_dir.exists():
            return []

        models = []
        for path in self.artifact_dir.glob("*.pkl"):
            models.append({
                "filename": path.name,
                "path": str(path),
                "size_kb": f"{path.stat().st_size / 1024:.1f}",
            })
        return models

    def clear_cache(self) -> None:
        """Flushes the in-memory model cache."""
        self._cache.clear()
        logger.info("Model registry cache cleared.")
