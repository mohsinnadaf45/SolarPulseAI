"""
app/schemas/health.py

Pydantic v2 schemas for AI-based solar plant health scoring.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


HealthStatusType = Literal["EXCELLENT", "GOOD", "NEEDS ATTENTION", "POOR", "CRITICAL"]


class PlantHealthComponents(BaseModel):
    generation_performance: float = Field(..., ge=0.0, le=100.0)
    inverter_health: float = Field(..., ge=0.0, le=100.0)
    soiling_condition: float = Field(..., ge=0.0, le=100.0)
    anomaly_health: float = Field(..., ge=0.0, le=100.0)
    equipment_health: float = Field(..., ge=0.0, le=100.0)


class PlantHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    plant_id: int
    health_score: float = Field(..., ge=0.0, le=100.0)
    health_status: HealthStatusType
    components: PlantHealthComponents
    major_concerns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    assessed_at: datetime


class PlantHealthHistoryResponse(BaseModel):
    plant_id: int
    total_records: int
    history: List[PlantHealthResponse]
