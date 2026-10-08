"""
app/schemas/curtailment.py

Pydantic v2 schemas for grid curtailment prediction, energy loss forecasting, and optimization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


CurtailmentRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class CurtailmentPredictionRequest(BaseModel):
    plant_id: int
    export_limit_kw: Optional[float] = Field(
        default=None, gt=0, description="Optional override for plant AC grid export limit (kW)"
    )
    horizon_hours: int = Field(
        default=24, ge=1, le=168, description="Prediction horizon in hours"
    )
    persist: bool = Field(default=True, description="Whether to persist the summary curtailment record")


class CurtailmentHourlyPoint(BaseModel):
    timestamp: datetime
    forecast_generation_kw: float
    export_limit_kw: float
    potential_curtailment_kw: float
    potential_curtailment_kwh: float
    curtailment_percentage: float
    is_curtailed: bool


class CurtailmentPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plant_id: int
    forecast_generation_kw: float
    export_limit_kw: float
    potential_curtailment_kw: float
    potential_curtailment_kwh: float
    curtailment_percentage: float
    risk_level: CurtailmentRiskLevel
    recommendation: str
    schedule: List[CurtailmentHourlyPoint] = Field(default_factory=list)
    bess_opportunity: Optional[Dict[str, Any]] = None
    assessed_at: datetime


class CurtailmentRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    forecast_time: datetime
    forecast_generation_kw: float
    export_limit_kw: float
    potential_curtailment_kw: float
    potential_curtailment_kwh: float
    curtailment_percentage: float
    risk_level: str
    recommendation: str
    created_at: datetime
