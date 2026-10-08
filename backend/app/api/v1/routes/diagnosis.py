"""
app/api/v1/routes/diagnosis.py

AI-Based Root-Cause Diagnosis endpoints:
  GET  /api/v1/diagnosis/taxonomy         — List diagnostic categories & known inverter error codes
  POST /api/v1/diagnosis/diagnose         — On-demand diagnostic evaluation
  GET  /api/v1/diagnosis/alert/{alert_id} — Auto-diagnose a specific alert
  GET  /api/v1/diagnosis/plant/{plant_id} — List historical diagnoses for a plant
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.diagnosis import (
    DiagnosisRequest,
    DiagnosisResponse,
    RootCauseTaxonomyItem,
)
from app.services import diagnosis_service, plant_service

router = APIRouter(prefix="/diagnosis", tags=["AI Diagnosis"])


@router.get(
    "/taxonomy",
    response_model=List[RootCauseTaxonomyItem],
    summary="Get root-cause diagnostic taxonomy and supported inverter error codes",
)
async def get_taxonomy(
    _: User = Depends(get_current_active_user),
) -> List[RootCauseTaxonomyItem]:
    return diagnosis_service.get_root_cause_taxonomy()


@router.post(
    "/diagnose",
    response_model=DiagnosisResponse,
    summary="Run AI-based root-cause diagnosis on telemetry or inverter error codes",
)
async def run_diagnosis(
    request: DiagnosisRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DiagnosisResponse:
    # Validate plant
    plant = await plant_service.get_plant(db, request.plant_id)

    diag = diagnosis_service.diagnose_root_cause(
        plant_id=plant.id,
        plant_name=plant.name,
        capacity_kw=plant.capacity_kw,
        alert_id=request.alert_id,
        inverter_error_code=request.inverter_error_code,
        expected_power_kw=request.expected_power_kw,
        actual_power_kw=request.actual_power_kw,
        irradiance_w_m2=request.irradiance_w_m2,
        temperature_c=request.temperature_c,
        module_temp_c=request.module_temp_c,
        days_since_cleaning=request.days_since_cleaning,
        notes=request.notes,
    )

    saved = await diagnosis_service.persist_diagnosis(db, diag)
    diag.id = saved.id
    return diag


@router.get(
    "/alert/{alert_id}",
    response_model=DiagnosisResponse,
    summary="Run or retrieve AI root-cause diagnosis for an anomaly alert",
)
async def diagnose_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DiagnosisResponse:
    try:
        return await diagnosis_service.run_diagnosis_for_alert(db, alert_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/plant/{plant_id}",
    response_model=List[DiagnosisResponse],
    summary="List root-cause diagnoses for a plant",
)
async def list_plant_diagnoses(
    plant_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> List[DiagnosisResponse]:
    return await diagnosis_service.list_diagnoses_by_plant(db, plant_id=plant_id, limit=limit)
