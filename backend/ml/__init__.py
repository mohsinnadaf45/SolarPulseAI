import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'backend.ml' imports resolve
# even when invoked as 'python -m ml...' or from the backend directory
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.ml.config import PlantConfig

__all__ = ["PlantConfig"]

