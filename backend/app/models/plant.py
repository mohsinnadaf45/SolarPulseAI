"""
app/models/plant.py

SQLAlchemy ORM models for Plant and PlantConfig.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)
    inverter_capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)
    module_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    # Relationships
    config: Mapped[Optional["PlantConfig"]] = relationship(
        "PlantConfig", back_populates="plant", uselist=False, cascade="all, delete-orphan"
    )
    scada_readings: Mapped[list] = relationship(
        "ScadaReading", back_populates="plant", cascade="all, delete-orphan"
    )
    forecasts: Mapped[list] = relationship(
        "ForecastRecord", back_populates="plant", cascade="all, delete-orphan"
    )
    alerts: Mapped[list] = relationship(
        "AnomalyAlert", back_populates="plant", cascade="all, delete-orphan"
    )
    maintenance_assessments: Mapped[list] = relationship(
        "EquipmentMaintenanceAssessment", back_populates="plant", cascade="all, delete-orphan"
    )
    health_records: Mapped[list] = relationship(
        "PlantHealthRecord", back_populates="plant", cascade="all, delete-orphan"
    )
    curtailment_records: Mapped[list] = relationship(
        "CurtailmentRecord", back_populates="plant", cascade="all, delete-orphan"
    )


class PlantConfig(Base):
    __tablename__ = "plant_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tilt: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)
    azimuth: Mapped[float] = mapped_column(Float, default=180.0, nullable=False)
    efficiency: Mapped[float] = mapped_column(Float, default=0.18, nullable=False)
    soiling_threshold: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    clipping_threshold: Mapped[float] = mapped_column(Float, default=95.0, nullable=False)
    forecast_horizon_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    # Relationships
    plant: Mapped["Plant"] = relationship("Plant", back_populates="config")
