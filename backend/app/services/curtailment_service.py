"""
app/services/curtailment_service.py

Grid Curtailment Prediction & Optimization Service (Enhancement 6).

Predicts when forecasted solar generation will exceed configured AC grid/export capacity limits,
estimates expected active power curtailment (kW) and energy loss (kWh), determines curtailment risk,
and provides intelligent decision-support recommendations (including BESS charging opportunities).

Safety & Decision Support:
- This service operates strictly as operational DECISION SUPPORT.
- It does NOT directly command or actuate physical inverters, grid breakers, or batteries.
- Incorporates existing clipping and forecast data without duplicating calculation engines.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.curtailment import CurtailmentRecord
from app.models.forecast import ForecastRecord
from app.models.plant import Plant, PlantConfig
from app.schemas.curtailment import (
    CurtailmentHourlyPoint,
    CurtailmentPredictionResponse,
    CurtailmentRecordResponse,
    CurtailmentRiskLevel,
)
from app.services import forecast_service

logger = get_logger(__name__)


def calculate_single_curtailment(
    forecast_generation_kw: float,
    export_limit_kw: float,
    duration_hours: float = 1.0,
) -> Tuple[float, float, float, bool]:
    """
    Calculate active power curtailment (kW), energy loss (kWh), and percentage for one step.

    Returns
    -------
    (potential_curtailment_kw, potential_curtailment_kwh, curtailment_percentage, is_curtailed)
    """
    forecast_kw = max(0.0, float(forecast_generation_kw))
    limit_kw = max(0.0, float(export_limit_kw))

    if forecast_kw > limit_kw:
        curtailed_kw = forecast_kw - limit_kw
        curtailed_kwh = curtailed_kw * duration_hours
        pct = (curtailed_kw / forecast_kw * 100.0) if forecast_kw > 0 else 0.0
        return round(curtailed_kw, 2), round(curtailed_kwh, 2), round(pct, 2), True
    else:
        return 0.0, 0.0, 0.0, False


def classify_curtailment_risk(
    curtailment_percentage: float,
    curtailed_kw: float,
) -> CurtailmentRiskLevel:
    """Classify curtailment severity into LOW, MEDIUM, or HIGH."""
    if curtailed_kw <= 0.0 or curtailment_percentage < settings.CURTAILMENT_RISK_MEDIUM_THRESHOLD_PCT:
        return "LOW"
    elif curtailment_percentage < settings.CURTAILMENT_RISK_HIGH_THRESHOLD_PCT:
        return "MEDIUM"
    else:
        return "HIGH"


def generate_curtailment_recommendation(
    risk_level: CurtailmentRiskLevel,
    curtailed_kw: float,
    curtailed_kwh: float,
    export_limit_kw: float,
    peak_time_str: Optional[str] = None,
) -> str:
    """Generate contextual decision-support recommendation."""
    if risk_level == "HIGH":
        time_hint = f" around {peak_time_str}" if peak_time_str else ""
        return (
            f"HIGH Curtailment Risk: Predicted excess generation reaches {curtailed_kw:.1f} kW "
            f"({curtailed_kwh:.1f} kWh total loss){time_hint}. "
            "Actionable recommendations: 1) Schedule co-located BESS battery charging to absorb peak surplus; "
            "2) Dispatch flexible on-site auxiliary loads; "
            "3) Pre-emptively stage inverter active power ramp curtailment to satisfy grid interconnection rules."
        )
    elif risk_level == "MEDIUM":
        return (
            f"MODERATE Curtailment Risk: Projected peak surplus of {curtailed_kw:.1f} kW "
            f"({curtailed_kwh:.1f} kWh loss). "
            "Recommendation: Consider partial battery storage charging during peak generation window "
            "and verify inverter ramp-rate governor limits."
        )
    else:
        return (
            f"LOW Curtailment Risk: Forecasted power remains safely within the permitted grid export limit "
            f"({export_limit_kw:.1f} kW). Standard export schedule maintained without energy discard."
        )


async def predict_curtailment(
    db: AsyncSession,
    plant_id: int,
    export_limit_kw: Optional[float] = None,
    horizon_hours: int = 24,
    persist: bool = True,
) -> CurtailmentPredictionResponse:
    """
    Predict grid curtailment over a multi-hour forecast horizon for a plant.
    Integrates actual solar forecasts and export capacity constraints.
    """
    # 1. Fetch plant and plant config
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if plant is None:
        raise ValueError(f"Plant {plant_id} not found")

    # 2. Determine effective export limit
    if export_limit_kw is not None and export_limit_kw > 0:
        effective_export_limit = export_limit_kw
    elif plant.inverter_capacity_kw and plant.inverter_capacity_kw > 0:
        effective_export_limit = plant.inverter_capacity_kw
    else:
        effective_export_limit = plant.capacity_kw * settings.CURTAILMENT_DEFAULT_EXPORT_LIMIT_RATIO

    now = datetime.now(tz=timezone.utc)
    horizon_end = now + timedelta(hours=horizon_hours)

    # 3. Retrieve or generate forecast records for horizon
    forecast_query = (
        select(ForecastRecord)
        .where(
            ForecastRecord.plant_id == plant_id,
            ForecastRecord.forecast_time >= now,
            ForecastRecord.forecast_time <= horizon_end,
        )
        .order_by(ForecastRecord.forecast_time.asc())
    )
    f_res = await db.execute(forecast_query)
    forecast_records = list(f_res.scalars().all())

    # If no future forecast records in DB, construct realistic forecast horizon
    # using physics / capacity curve for the next N hours
    schedule: List[CurtailmentHourlyPoint] = []
    total_forecast_kw = 0.0
    total_curtailment_kw = 0.0
    total_curtailment_kwh = 0.0
    peak_curtailment_kw = 0.0
    peak_curtailment_time: Optional[datetime] = None

    if forecast_records:
        for fr in forecast_records:
            c_kw, c_kwh, c_pct, is_curtailed = calculate_single_curtailment(
                forecast_generation_kw=fr.predicted_power_kw,
                export_limit_kw=effective_export_limit,
                duration_hours=1.0,
            )
            schedule.append(
                CurtailmentHourlyPoint(
                    timestamp=fr.forecast_time,
                    forecast_generation_kw=fr.predicted_power_kw,
                    export_limit_kw=effective_export_limit,
                    potential_curtailment_kw=c_kw,
                    potential_curtailment_kwh=c_kwh,
                    curtailment_percentage=c_pct,
                    is_curtailed=is_curtailed,
                )
            )
            total_forecast_kw += fr.predicted_power_kw
            total_curtailment_kw += c_kw
            total_curtailment_kwh += c_kwh
            if c_kw > peak_curtailment_kw:
                peak_curtailment_kw = c_kw
                peak_curtailment_time = fr.forecast_time
    else:
        # Generate multi-hour schedule based on solar diurnal curve and plant capacity
        for h in range(horizon_hours):
            step_time = now + timedelta(hours=h)
            hour_of_day = step_time.hour
            # Diurnal solar profile between 6:00 and 18:00
            if 6 <= hour_of_day <= 18:
                solar_factor = max(0.0, np.sin(np.pi * (hour_of_day - 6.0) / 12.0))
                # Add slight operational midday peaking
                sim_power = round(plant.capacity_kw * (solar_factor ** 1.2), 2)
            else:
                sim_power = 0.0

            c_kw, c_kwh, c_pct, is_curtailed = calculate_single_curtailment(
                forecast_generation_kw=sim_power,
                export_limit_kw=effective_export_limit,
                duration_hours=1.0,
            )
            schedule.append(
                CurtailmentHourlyPoint(
                    timestamp=step_time,
                    forecast_generation_kw=sim_power,
                    export_limit_kw=effective_export_limit,
                    potential_curtailment_kw=c_kw,
                    potential_curtailment_kwh=c_kwh,
                    curtailment_percentage=c_pct,
                    is_curtailed=is_curtailed,
                )
            )
            total_forecast_kw += sim_power
            total_curtailment_kw += c_kw
            total_curtailment_kwh += c_kwh
            if c_kw > peak_curtailment_kw:
                peak_curtailment_kw = c_kw
                peak_curtailment_time = step_time

    # 4. Overall metrics
    overall_pct = (
        (total_curtailment_kwh / total_forecast_kw * 100.0)
        if total_forecast_kw > 0
        else 0.0
    )
    overall_pct = round(overall_pct, 2)
    risk_level = classify_curtailment_risk(overall_pct, peak_curtailment_kw)

    peak_time_str = peak_curtailment_time.strftime("%H:%M UTC") if peak_curtailment_time else None
    recommendation = generate_curtailment_recommendation(
        risk_level=risk_level,
        curtailed_kw=peak_curtailment_kw,
        curtailed_kwh=total_curtailment_kwh,
        export_limit_kw=effective_export_limit,
        peak_time_str=peak_time_str,
    )

    # 5. BESS Opportunity Analysis (Decision support)
    bess_opportunity: Optional[Dict[str, Any]] = None
    if peak_curtailment_kw > 0:
        bess_opportunity = {
            "recommended_charging_power_kw": peak_curtailment_kw,
            "absorbable_energy_kwh": total_curtailment_kwh,
            "optimal_charge_window": (
                f"{schedule[0].timestamp.strftime('%H:%M')} - "
                f"{(schedule[0].timestamp + timedelta(hours=len(schedule))).strftime('%H:%M UTC')}"
            ),
            "status": "DECISION_SUPPORT_ACTIVE",
            "dispatch_note": (
                f"A battery energy storage system sized at ~{peak_curtailment_kw:.0f} kW / "
                f"{total_curtailment_kwh:.0f} kWh could capture 100% of otherwise discarded solar energy."
            ),
        }

    # Representative point for summary view (peak or current)
    summary_forecast_kw = round(peak_curtailment_kw + effective_export_limit if peak_curtailment_kw > 0 else (schedule[0].forecast_generation_kw if schedule else 0.0), 2)

    # 6. Persistence
    if persist:
        record = CurtailmentRecord(
            plant_id=plant_id,
            forecast_time=peak_curtailment_time or now,
            forecast_generation_kw=summary_forecast_kw,
            export_limit_kw=effective_export_limit,
            potential_curtailment_kw=round(peak_curtailment_kw, 2),
            potential_curtailment_kwh=round(total_curtailment_kwh, 2),
            curtailment_percentage=overall_pct,
            risk_level=risk_level,
            recommendation=recommendation,
            created_at=now,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info(
            f"Curtailment prediction persisted: plant={plant_id} "
            f"peak_curtailment={peak_curtailment_kw:.1f} kW risk={risk_level}"
        )

    return CurtailmentPredictionResponse(
        plant_id=plant_id,
        forecast_generation_kw=summary_forecast_kw,
        export_limit_kw=round(effective_export_limit, 2),
        potential_curtailment_kw=round(peak_curtailment_kw, 2),
        potential_curtailment_kwh=round(total_curtailment_kwh, 2),
        curtailment_percentage=overall_pct,
        risk_level=risk_level,
        recommendation=recommendation,
        schedule=schedule,
        bess_opportunity=bess_opportunity,
        assessed_at=now,
    )


async def get_curtailment_history(
    db: AsyncSession,
    plant_id: int,
    limit: int = 50,
) -> List[CurtailmentRecordResponse]:
    """Retrieve historical curtailment prediction records for auditing."""
    result = await db.execute(
        select(CurtailmentRecord)
        .where(CurtailmentRecord.plant_id == plant_id)
        .order_by(CurtailmentRecord.created_at.desc())
        .limit(limit)
    )
    records = list(result.scalars().all())

    return [
        CurtailmentRecordResponse(
            id=r.id,
            plant_id=r.plant_id,
            forecast_time=r.forecast_time,
            forecast_generation_kw=r.forecast_generation_kw,
            export_limit_kw=r.export_limit_kw,
            potential_curtailment_kw=r.potential_curtailment_kw,
            potential_curtailment_kwh=r.potential_curtailment_kwh,
            curtailment_percentage=r.curtailment_percentage,
            risk_level=r.risk_level,
            recommendation=r.recommendation,
            created_at=r.created_at,
        )
        for r in records
    ]
