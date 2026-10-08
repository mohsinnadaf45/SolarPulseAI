"""
app/api/v1/routes/plants.py

Plant management endpoints:
  POST   /api/v1/plants
  GET    /api/v1/plants
  GET    /api/v1/plants/{plant_id}
  PUT    /api/v1/plants/{plant_id}
  DELETE /api/v1/plants/{plant_id}
  GET    /api/v1/plants/{plant_id}/config
  PUT    /api/v1/plants/{plant_id}/config
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.plant import (
    PlantConfigCreate,
    PlantConfigResponse,
    PlantConfigUpdate,
    PlantCreate,
    PlantResponse,
    PlantUpdate,
)
from app.services import plant_service

router = APIRouter(prefix="/plants", tags=["Plants"])


@router.post(
    "",
    response_model=PlantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new solar plant",
)
async def create_plant(
    data: PlantCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantResponse:
    plant = await plant_service.create_plant(db, data)
    return plant  # type: ignore[return-value]


@router.post(
    "/seed",
    summary="Seed demo solar plants, forecasts, and telemetry",
)
async def seed_demo_plants() -> dict:
    """Convenience endpoint to populate database with demo plants and historical telemetry."""
    from app.scripts.seed_data import seed
    await seed()
    return {"message": "Demo solar plants and operational data successfully seeded."}


@router.get(
    "",
    response_model=List[PlantResponse],
    summary="List all active plants",
)
async def list_plants(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> List[PlantResponse]:
    plants = await plant_service.list_plants(db, skip=skip, limit=limit)
    return plants  # type: ignore[return-value]


@router.get(
    "/{plant_id}",
    response_model=PlantResponse,
    summary="Get a plant by ID",
)
async def get_plant(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantResponse:
    plant = await plant_service.get_plant(db, plant_id)
    return plant  # type: ignore[return-value]


@router.put(
    "/{plant_id}",
    response_model=PlantResponse,
    summary="Update a plant",
)
async def update_plant(
    plant_id: int,
    data: PlantUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantResponse:
    plant = await plant_service.update_plant(db, plant_id, data)
    return plant  # type: ignore[return-value]


@router.delete(
    "/{plant_id}",
    summary="Deactivate a plant (soft delete)",
)
async def delete_plant(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    return await plant_service.delete_plant(db, plant_id)


@router.get(
    "/{plant_id}/config",
    response_model=PlantConfigResponse,
    summary="Get plant configuration",
)
async def get_plant_config(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantConfigResponse:
    config = await plant_service.get_plant_config(db, plant_id)
    return config  # type: ignore[return-value]


@router.put(
    "/{plant_id}/config",
    response_model=PlantConfigResponse,
    summary="Update plant configuration",
)
async def update_plant_config(
    plant_id: int,
    data: PlantConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PlantConfigResponse:
    config = await plant_service.update_plant_config(db, plant_id, data)
    return config  # type: ignore[return-value]
