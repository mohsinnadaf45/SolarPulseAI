"""
app/api/v1/routes/health.py

AI-Based Solar Plant Health Scoring API endpoints (Enhancement 5):
  GET  /api/v1/health-score/{plant_id}            — get current plant health score and status
  POST /api/v1/health-score/{plant_id}/calculate  — trigger on-demand health score calculation
  GET  /api/v1/health-score/{plant_id}/components — retrieve component score breakdown
  GET  /api/v1/health-score/{plant_id}/history    — retrieve historical health scores
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.health import (
    PlantHealthComponents,
    PlantHealthHistoryResponse,
    PlantHealthResponse,
)
from app.services import health_service

router = APIRouter(prefix="/health-score", tags=["Plant Health Scoring"])


@router.get(
    "/{plant_id}",
    response_model=PlantHealthResponse,
    summary="Get current solar plant health score and status",
)
async def get_plant_health(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantHealthResponse:
    try:
        return await health_service.get_latest_plant_health(db, plant_id=plant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/{plant_id}/calculate",
    response_model=PlantHealthResponse,
    summary="Trigger fresh AI plant health score calculation",
)
async def calculate_plant_health(
    plant_id: int,
    persist: bool = Query(default=True, description="Persist health score record to database"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantHealthResponse:
    try:
        return await health_service.calculate_plant_health(
            db, plant_id=plant_id, persist=persist
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{plant_id}/components",
    response_model=PlantHealthComponents,
    summary="Retrieve component scores breakdown for solar plant",
)
async def get_health_components(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantHealthComponents:
    try:
        health_data = await health_service.get_latest_plant_health(db, plant_id=plant_id)
        return health_data.components
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{plant_id}/history",
    response_model=PlantHealthHistoryResponse,
    summary="Retrieve historical health scores for trend analysis",
)
async def get_health_history(
    plant_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantHealthHistoryResponse:
    try:
        return await health_service.get_plant_health_history(
            db, plant_id=plant_id, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
