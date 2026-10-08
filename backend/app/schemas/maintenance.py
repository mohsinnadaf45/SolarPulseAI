"""
app/schemas/maintenance.py

Pydantic v2 schemas for predictive maintenance and equipment failure risk forecasting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


RiskLevelType = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class MaintenanceAssessmentRequest(BaseModel):
    plant_id: int
    equipment_id: Optional[str] = Field(default=None, description="Specific equipment ID to assess")
    window_hours: int = Field(default=24, ge=1, le=720, description="Historical lookback window in hours")
    persist: bool = Field(default=True, description="Whether to persist the assessment record")


class MaintenanceAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    plant_id: int
    equipment_id: str
    equipment_type: str = "inverter"
    failure_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: RiskLevelType
    warning: str
    contributing_factors: List[str]
    recommended_action: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    assessed_at: datetime


class HighRiskEquipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plant_id: int
    equipment_id: str
    equipment_type: str
    failure_risk_score: float
    risk_level: RiskLevelType
    warning: str
    recommended_action: str
    assessed_at: datetime


class MaintenanceRecommendationItem(BaseModel):
    plant_id: int
    equipment_id: str
    risk_level: RiskLevelType
    priority: Literal["IMMEDIATE", "URGENT", "SCHEDULED", "ROUTINE"]
    recommended_action: str
    contributing_factors: List[str]
    assessed_at: datetime


class MaintenanceRecommendationResponse(BaseModel):
    plant_id: int
    total_recommendations: int
    recommendations: List[MaintenanceRecommendationItem]
