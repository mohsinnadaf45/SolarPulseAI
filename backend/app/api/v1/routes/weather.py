"""
app/api/v1/routes/weather.py

Weather endpoints:
  GET /api/v1/weather/{plant_id}/current    - live conditions at plant location
  GET /api/v1/weather/{plant_id}/forecast   - multi-day hourly forecast
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.services import plant_service, weather_service

router = APIRouter(prefix="/weather", tags=["Weather"])


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _point_to_dict(pt: weather_service.WeatherPoint) -> Dict[str, Any]:
    return {
        "timestamp": pt.timestamp.isoformat(),
        "temperature_c": round(pt.temperature_c, 2),
        "humidity_pct": round(pt.humidity_pct, 1),
        "wind_speed_kph": round(pt.wind_speed_kph, 1),
        "cloud_cover_pct": round(pt.cloud_cover_pct, 1),
        "uv_index": round(pt.uv_index, 1),
        "irradiance_w_m2": round(pt.irradiance_w_m2, 1),
        "condition": pt.condition_text,
        "is_day": pt.is_day,
    }


def _weather_data_to_dict(
    wd: weather_service.WeatherData,
    include_hourly: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "latitude": wd.latitude,
        "longitude": wd.longitude,
        "location_name": wd.location_name,
        "timezone_id": wd.timezone_id,
        "fetched_at": wd.fetched_at.isoformat(),
        "source": wd.source,
        "current": _point_to_dict(wd.current),
    }
    if include_hourly:
        payload["hourly_forecast"] = [_point_to_dict(p) for p in wd.hourly_forecast]
    return payload


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{plant_id}/current",
    summary="Current weather conditions at a plant location",
)
async def get_current_weather(
    plant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Returns the latest weather conditions (temperature, irradiance proxy,
    humidity, wind speed, cloud cover) for the plant's lat/lon.
    """
    plant = await plant_service.get_plant(db, plant_id)
    weather = await weather_service.get_current_weather(plant.latitude, plant.longitude)
    return _weather_data_to_dict(weather, include_hourly=False)


@router.get(
    "/{plant_id}/forecast",
    summary="Multi-day hourly weather forecast at a plant location",
)
async def get_forecast_weather(
    plant_id: int,
    days: int = Query(default=3, ge=1, le=3, description="Forecast days (1-3)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Returns hourly weather forecast for up to 3 days at the plant location.
    Includes estimated irradiance derived from cloud cover and UV index.
    """
    plant = await plant_service.get_plant(db, plant_id)
    weather = await weather_service.get_forecast_weather(
        plant.latitude, plant.longitude, days=days
    )
    return _weather_data_to_dict(weather, include_hourly=True)
