"""
app/models/__init__.py

Import all ORM models here so SQLAlchemy metadata is aware of every table
before create_all / Alembic autogenerate is called.
"""

from app.models.user import Permission, Role, User, role_permissions  # noqa: F401
from app.models.plant import Plant, PlantConfig  # noqa: F401
from app.models.scada import ScadaReading  # noqa: F401
from app.models.forecast import ForecastRecord  # noqa: F401
from app.models.alert import AnomalyAlert  # noqa: F401
from app.models.diagnosis import DiagnosisRecord  # noqa: F401
from app.models.maintenance import EquipmentMaintenanceAssessment  # noqa: F401
from app.models.health import PlantHealthRecord  # noqa: F401
from app.models.curtailment import CurtailmentRecord  # noqa: F401

__all__ = [
    "User",
    "Role",
    "Permission",
    "role_permissions",
    "Plant",
    "PlantConfig",
    "ScadaReading",
    "ForecastRecord",
    "AnomalyAlert",
    "DiagnosisRecord",
    "EquipmentMaintenanceAssessment",
    "PlantHealthRecord",
    "CurtailmentRecord",
]
