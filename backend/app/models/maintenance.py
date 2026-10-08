"""
app/models/maintenance.py

SQLAlchemy ORM model for predictive maintenance assessments and equipment failure risk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EquipmentMaintenanceAssessment(Base):
    __tablename__ = "equipment_maintenance_assessments"
    __table_args__ = (
        Index("ix_maint_plant_assessed", "plant_id", "assessed_at"),
        Index("ix_maint_equip_risk", "equipment_id", "risk_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    equipment_type: Mapped[str] = mapped_column(String(64), default="inverter", nullable=False)

    failure_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)  # LOW | MEDIUM | HIGH | CRITICAL
    warning: Mapped[str] = mapped_column(String(512), nullable=False)
    contributing_factors: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(1024), nullable=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    # Relationships
    plant: Mapped["Plant"] = relationship("Plant", back_populates="maintenance_assessments")  # type: ignore[name-defined]
