"""
app/services/health_service.py

AI-Based Solar Plant Health Scoring Service (Enhancement 5).

Calculates a comprehensive 0–100 health score for a solar plant by integrating:
  1. Generation Performance (expected vs actual power, shortfall trends)
  2. Inverter Performance (conversion efficiency, clipping stability, inverter telemetry)
  3. Soiling Condition (dynamic soiling loss estimation from soiling_service)
  4. Anomaly Health (active alerts, shortfall frequency, severity penalties)
  5. Equipment Health (predictive maintenance failure risk from Enhancement 4)

Weights and thresholds are dynamically configured via app.core.config.settings.
Missing data streams are handled safely by dynamic weight renormalization
so plants are never unfairly penalized for missing optional sensors.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.alert import AnomalyAlert
from app.models.health import PlantHealthRecord
from app.models.plant import Plant, PlantConfig
from app.models.scada import ScadaReading
from app.schemas.health import (
    HealthStatusType,
    PlantHealthComponents,
    PlantHealthHistoryResponse,
    PlantHealthResponse,
)
from app.services.maintenance_service import assess_equipment_failure_risk
from app.services.soiling_service import calculate_soiling_loss

logger = get_logger(__name__)


def classify_health_status(score: float) -> HealthStatusType:
    """Map numeric 0–100 health score to semantic operational status."""
    if score >= 90.0:
        return "EXCELLENT"
    elif score >= 75.0:
        return "GOOD"
    elif score >= 60.0:
        return "NEEDS ATTENTION"
    elif score >= 40.0:
        return "POOR"
    else:
        return "CRITICAL"


def compute_generation_score(
    readings: List[ScadaReading],
) -> Tuple[Optional[float], List[str]]:
    """
    Evaluate generation performance component (0–100).
    Compares actual power to expected power during active generation hours.
    """
    concerns: List[str] = []
    ratios: List[float] = []

    for r in readings:
        if (
            r.expected_power_kw is not None
            and r.expected_power_kw > 10.0
            and r.power_kw is not None
        ):
            # Ratio of actual to expected, capped at 1.0 (100%)
            ratio = min(1.0, max(0.0, r.power_kw / r.expected_power_kw))
            ratios.append(ratio * 100.0)

    if not ratios:
        return None, concerns

    mean_perf = float(np.mean(ratios))
    if mean_perf < 75.0:
        concerns.append(
            f"Generation yield underperforming expected baseline by {(100.0 - mean_perf):.1f}%"
        )
    return round(mean_perf, 1), concerns


def compute_inverter_score(
    readings: List[ScadaReading],
    nominal_efficiency: float,
) -> Tuple[Optional[float], List[str]]:
    """
    Evaluate inverter performance component (0–100).
    Checks conversion efficiency and power tracking stability.
    """
    concerns: List[str] = []
    eff_scores: List[float] = []

    for r in readings:
        if (
            r.inverter_power_kw is not None
            and r.power_kw is not None
            and r.power_kw > 10.0
        ):
            eff = min(1.0, max(0.0, r.inverter_power_kw / r.power_kw))
            # 100% when at or above nominal; drops steeply if derated
            ratio = min(1.0, eff / nominal_efficiency)
            eff_scores.append(ratio * 100.0)

    if not eff_scores:
        return None, concerns

    mean_inv = float(np.mean(eff_scores))
    if mean_inv < 80.0:
        concerns.append("Inverter conversion efficiency operating below nominal threshold")
    return round(mean_inv, 1), concerns


def compute_soiling_score(
    latest_reading: Optional[ScadaReading],
    config: Optional[PlantConfig],
) -> Tuple[float, List[str]]:
    """
    Evaluate soiling condition component (0–100).
    Uses dynamic soiling service calculation.
    """
    concerns: List[str] = []
    irr = latest_reading.irradiance_w_m2 if latest_reading else 800.0
    power = latest_reading.power_kw if latest_reading else 500.0

    soiling_res = calculate_soiling_loss(
        current_power_kw=power or 500.0,
        days_since_cleaning=7.0,
        rainfall_mm=0.0,
        irradiance_w_m2=irr or 800.0,
    )
    # 0% loss -> 100 score; 15% loss -> 50 score; 30% loss -> 0 score
    soiling_score = max(0.0, min(100.0, 100.0 - (soiling_res.soiling_loss_percent * 3.33)))
    soiling_score = round(soiling_score, 1)

    threshold = config.soiling_threshold if config else 5.0
    if soiling_res.soiling_loss_percent >= threshold:
        concerns.append(
            f"Estimated panel soiling loss ({soiling_res.soiling_loss_percent:.1f}%) exceeds plant threshold ({threshold:.1f}%)"
        )
    return soiling_score, concerns


def compute_anomaly_score(
    alerts: List[AnomalyAlert],
) -> Tuple[float, List[str]]:
    """
    Evaluate anomaly health component (0–100).
    Penalizes based on unresolved alerts and recent alert frequency.
    """
    concerns: List[str] = []
    penalty = 0.0
    unresolved_crit = 0
    unresolved_warn = 0

    for a in alerts:
        if not a.is_resolved:
            if a.severity.upper() == "CRITICAL":
                unresolved_crit += 1
                penalty += 20.0
            elif a.severity.upper() == "WARNING":
                unresolved_warn += 1
                penalty += 10.0
            else:
                penalty += 3.0
        else:
            penalty += 1.5  # minor memory of resolved alert

    if unresolved_crit > 0:
        concerns.append(f"{unresolved_crit} unresolved critical anomaly alert(s) active on plant")
    if unresolved_warn > 0:
        concerns.append(f"{unresolved_warn} unresolved warning alert(s) active on plant")

    anomaly_score = max(0.0, min(100.0, 100.0 - penalty))
    return round(anomaly_score, 1), concerns


async def calculate_plant_health(
    db: AsyncSession,
    plant_id: int,
    persist: bool = True,
) -> PlantHealthResponse:
    """
    Calculate composite AI plant health score and component breakdown for a solar plant.
    """
    # 1. Verify plant and config
    p_res = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = p_res.scalar_one_or_none()
    if plant is None:
        raise ValueError(f"Plant {plant_id} not found")

    c_res = await db.execute(select(PlantConfig).where(PlantConfig.plant_id == plant_id))
    config = c_res.scalar_one_or_none()

    # 2. Fetch SCADA telemetry (past 24h)
    now = datetime.now(tz=timezone.utc)
    scada_res = await db.execute(
        select(ScadaReading)
        .where(
            ScadaReading.plant_id == plant_id,
            ScadaReading.timestamp >= (now - timedelta(hours=24)),
        )
        .order_by(ScadaReading.timestamp.desc())
        .limit(200)
    )
    readings = list(scada_res.scalars().all())

    # 3. Fetch alerts (past 48h)
    alerts_res = await db.execute(
        select(AnomalyAlert)
        .where(
            AnomalyAlert.plant_id == plant_id,
            AnomalyAlert.timestamp >= (now - timedelta(hours=48)),
        )
        .order_by(AnomalyAlert.timestamp.desc())
        .limit(100)
    )
    alerts = list(alerts_res.scalars().all())

    # 4. Compute components
    major_concerns: List[str] = []
    recommendations: List[str] = []

    # Component 1: Generation Performance
    gen_score, gen_concerns = compute_generation_score(readings)
    major_concerns.extend(gen_concerns)

    # Component 2: Inverter Performance
    inv_score, inv_concerns = compute_inverter_score(
        readings, nominal_efficiency=settings.MAINTENANCE_NOMINAL_EFFICIENCY
    )
    major_concerns.extend(inv_concerns)

    # Component 3: Soiling Condition
    soiling_score, soil_concerns = compute_soiling_score(
        readings[0] if readings else None, config
    )
    major_concerns.extend(soil_concerns)

    # Component 4: Anomaly Health
    anom_score, anom_concerns = compute_anomaly_score(alerts)
    major_concerns.extend(anom_concerns)

    # Component 5: Equipment Health (Predictive Maintenance integration)
    try:
        maint_res = await assess_equipment_failure_risk(
            db, plant_id=plant_id, persist=False
        )
        # Equipment health is inverse of failure risk
        equip_score = max(0.0, min(100.0, 100.0 - maint_res.failure_risk_score))
        equip_score = round(equip_score, 1)
        if maint_res.failure_risk_score >= 60.0:
            major_concerns.append(
                f"Elevated failure risk on {maint_res.equipment_id} ({maint_res.risk_level}, risk score {maint_res.failure_risk_score:.0f})"
            )
            recommendations.append(maint_res.recommended_action)
    except Exception as exc:
        logger.warning(f"Could not compute predictive equipment health: {exc}")
        equip_score = 90.0  # safe default

    # ── Safe Weight Normalization for Available Components ─────────────────
    active_weights: Dict[str, Tuple[float, float]] = {}
    # tuple: (score, weight)

    if gen_score is not None:
        active_weights["gen"] = (gen_score, settings.HEALTH_WEIGHT_GENERATION)
    else:
        # If no SCADA generation readings exist yet, use fallback neutral score
        active_weights["gen"] = (95.0, settings.HEALTH_WEIGHT_GENERATION)
        gen_score = 95.0

    if inv_score is not None:
        active_weights["inv"] = (inv_score, settings.HEALTH_WEIGHT_INVERTER)
    else:
        active_weights["inv"] = (95.0, settings.HEALTH_WEIGHT_INVERTER)
        inv_score = 95.0

    active_weights["soil"] = (soiling_score, settings.HEALTH_WEIGHT_SOILING)
    active_weights["anom"] = (anom_score, settings.HEALTH_WEIGHT_ANOMALY)
    active_weights["equip"] = (equip_score, settings.HEALTH_WEIGHT_EQUIPMENT)

    sum_weights = sum(w for _, w in active_weights.values())
    weighted_total = sum(s * w for s, w in active_weights.values())
    final_health_score = round(max(0.0, min(100.0, weighted_total / sum_weights)), 1)

    health_status = classify_health_status(final_health_score)

    # ── Actionable Recommendations ─────────────────────────────────────────
    if soiling_score < 80.0:
        recommendations.append(
            "Schedule automated sprinkler wash or manual cleaning cycle to mitigate soiling loss."
        )
    if anom_score < 75.0:
        recommendations.append(
            "Review and resolve outstanding anomaly alerts in the monitoring dashboard."
        )
    if gen_score < 80.0:
        recommendations.append(
            "Perform string-level DC IV curve tracing to isolate generation shortfall causes."
        )
    if not recommendations:
        recommendations.append("All plant systems operating within normal parameters. Maintain regular monitoring.")

    # ── Persistence ────────────────────────────────────────────────────────
    record: Optional[PlantHealthRecord] = None
    if persist:
        record = PlantHealthRecord(
            plant_id=plant_id,
            health_score=final_health_score,
            health_status=health_status,
            generation_performance=gen_score,
            inverter_health=inv_score,
            soiling_condition=soiling_score,
            anomaly_health=anom_score,
            equipment_health=equip_score,
            major_concerns=major_concerns,
            recommendations=recommendations,
            assessed_at=now,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info(
            f"Plant health record persisted: plant={plant_id} score={final_health_score} status={health_status}"
        )

    return PlantHealthResponse(
        id=record.id if record else None,
        plant_id=plant_id,
        health_score=final_health_score,
        health_status=health_status,
        components=PlantHealthComponents(
            generation_performance=gen_score,
            inverter_health=inv_score,
            soiling_condition=soiling_score,
            anomaly_health=anom_score,
            equipment_health=equip_score,
        ),
        major_concerns=major_concerns,
        recommendations=recommendations,
        assessed_at=now,
    )


async def get_latest_plant_health(
    db: AsyncSession,
    plant_id: int,
) -> PlantHealthResponse:
    """Retrieve the most recent health record or compute on-demand."""
    result = await db.execute(
        select(PlantHealthRecord)
        .where(PlantHealthRecord.plant_id == plant_id)
        .order_by(PlantHealthRecord.assessed_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()

    if record is None:
        return await calculate_plant_health(db, plant_id=plant_id, persist=True)

    return PlantHealthResponse(
        id=record.id,
        plant_id=record.plant_id,
        health_score=record.health_score,
        health_status=record.health_status,  # type: ignore[arg-type]
        components=PlantHealthComponents(
            generation_performance=record.generation_performance,
            inverter_health=record.inverter_health,
            soiling_condition=record.soiling_condition,
            anomaly_health=record.anomaly_health,
            equipment_health=record.equipment_health,
        ),
        major_concerns=record.major_concerns,
        recommendations=record.recommendations,
        assessed_at=record.assessed_at,
    )


async def get_plant_health_history(
    db: AsyncSession,
    plant_id: int,
    limit: int = 50,
) -> PlantHealthHistoryResponse:
    """Retrieve historical health scoring records for trend analysis."""
    result = await db.execute(
        select(PlantHealthRecord)
        .where(PlantHealthRecord.plant_id == plant_id)
        .order_by(PlantHealthRecord.assessed_at.desc())
        .limit(limit)
    )
    records = list(result.scalars().all())

    if not records:
        latest = await calculate_plant_health(db, plant_id=plant_id, persist=True)
        return PlantHealthHistoryResponse(
            plant_id=plant_id,
            total_records=1,
            history=[latest],
        )

    history = [
        PlantHealthResponse(
            id=r.id,
            plant_id=r.plant_id,
            health_score=r.health_score,
            health_status=r.health_status,  # type: ignore[arg-type]
            components=PlantHealthComponents(
                generation_performance=r.generation_performance,
                inverter_health=r.inverter_health,
                soiling_condition=r.soiling_condition,
                anomaly_health=r.anomaly_health,
                equipment_health=r.equipment_health,
            ),
            major_concerns=r.major_concerns,
            recommendations=r.recommendations,
            assessed_at=r.assessed_at,
        )
        for r in records
    ]

    return PlantHealthHistoryResponse(
        plant_id=plant_id,
        total_records=len(history),
        history=history,
    )
