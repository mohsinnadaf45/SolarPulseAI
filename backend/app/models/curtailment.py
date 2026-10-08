"""
app/models/curtailment.py

SQLAlchemy ORM model for grid curtailment prediction and energy loss records.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CurtailmentRecord(Base):
    __tablename__ = "curtailment_records"
    __table_args__ = (
        Index("ix_curtailment_plant_time", "plant_id", "forecast_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_generation_kw: Mapped[float] = mapped_column(Float, nullable=False)
    export_limit_kw: Mapped[float] = mapped_column(Float, nullable=False)
    potential_curtailment_kw: Mapped[float] = mapped_column(Float, nullable=False)
    potential_curtailment_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    curtailment_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)  # LOW | MEDIUM | HIGH
    recommendation: Mapped[str] = mapped_column(String(1024), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    # Relationships
    plant: Mapped["Plant"] = relationship("Plant", back_populates="curtailment_records")  # type: ignore[name-defined]
