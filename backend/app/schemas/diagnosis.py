"""
app/schemas/diagnosis.py

Pydantic schemas for AI-based root-cause diagnosis of solar plant anomalies and inverter faults.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TechnicianStep(BaseModel):
    step_number: int
    action: str
    required_tools: List[str] = Field(default_factory=list)
    safety_note: Optional[str] = None


class DiagnosisRequest(BaseModel):
    plant_id: int
    alert_id: Optional[int] = None
    inverter_error_code: Optional[str] = Field(
        default=None, description="Inverter fault code (e.g. F056, F034, E003, AFCI, ISO_FAULT)"
    )
    expected_power_kw: Optional[float] = None
    actual_power_kw: Optional[float] = None
    irradiance_w_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    module_temp_c: Optional[float] = None
    days_since_cleaning: Optional[float] = None
    notes: Optional[str] = None


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    plant_id: int
    plant_name: Optional[str] = None
    alert_id: Optional[int] = None
    timestamp: datetime
    root_cause_category: str
    root_cause_title: str
    confidence_score: float = Field(..., description="Diagnostic certainty score (0-100%)")
    inverter_error_code: Optional[str] = None
    estimated_loss_kw: float
    financial_impact_per_day: float = Field(..., description="Estimated revenue loss in USD/day")
    urgency_level: str  # CRITICAL | HIGH | MEDIUM | LOW
    summary: str
    root_cause_details: str
    technician_steps: List[TechnicianStep]
    safety_warning: Optional[str] = None
    preventative_advice: Optional[str] = None
    telemetry_evidence: Optional[dict] = None
    created_at: datetime


class RootCauseTaxonomyItem(BaseModel):
    category: str
    title: str
    common_error_codes: List[str]
    description: str
    typical_urgency: str
