"""
app/models/health.py

SQLAlchemy ORM model for overall solar plant health scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlantHealthRecord(Base):
    __tablename__ = "plant_health_records"
    __table_args__ = (
        Index("ix_plant_health_plant_assessed", "plant_id", "assessed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    health_score: Mapped[float] = mapped_column(Float, nullable=False)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False)  # EXCELLENT | GOOD | NEEDS ATTENTION | POOR | CRITICAL

    generation_performance: Mapped[float] = mapped_column(Float, nullable=False)
    inverter_health: Mapped[float] = mapped_column(Float, nullable=False)
    soiling_condition: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_health: Mapped[float] = mapped_column(Float, nullable=False)
    equipment_health: Mapped[float] = mapped_column(Float, nullable=False)

    major_concerns: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    recommendations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    # Relationships
    plant: Mapped["Plant"] = relationship("Plant", back_populates="health_records")  # type: ignore[name-defined]
