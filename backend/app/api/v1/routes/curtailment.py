"""
app/api/v1/routes/curtailment.py

Grid Curtailment Prediction & Optimization API endpoints (Enhancement 6):
  GET  /api/v1/curtailment/{plant_id}          — predict/retrieve curtailment analysis
  POST /api/v1/curtailment/predict             — on-demand curtailment prediction
  GET  /api/v1/curtailment/{plant_id}/history  — retrieve historical curtailment records
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.curtailment import (
    CurtailmentPredictionRequest,
    CurtailmentPredictionResponse,
    CurtailmentRecordResponse,
)
from app.services import curtailment_service

router = APIRouter(prefix="/curtailment", tags=["Grid Curtailment"])


@router.get(
    "/{plant_id}",
    response_model=CurtailmentPredictionResponse,
    summary="Predict grid curtailment and energy loss for solar plant",
)
async def get_curtailment_prediction(
    plant_id: int,
    export_limit_kw: Optional[float] = Query(
        default=None, gt=0, description="Optional override for plant export limit (kW)"
    ),
    horizon_hours: int = Query(default=24, ge=1, le=168, description="Forecast horizon in hours"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> CurtailmentPredictionResponse:
    try:
        return await curtailment_service.predict_curtailment(
            db,
            plant_id=plant_id,
            export_limit_kw=export_limit_kw,
            horizon_hours=horizon_hours,
            persist=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/predict",
    response_model=CurtailmentPredictionResponse,
    summary="On-demand grid curtailment prediction with custom parameters",
)
async def predict_curtailment_on_demand(
    request: CurtailmentPredictionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> CurtailmentPredictionResponse:
    try:
        return await curtailment_service.predict_curtailment(
            db,
            plant_id=request.plant_id,
            export_limit_kw=request.export_limit_kw,
            horizon_hours=request.horizon_hours,
            persist=request.persist,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{plant_id}/history",
    response_model=List[CurtailmentRecordResponse],
    summary="Retrieve historical curtailment prediction records",
)
async def get_curtailment_history(
    plant_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> List[CurtailmentRecordResponse]:
    try:
        return await curtailment_service.get_curtailment_history(
            db, plant_id=plant_id, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
