"""
app/schemas/forecast.py

Pydantic v2 schemas for forecast data.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ForecastRequest(BaseModel):
    plant_id: int
    horizon_minutes: int = Field(default=60, ge=5, le=1440)
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    forecast_time: datetime
    generated_at: datetime
    predicted_power_kw: float
    actual_power_kw: Optional[float] = None
    confidence_lower: Optional[float] = None
    confidence_upper: Optional[float] = None
    model_name: str
    model_version: str
    physics_power_kw: Optional[float] = None
    ml_power_kw: Optional[float] = None


class ForecastSummary(BaseModel):
    plant_id: int
    period_start: datetime
    period_end: datetime
    total_predicted_kwh: float
    total_actual_kwh: Optional[float] = None
    mean_absolute_error_kw: Optional[float] = None
    record_count: int
    model_name: str


class ProbabilisticForecastPoint(BaseModel):
    forecast_time: datetime
    p10_kw: float = Field(..., description="10th percentile conservative lower bound")
    p50_kw: float = Field(..., description="50th percentile median expected forecast")
    p90_kw: float = Field(..., description="90th percentile optimistic upper bound")
    uncertainty_band_kw: float = Field(..., description="P90 - P10 prediction interval width")
    relative_uncertainty_pct: float = Field(..., description="Spread as percentage of power/capacity")
    ramp_rate_kw_per_min: float = Field(..., description="Expected rate of power change (kW/min)")
    ramp_rate_pct_per_min: float = Field(..., description="Rate of change relative to plant capacity (%/min)")
    ramp_direction: str = Field(..., description="'up', 'down', or 'stable'")
    ramp_risk_level: str = Field(..., description="'low', 'medium', 'high', or 'critical'")
    cloud_impact_factor: float = Field(..., description="Cloud passage impact index (0.0 - 1.0)")
    bess_reserve_recommendation_kw: float = Field(..., description="Recommended BESS reserve buffering")
    reserve_action: str = Field(..., description="Operational recommendation for plant operators")


class RampRiskSummarySchema(BaseModel):
    max_ramp_rate_kw_per_min: float
    max_ramp_down_kw_per_min: float
    max_ramp_up_kw_per_min: float
    ramp_risk_score: float = Field(..., description="Overall risk index (0 to 100)")
    highest_risk_level: str
    high_risk_event_count: int
    critical_risk_event_count: int
    avg_uncertainty_band_kw: float
    recommended_bess_capacity_kw: float
    primary_action_advisory: str


class ProbabilisticForecastResponse(BaseModel):
    plant_id: int
    plant_name: str
    capacity_kw: float
    generated_at: datetime
    horizon_minutes: int
    interval_minutes: int
    model_name: str
    points: List[ProbabilisticForecastPoint]
    summary: RampRiskSummarySchema
