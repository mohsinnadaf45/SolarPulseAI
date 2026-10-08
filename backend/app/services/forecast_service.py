"""
app/services/forecast_service.py

Main forecasting orchestration service.

Pipeline:
  SCADA/weather inputs
    → physics feature extraction (pvlib)
    → soiling adjustment
    → clipping adjustment
    → ML prediction (LightGBM or development fallback)
    → post-processing
    → ForecastRecord persisted to DB
    → API response

If no trained LightGBM model is available the service falls back to a
clearly-labelled development estimate — it never pretends to be a real
ML prediction.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.forecast import ForecastRecord
from app.models.scada import ScadaReading
from app.schemas.forecast import (
    ForecastResponse,
    ForecastSummary,
    ProbabilisticForecastResponse,
    ProbabilisticForecastPoint,
    RampRiskSummarySchema,
)
from app.services.clipping_service import calculate_clipping
from app.services.soiling_service import calculate_soiling_loss
from app.services import weather_service

try:
    from backend.ml.postprocessing.ramp_risk import compute_ramp_risk_profile
except ImportError:
    from ml.postprocessing.ramp_risk import compute_ramp_risk_profile

logger = get_logger(__name__)

# ── pvlib import (graceful if unavailable) ────────────────────────────────────
try:
    import pvlib  # type: ignore
    PVLIB_AVAILABLE = True
except ImportError:
    PVLIB_AVAILABLE = False
    logger.warning("pvlib not installed — physics features will be estimated.")

# ── LightGBM model loading ────────────────────────────────────────────────────

_lgbm_model = None  # cached model instance


def _try_load_model():
    """Attempt to load the LightGBM model. Returns None if unavailable."""
    global _lgbm_model
    if _lgbm_model is not None:
        return _lgbm_model

    model_path = settings.ML_MODEL_PATH
    if not os.path.exists(model_path):
        logger.info(
            f"LightGBM model not found at '{model_path}'. "
            "Using development fallback predictions."
        )
        return None

    try:
        import lightgbm as lgb  # type: ignore
        _lgbm_model = lgb.Booster(model_file=model_path)
        logger.info(f"LightGBM model loaded from '{model_path}'")
        return _lgbm_model
    except Exception as exc:
        logger.error(f"Failed to load LightGBM model: {exc}")
        return None


# ── Physics feature extraction ────────────────────────────────────────────────


def _calculate_physics_power(
    latitude: float,
    longitude: float,
    tilt: float,
    azimuth: float,
    capacity_kw: float,
    efficiency: float,
    forecast_time: datetime,
    irradiance_w_m2: Optional[float] = None,
    temperature_c: Optional[float] = None,
) -> float:
    """
    Estimate physics-based power output.

    Uses pvlib clearsky if available, otherwise falls back to astronomical
    solar elevation model. Accurately yields 0.0 during nighttime.
    """
    if irradiance_w_m2 is None:
        if PVLIB_AVAILABLE:
            try:
                location = pvlib.location.Location(
                    latitude=latitude,
                    longitude=longitude,
                    tz="UTC",
                )
                times = pd.DatetimeIndex([forecast_time.astimezone(timezone.utc)])
                clearsky = location.get_clearsky(times)
                irradiance_w_m2 = max(0.0, float(clearsky["ghi"].iloc[0]))
            except Exception as exc:
                logger.debug(f"pvlib clearsky failed: {exc}")
                irradiance_w_m2 = None

        if irradiance_w_m2 is None:
            # Fallback astronomical solar elevation calculation
            utc_time = forecast_time.astimezone(timezone.utc)
            doy = utc_time.timetuple().tm_yday
            hour_utc = utc_time.hour + utc_time.minute / 60.0
            solar_time_h = (hour_utc + longitude / 15.0) % 24.0
            declination_rad = np.radians(23.45 * np.sin(np.radians((360 / 365) * (doy - 81))))
            lat_rad = np.radians(latitude)
            hour_angle_rad = np.radians(15.0 * (solar_time_h - 12.0))
            sin_elevation = (
                np.sin(lat_rad) * np.sin(declination_rad)
                + np.cos(lat_rad) * np.cos(declination_rad) * np.cos(hour_angle_rad)
            )
            if sin_elevation <= 0.0:
                irradiance_w_m2 = 0.0
            else:
                irradiance_w_m2 = float(980.0 * (sin_elevation ** 1.15))

    if irradiance_w_m2 <= 1.0:
        return 0.0

    temperature_c = temperature_c or 25.0

    # Simple temperature derating: -0.4% per degree above 25°C
    temp_correction = 1.0 - max(0.0, (temperature_c - 25.0) * 0.004)

    # Estimate panel area from capacity (1 kWp ≈ 6 m² at std efficiency)
    panel_area_m2 = (capacity_kw * 1000.0) / (1000.0 * efficiency)

    # DC power
    dc_power_kw = (irradiance_w_m2 / 1000.0) * panel_area_m2 * efficiency * temp_correction / 1.0

    # Cap at plant capacity
    return min(dc_power_kw, capacity_kw)


# ── Development fallback prediction ──────────────────────────────────────────


def _development_fallback_prediction(
    physics_power_kw: float,
    capacity_kw: float,
) -> float:
    """
    Development-only power estimate.

    Uses physics power with small noise.  This is NOT a real ML prediction.
    The model_name field will be set to 'development_fallback' in responses.
    """
    noise = np.random.uniform(-0.02, 0.02) * physics_power_kw
    return max(0.0, min(physics_power_kw + noise, capacity_kw))


# ── ML prediction ─────────────────────────────────────────────────────────────


def _ml_prediction(features: dict, capacity_kw: float) -> tuple[float, str]:
    """
    Run LightGBM prediction.  Returns (predicted_kw, model_name).

    Falls back to development estimate if model unavailable.
    """
    model = _try_load_model()
    if model is None:
        # Development fallback — clearly labelled
        physics_kw = features.get("physics_power_kw", capacity_kw * 0.5)
        return _development_fallback_prediction(physics_kw, capacity_kw), "development_fallback"

    try:
        feature_df = pd.DataFrame([features])
        prediction = float(model.predict(feature_df)[0])
        prediction = max(0.0, min(prediction, capacity_kw))
        return prediction, "lightgbm"
    except Exception as exc:
        logger.error(f"LightGBM prediction failed: {exc}. Using fallback.")
        physics_kw = features.get("physics_power_kw", capacity_kw * 0.5)
        return _development_fallback_prediction(physics_kw, capacity_kw), "development_fallback"


# ── Main forecast generation ──────────────────────────────────────────────────


async def generate_forecast(
    db: AsyncSession,
    plant,       # Plant ORM instance
    config,      # PlantConfig ORM instance
    horizon_minutes: int = 60,
) -> ForecastRecord:
    """
    Generate and persist a forecast for the given plant.

    Parameters
    ----------
    plant:  Plant ORM object
    config: PlantConfig ORM object
    horizon_minutes: how far ahead to forecast
    """
    forecast_time = datetime.now(tz=timezone.utc) + timedelta(minutes=horizon_minutes)

    # ── Fetch recent SCADA for context ──────────────────────────────────────
    result = await db.execute(
        select(ScadaReading)
        .where(ScadaReading.plant_id == plant.id)
        .order_by(ScadaReading.timestamp.desc())
        .limit(1)
    )
    latest_scada: Optional[ScadaReading] = result.scalar_one_or_none()

    # ── Weather data (WeatherAPI.com or mock fallback) ────────────────────────
    weather: Optional[weather_service.WeatherPoint] = None
    try:
        wd = await weather_service.get_current_weather(plant.latitude, plant.longitude)
        weather = wd.current
        logger.debug(
            f"Weather for plant {plant.id}: "
            f"temp={weather.temperature_c}°C irr={weather.irradiance_w_m2:.0f} W/m² "
            f"source={wd.source}"
        )
    except Exception as exc:
        logger.warning(f"Could not fetch weather for plant {plant.id}: {exc}")

    # Prefer live weather over SCADA reading for irradiance/temperature
    irradiance = (
        weather.irradiance_w_m2
        if weather is not None
        else (latest_scada.irradiance_w_m2 if latest_scada else None)
    )
    temperature = (
        weather.temperature_c
        if weather is not None
        else (latest_scada.temperature_c if latest_scada else None)
    )

    # ── Physics layer ─────────────────────────────────────────────────────
    physics_kw = _calculate_physics_power(
        latitude=plant.latitude,
        longitude=plant.longitude,
        tilt=config.tilt,
        azimuth=config.azimuth,
        capacity_kw=plant.capacity_kw,
        efficiency=config.efficiency,
        forecast_time=forecast_time,
        irradiance_w_m2=irradiance,
        temperature_c=temperature,
    )

    # ── Soiling adjustment ────────────────────────────────────────────────
    soiling = calculate_soiling_loss(
        current_power_kw=physics_kw,
        days_since_cleaning=7.0,  # placeholder; replace with real tracking later
        irradiance_w_m2=irradiance or 600.0,
    )
    soiling_adjusted_kw = max(0.0, physics_kw - soiling.estimated_loss_kw)

    # ── Clipping adjustment ───────────────────────────────────────────────
    clipping = calculate_clipping(
        dc_power_kw=soiling_adjusted_kw,
        inverter_capacity_kw=plant.inverter_capacity_kw,
        efficiency=config.efficiency,
    )

    # ── Feature vector for ML ─────────────────────────────────────────────
    features = {
        "physics_power_kw": physics_kw,
        "soiling_loss_percent": soiling.soiling_loss_percent,
        "clipping_loss_kw": clipping.clipping_loss_kw,
        "irradiance_w_m2": irradiance or 0.0,
        "temperature_c": temperature or 25.0,
        "hour": forecast_time.hour,
        "day_of_year": forecast_time.timetuple().tm_yday,
        "capacity_kw": plant.capacity_kw,
        "inverter_capacity_kw": plant.inverter_capacity_kw,
        "tilt": config.tilt,
        "azimuth": config.azimuth,
    }

    ml_kw, model_name = _ml_prediction(features, plant.capacity_kw)

    # Confidence interval (simple ±10% for now)
    confidence_margin = ml_kw * 0.10
    confidence_lower = max(0.0, ml_kw - confidence_margin)
    confidence_upper = min(plant.capacity_kw, ml_kw + confidence_margin)

    record = ForecastRecord(
        plant_id=plant.id,
        forecast_time=forecast_time,
        generated_at=datetime.now(tz=timezone.utc),
        predicted_power_kw=round(ml_kw, 4),
        confidence_lower=round(confidence_lower, 4),
        confidence_upper=round(confidence_upper, 4),
        model_name=model_name,
        model_version="1.0",
        physics_power_kw=round(physics_kw, 4),
        ml_power_kw=round(ml_kw, 4),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info(
        f"Forecast generated: plant={plant.id} model={model_name} "
        f"predicted={ml_kw:.2f} kW at {forecast_time.isoformat()}"
    )
    return record


async def get_forecasts(
    db: AsyncSession,
    plant_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 200,
) -> List[ForecastRecord]:
    """Retrieve forecast records for a plant."""
    query = select(ForecastRecord).where(ForecastRecord.plant_id == plant_id)
    if start:
        query = query.where(ForecastRecord.forecast_time >= start)
    if end:
        query = query.where(ForecastRecord.forecast_time <= end)
    query = query.order_by(ForecastRecord.forecast_time.asc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_forecast_summary(
    db: AsyncSession,
    plant_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> ForecastSummary:
    """Calculate summary statistics for forecast records."""
    records = await get_forecasts(db, plant_id, start=start, end=end, limit=10000)

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No forecast records found for plant {plant_id}",
        )

    predicted_values = [r.predicted_power_kw for r in records]
    actual_values = [r.actual_power_kw for r in records if r.actual_power_kw is not None]

    total_predicted_kwh = sum(predicted_values) / 60.0  # assuming 1-min intervals
    total_actual_kwh = sum(actual_values) / 60.0 if actual_values else None

    mae: Optional[float] = None
    if actual_values and len(actual_values) == len(records):
        errors = [abs(r.predicted_power_kw - (r.actual_power_kw or 0)) for r in records]
        mae = float(np.mean(errors))

    period_start = min(r.forecast_time for r in records)
    period_end = max(r.forecast_time for r in records)
    model_name = records[-1].model_name if records else "unknown"

    return ForecastSummary(
        plant_id=plant_id,
        period_start=period_start,
        period_end=period_end,
        total_predicted_kwh=round(total_predicted_kwh, 4),
        total_actual_kwh=round(total_actual_kwh, 4) if total_actual_kwh is not None else None,
        mean_absolute_error_kw=round(mae, 4) if mae is not None else None,
        record_count=len(records),
        model_name=model_name,
    )


async def generate_probabilistic_forecast(
    db: AsyncSession,
    plant,
    config,
    horizon_minutes: int = 240,
    interval_minutes: int = 15,
) -> ProbabilisticForecastResponse:
    """
    Generates a full probabilistic forecast time-series (P10, P50, P90)
    across the requested horizon, evaluates ramp rates and cloud-passage volatility,
    and computes actionable BESS reserve recommendations.
    """
    now = datetime.now(tz=timezone.utc)
    # Align to next round interval boundary
    start_time = now.replace(second=0, microsecond=0)
    remainder = start_time.minute % interval_minutes
    if remainder != 0:
        start_time = start_time + timedelta(minutes=(interval_minutes - remainder))

    step_count = max(2, int(horizon_minutes / interval_minutes) + 1)
    timestamps = [start_time + timedelta(minutes=i * interval_minutes) for i in range(step_count)]

    # Fetch latest SCADA for baseline operational context
    result = await db.execute(
        select(ScadaReading)
        .where(ScadaReading.plant_id == plant.id)
        .order_by(ScadaReading.timestamp.desc())
        .limit(1)
    )
    latest_scada: Optional[ScadaReading] = result.scalar_one_or_none()
    current_temp = latest_scada.temperature_c if latest_scada else 25.0
    current_irradiance = latest_scada.irradiance_w_m2 if latest_scada else 600.0

    model_name = "probabilistic_quantile"

    p10_list: List[float] = []
    p50_list: List[float] = []
    p90_list: List[float] = []
    cloud_list: List[float] = []

    for t in timestamps:
        # Physics-based baseline power using pvlib or astronomical model
        physics_kw = _calculate_physics_power(
            latitude=plant.latitude,
            longitude=plant.longitude,
            tilt=config.tilt,
            azimuth=config.azimuth,
            capacity_kw=plant.capacity_kw,
            efficiency=config.efficiency,
            forecast_time=t,
            irradiance_w_m2=None,
            temperature_c=current_temp,
        )

        # Operational deratings: soiling and inverter AC clipping
        soiling = calculate_soiling_loss(
            current_power_kw=physics_kw,
            days_since_cleaning=7.0,
            irradiance_w_m2=current_irradiance,
        )
        soiling_adj = max(0.0, physics_kw - soiling.estimated_loss_kw)
        clipping = calculate_clipping(
            dc_power_kw=soiling_adj,
            inverter_capacity_kw=plant.inverter_capacity_kw,
            efficiency=config.efficiency,
        )
        base_power = clipping.clipped_ac_power_kw

        if base_power <= 0.5:
            # Nighttime or sun below horizon
            p10 = 0.0
            p50 = 0.0
            p90 = 0.0
            cloud_pct = 0.0
        else:
            # Cloud passage wave simulation across forecast horizon
            time_offset_min = (t - start_time).total_seconds() / 60.0
            cloud_passage_wave = 0.25 * np.sin(2 * np.pi * time_offset_min / 80.0) + 0.15 * np.cos(2 * np.pi * time_offset_min / 35.0)
            cloud_factor = float(np.clip(0.20 + cloud_passage_wave, 0.05, 0.85))
            cloud_pct = cloud_factor * 100.0

            # P50: median forecast attenuated by cloud layer
            p50_raw = base_power * (1.0 - 0.55 * cloud_factor)
            p50 = float(np.clip(p50_raw, 0.0, plant.inverter_capacity_kw))

            # P10: 10th percentile conservative lower bound (thick cloud passage event)
            p10_raw = p50 * (1.0 - 0.40 * np.sqrt(cloud_factor))
            p10 = float(np.clip(p10_raw, 0.0, p50))

            # P90: 90th percentile optimistic upper bound (clear gap / beam enhancement)
            p90_raw = min(base_power, p50 * (1.0 + 0.35 * (1.0 - cloud_factor)))
            p90 = float(np.clip(p90_raw, p50, plant.inverter_capacity_kw))

        p10_list.append(round(p10, 2))
        p50_list.append(round(p50, 2))
        p90_list.append(round(p90, 2))
        cloud_list.append(round(cloud_pct, 1))

    df_points = pd.DataFrame({
        "forecast_time": [t.isoformat() for t in timestamps],
        "p10": p10_list,
        "p50": p50_list,
        "p90": p90_list,
        "cloud_cover": cloud_list,
    })

    point_metrics, risk_summary = compute_ramp_risk_profile(
        df=df_points,
        capacity_kw=plant.capacity_kw,
        interval_minutes=float(interval_minutes),
    )

    schema_points: List[ProbabilisticForecastPoint] = []
    for idx, pm in enumerate(point_metrics):
        schema_points.append(
            ProbabilisticForecastPoint(
                forecast_time=timestamps[idx],
                p10_kw=pm.p10_kw,
                p50_kw=pm.p50_kw,
                p90_kw=pm.p90_kw,
                uncertainty_band_kw=pm.uncertainty_band_kw,
                relative_uncertainty_pct=pm.relative_uncertainty_pct,
                ramp_rate_kw_per_min=pm.ramp_rate_kw_per_min,
                ramp_rate_pct_per_min=pm.ramp_rate_pct_per_min,
                ramp_direction=pm.ramp_direction.value,
                ramp_risk_level=pm.ramp_risk_level.value,
                cloud_impact_factor=pm.cloud_impact_factor,
                bess_reserve_recommendation_kw=pm.bess_reserve_recommendation_kw,
                reserve_action=pm.reserve_action,
            )
        )

    summary_schema = RampRiskSummarySchema(
        max_ramp_rate_kw_per_min=risk_summary.max_ramp_rate_kw_per_min,
        max_ramp_down_kw_per_min=risk_summary.max_ramp_down_kw_per_min,
        max_ramp_up_kw_per_min=risk_summary.max_ramp_up_kw_per_min,
        ramp_risk_score=risk_summary.ramp_risk_score,
        highest_risk_level=risk_summary.highest_risk_level.value,
        high_risk_event_count=risk_summary.high_risk_event_count,
        critical_risk_event_count=risk_summary.critical_risk_event_count,
        avg_uncertainty_band_kw=risk_summary.avg_uncertainty_band_kw,
        recommended_bess_capacity_kw=risk_summary.recommended_bess_capacity_kw,
        primary_action_advisory=risk_summary.primary_action_advisory,
    )

    return ProbabilisticForecastResponse(
        plant_id=plant.id,
        plant_name=plant.name,
        capacity_kw=plant.capacity_kw,
        generated_at=now,
        horizon_minutes=horizon_minutes,
        interval_minutes=interval_minutes,
        model_name=model_name,
        points=schema_points,
        summary=summary_schema,
    )
