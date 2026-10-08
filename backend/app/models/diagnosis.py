"""
app/models/diagnosis.py

SQLAlchemy ORM model for DiagnosisRecord.
Stores AI-driven root-cause diagnostic findings, loss impact, and remediation procedures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DiagnosisRecord(Base):
    __tablename__ = "diagnosis_records"
    __table_args__ = (
        Index("ix_diagnosis_plant_timestamp", "plant_id", "timestamp"),
        Index("ix_diagnosis_alert_id", "alert_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alert_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("anomaly_alerts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    root_cause_category: Mapped[str] = mapped_column(String(64), nullable=False)
    root_cause_title: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    inverter_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    estimated_loss_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    financial_impact_per_day: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    urgency_level: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)

    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    root_cause_details: Mapped[str] = mapped_column(Text, nullable=False)
    technician_steps_json: Mapped[str] = mapped_column(Text, nullable=False)
    safety_warning: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    preventative_advice: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    # Relationships
    plant: Mapped["Plant"] = relationship("Plant")  # type: ignore[name-defined]
    alert: Mapped[Optional["AnomalyAlert"]] = relationship("AnomalyAlert")  # type: ignore[name-defined]
