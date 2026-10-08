"""
app/api/v1/routes/maintenance.py

Predictive Maintenance & Failure Forecasting API endpoints (Enhancement 4):
  POST /api/v1/maintenance/assess               — calculate/persist failure risk assessment
  GET  /api/v1/maintenance/{plant_id}          — retrieve equipment risk assessments
  GET  /api/v1/maintenance/high-risk/list      — list high-risk equipment
  GET  /api/v1/maintenance/{plant_id}/recommendations — retrieve maintenance recommendations
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.maintenance import (
    HighRiskEquipmentResponse,
    MaintenanceAssessmentRequest,
    MaintenanceAssessmentResponse,
    MaintenanceRecommendationResponse,
)
from app.services import maintenance_service

router = APIRouter(prefix="/maintenance", tags=["Predictive Maintenance"])


@router.post(
    "/assess",
    response_model=MaintenanceAssessmentResponse,
    summary="Calculate equipment failure risk assessment",
)
async def assess_equipment_risk(
    request: MaintenanceAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MaintenanceAssessmentResponse:
    try:
        assessment = await maintenance_service.assess_equipment_failure_risk(
            db,
            plant_id=request.plant_id,
            equipment_id=request.equipment_id,
            window_hours=request.window_hours,
            persist=request.persist,
        )
        return assessment
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/high-risk/list",
    response_model=List[HighRiskEquipmentResponse],
    summary="List equipment with HIGH or CRITICAL failure risk",
)
async def get_high_risk_equipment(
    plant_id: Optional[int] = Query(default=None, description="Optional plant ID filter"),
    min_score: float = Query(default=60.0, ge=0.0, le=100.0, description="Minimum risk score threshold"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> List[HighRiskEquipmentResponse]:
    return await maintenance_service.get_high_risk_equipment(
        db, plant_id=plant_id, min_score=min_score, limit=limit
    )


@router.get(
    "/{plant_id}",
    response_model=List[MaintenanceAssessmentResponse],
    summary="Retrieve failure risk assessments for plant equipment",
)
async def get_plant_maintenance_assessments(
    plant_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> List[MaintenanceAssessmentResponse]:
    try:
        return await maintenance_service.get_maintenance_assessments(
            db, plant_id=plant_id, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{plant_id}/recommendations",
    response_model=MaintenanceRecommendationResponse,
    summary="Retrieve actionable maintenance recommendations for plant equipment",
)
async def get_plant_maintenance_recommendations(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MaintenanceRecommendationResponse:
    try:
        return await maintenance_service.get_maintenance_recommendations(
            db, plant_id=plant_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
