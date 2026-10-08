"""
app/services/maintenance_service.py

Predictive Maintenance and Equipment Failure Risk Forecasting Service (Enhancement 4).

Analyzes operational SCADA parameters, inverter conversion efficiency, thermal stress,
and anomaly history to estimate failure risk BEFORE physical equipment failure occurs.

ML / Risk Engine Strategy:
- As verified, no labelled historical equipment failure dataset exists in the repository.
- This service implements a transparent, domain-grounded operational risk-scoring engine
  behind the FailureRiskPredictorBase interface.
- Architecture is designed for drop-in replacement with a trained ML classifier (e.g., LightGBM / XGBoost)
  once labeled maintenance/fault event logs become available.
- Safety & Decision Support: The system produces probability/risk indicators and actionable
  recommendations. It never claims confirmed physical diagnosis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.alert import AnomalyAlert
from app.models.maintenance import EquipmentMaintenanceAssessment
from app.models.plant import Plant
from app.models.scada import ScadaReading
from app.schemas.maintenance import (
    HighRiskEquipmentResponse,
    MaintenanceAssessmentResponse,
    MaintenanceRecommendationItem,
    MaintenanceRecommendationResponse,
    RiskLevelType,
)

logger = get_logger(__name__)


# ── Predictor Interface & Operational Engine ─────────────────────────────────


class FailureRiskPredictorBase(ABC):
    """Abstract base class for equipment failure risk predictors."""

    @abstractmethod
    def predict_risk(
        self,
        equipment_id: str,
        readings: List[ScadaReading],
        alerts: List[AnomalyAlert],
        nominal_efficiency: float,
        rated_capacity_kw: float,
    ) -> Dict[str, Any]:
        """Compute failure risk score, level, warning, factors, and metrics."""
        pass


class OperationalRiskScorer(FailureRiskPredictorBase):
    """
    Transparent, physics- and operational-indicator grounded risk scoring engine.
    Evaluates 4 core operational dimensions:
      1. Thermal stress (ambient and module temperature derating)
      2. Inverter conversion efficiency degradation
      3. Generation shortfall & deviation persistence
      4. Anomaly alert frequency & severity history
    """

    def predict_risk(
        self,
        equipment_id: str,
        readings: List[ScadaReading],
        alerts: List[AnomalyAlert],
        nominal_efficiency: float = 0.96,
        rated_capacity_kw: float = 1000.0,
    ) -> Dict[str, Any]:
        contributing_factors: List[str] = []
        metrics: Dict[str, Any] = {}

        # ── 1. Thermal Stress Evaluation ─────────────────────────────────────
        thermal_scores: List[float] = []
        max_mod_temp: Optional[float] = None
        max_amb_temp: Optional[float] = None

        for r in readings:
            if r.module_temperature_c is not None:
                max_mod_temp = max(max_mod_temp or -999.0, r.module_temperature_c)
                # Over 45°C starts elevated derating; >65°C is critical thermal stress
                t_score = max(0.0, min(100.0, (r.module_temperature_c - 45.0) / 25.0 * 100.0))
                thermal_scores.append(t_score)
            elif r.temperature_c is not None:
                max_amb_temp = max(max_amb_temp or -999.0, r.temperature_c)
                # Over 38°C ambient is high thermal burden
                t_score = max(0.0, min(100.0, (r.temperature_c - 35.0) / 15.0 * 100.0))
                thermal_scores.append(t_score)

        if thermal_scores:
            thermal_risk = float(np.mean(thermal_scores))
            if max_mod_temp is not None and max_mod_temp >= settings.MAINTENANCE_CRITICAL_TEMP_C:
                thermal_risk = max(thermal_risk, 80.0)
                contributing_factors.append(
                    f"Severe module operating temperature recorded ({max_mod_temp:.1f}°C, threshold {settings.MAINTENANCE_CRITICAL_TEMP_C:.1f}°C)"
                )
            elif thermal_risk >= 50.0:
                contributing_factors.append(
                    f"Elevated operating temperature derating detected (peak {max_mod_temp or max_amb_temp:.1f}°C)"
                )
        else:
            thermal_risk = 0.0  # Safe default if no temperature telemetry

        metrics["thermal_risk_score"] = round(thermal_risk, 2)
        metrics["max_module_temp_c"] = max_mod_temp
        metrics["max_ambient_temp_c"] = max_amb_temp

        # ── 2. Inverter Efficiency Degradation ────────────────────────────────
        efficiency_scores: List[float] = []
        observed_efficiencies: List[float] = []

        for r in readings:
            # Check inverter power vs DC / expected power
            if r.inverter_power_kw is not None and r.power_kw is not None and r.power_kw > 10.0:
                eff = min(1.0, max(0.0, r.inverter_power_kw / r.power_kw))
                observed_efficiencies.append(eff)
                # Compare against nominal efficiency (e.g. 0.96)
                if eff < nominal_efficiency:
                    derate_pct = (nominal_efficiency - eff) / nominal_efficiency * 100.0
                    eff_score = max(0.0, min(100.0, derate_pct * 10.0))
                    efficiency_scores.append(eff_score)
                else:
                    efficiency_scores.append(0.0)

        if efficiency_scores:
            eff_risk = float(np.mean(efficiency_scores))
            mean_eff = float(np.mean(observed_efficiencies))
            metrics["mean_observed_efficiency"] = round(mean_eff, 4)
            if mean_eff < (nominal_efficiency * 0.90):
                eff_risk = max(eff_risk, 80.0)
                contributing_factors.append(
                    f"Substantial inverter conversion degradation (observed {mean_eff * 100:.1f}%, nominal {nominal_efficiency * 100:.1f}%)"
                )
            elif eff_risk >= 40.0:
                contributing_factors.append(
                    f"Inverter conversion efficiency derate (observed {mean_eff * 100:.1f}%)"
                )
        else:
            eff_risk = 0.0
            metrics["mean_observed_efficiency"] = nominal_efficiency

        metrics["efficiency_derate_score"] = round(eff_risk, 2)

        # ── 3. Generation Shortfall & Deviation Persistence ──────────────────
        shortfall_scores: List[float] = []
        shortfall_count = 0

        for r in readings:
            if r.expected_power_kw is not None and r.expected_power_kw > 10.0 and r.power_kw is not None:
                shortfall = max(0.0, (r.expected_power_kw - r.power_kw) / r.expected_power_kw * 100.0)
                if shortfall >= 10.0:
                    shortfall_count += 1
                shortfall_scores.append(min(100.0, shortfall * 2.0))

        if shortfall_scores:
            shortfall_risk = float(np.mean(shortfall_scores))
            if shortfall_count >= 5 or shortfall_risk >= 50.0:
                contributing_factors.append(
                    f"Repeated generation shortfall detected ({shortfall_count} readings with >10% shortfall)"
                )
        else:
            shortfall_risk = 0.0

        metrics["shortfall_persistence_score"] = round(shortfall_risk, 2)
        metrics["shortfall_reading_count"] = shortfall_count

        # ── 4. Anomaly Alert History & Severity ──────────────────────────────
        anomaly_score = 0.0
        unresolved_crit = 0
        unresolved_warn = 0

        for a in alerts:
            if not a.is_resolved:
                if a.severity.upper() == "CRITICAL":
                    unresolved_crit += 1
                    anomaly_score += 30.0
                elif a.severity.upper() == "WARNING":
                    unresolved_warn += 1
                    anomaly_score += 15.0
            else:
                anomaly_score += 3.0  # slight trace from past resolved anomalies

        anomaly_risk = max(0.0, min(100.0, anomaly_score))
        if unresolved_crit > 0:
            contributing_factors.append(
                f"Active unresolved critical anomalies detected ({unresolved_crit} critical alert{'s' if unresolved_crit > 1 else ''})"
            )
        elif unresolved_warn > 0:
            contributing_factors.append(
                f"Active unresolved warning anomalies detected ({unresolved_warn} alert{'s' if unresolved_warn > 1 else ''})"
            )

        metrics["anomaly_severity_score"] = round(anomaly_risk, 2)
        metrics["unresolved_critical_alerts"] = unresolved_crit
        metrics["unresolved_warning_alerts"] = unresolved_warn

        # ── Composite Failure Risk Score ──────────────────────────────────────
        w_t = settings.MAINTENANCE_THERMAL_WEIGHT
        w_e = settings.MAINTENANCE_EFFICIENCY_WEIGHT
        w_s = settings.MAINTENANCE_SHORTFALL_WEIGHT
        w_a = settings.MAINTENANCE_ANOMALY_WEIGHT
        total_w = w_t + w_e + w_s + w_a

        composite_score = (
            w_t * thermal_risk + w_e * eff_risk + w_s * shortfall_risk + w_a * anomaly_risk
        ) / total_w
        composite_score = round(max(0.0, min(100.0, composite_score)), 1)

        # ── Risk Level & Actionable Recommendations ───────────────────────────
        if composite_score >= 80.0:
            risk_level: RiskLevelType = "CRITICAL"
            warning = "Critical failure risk: severe operational anomalies and equipment stress detected"
            recommended_action = (
                "Dispatch maintenance crew for immediate on-site inspection of inverter stage, "
                "DC bus, and cooling system within 24 hours."
            )
        elif composite_score >= 60.0:
            risk_level = "HIGH"
            warning = "High failure risk: abnormal operating pattern and accelerated derating detected"
            recommended_action = (
                "Inspect inverter thermal dissipation and electrical connections within 48 to 72 hours. "
                "Verify string fuses and MPPT stage."
            )
        elif composite_score >= 30.0:
            risk_level = "MEDIUM"
            warning = "Moderate operational deviation: monitor equipment telemetry and thermal performance"
            recommended_action = (
                "Schedule preventative maintenance review. Inspect inverter air filters and "
                "clean dust accumulation during next routine cycle."
            )
        else:
            risk_level = "LOW"
            warning = "Equipment operating within normal operational parameters"
            recommended_action = "Continue regular monitoring and periodic routine maintenance."

        if not contributing_factors:
            contributing_factors.append("Nominal operational telemetry; no significant derating signals")

        return {
            "equipment_id": equipment_id,
            "equipment_type": "inverter",
            "failure_risk_score": composite_score,
            "risk_level": risk_level,
            "warning": warning,
            "contributing_factors": contributing_factors,
            "recommended_action": recommended_action,
            "metrics": metrics,
        }


# Singleton engine instance (extensible to ML model)
_risk_engine: FailureRiskPredictorBase = OperationalRiskScorer()


# ── Database Operations & Orchestration ──────────────────────────────────────


async def assess_equipment_failure_risk(
    db: AsyncSession,
    plant_id: int,
    equipment_id: Optional[str] = None,
    window_hours: int = 24,
    persist: bool = True,
) -> MaintenanceAssessmentResponse:
    """
    Evaluate equipment failure risk for a solar plant.
    Fetches real operational SCADA and anomaly history and runs the risk engine.
    """
    # 1. Verify plant exists
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if plant is None:
        raise ValueError(f"Plant {plant_id} not found")

    target_equipment_id = equipment_id or f"INV-{plant_id:03d}-01"

    # 2. Fetch SCADA telemetry over evaluation window
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    scada_res = await db.execute(
        select(ScadaReading)
        .where(
            ScadaReading.plant_id == plant_id,
            ScadaReading.timestamp >= window_start,
        )
        .order_by(ScadaReading.timestamp.desc())
        .limit(500)
    )
    readings = list(scada_res.scalars().all())

    # 3. Fetch anomaly alerts in window
    alerts_res = await db.execute(
        select(AnomalyAlert)
        .where(
            AnomalyAlert.plant_id == plant_id,
            AnomalyAlert.timestamp >= window_start,
        )
        .order_by(AnomalyAlert.timestamp.desc())
        .limit(100)
    )
    alerts = list(alerts_res.scalars().all())

    # 4. Predict risk
    assessment_data = _risk_engine.predict_risk(
        equipment_id=target_equipment_id,
        readings=readings,
        alerts=alerts,
        nominal_efficiency=settings.MAINTENANCE_NOMINAL_EFFICIENCY,
        rated_capacity_kw=plant.inverter_capacity_kw or plant.capacity_kw,
    )

    assessment_record: Optional[EquipmentMaintenanceAssessment] = None
    if persist:
        assessment_record = EquipmentMaintenanceAssessment(
            plant_id=plant_id,
            equipment_id=assessment_data["equipment_id"],
            equipment_type=assessment_data["equipment_type"],
            failure_risk_score=assessment_data["failure_risk_score"],
            risk_level=assessment_data["risk_level"],
            warning=assessment_data["warning"],
            contributing_factors=assessment_data["contributing_factors"],
            recommended_action=assessment_data["recommended_action"],
            metrics=assessment_data["metrics"],
            assessed_at=now,
        )
        db.add(assessment_record)
        await db.commit()
        await db.refresh(assessment_record)
        logger.info(
            f"Maintenance assessment persisted: plant={plant_id} equip={target_equipment_id} "
            f"score={assessment_data['failure_risk_score']} level={assessment_data['risk_level']}"
        )

    return MaintenanceAssessmentResponse(
        id=assessment_record.id if assessment_record else None,
        plant_id=plant_id,
        equipment_id=assessment_data["equipment_id"],
        equipment_type=assessment_data["equipment_type"],
        failure_risk_score=assessment_data["failure_risk_score"],
        risk_level=assessment_data["risk_level"],
        warning=assessment_data["warning"],
        contributing_factors=assessment_data["contributing_factors"],
        recommended_action=assessment_data["recommended_action"],
        metrics=assessment_data["metrics"],
        assessed_at=now,
    )


async def get_maintenance_assessments(
    db: AsyncSession,
    plant_id: int,
    limit: int = 50,
) -> List[MaintenanceAssessmentResponse]:
    """Retrieve historical maintenance assessments for a plant."""
    res = await db.execute(
        select(EquipmentMaintenanceAssessment)
        .where(EquipmentMaintenanceAssessment.plant_id == plant_id)
        .order_by(EquipmentMaintenanceAssessment.assessed_at.desc())
        .limit(limit)
    )
    records = list(res.scalars().all())

    # If no records exist yet, compute an on-demand assessment
    if not records:
        latest = await assess_equipment_failure_risk(db, plant_id=plant_id, persist=True)
        return [latest]

    return [
        MaintenanceAssessmentResponse(
            id=r.id,
            plant_id=r.plant_id,
            equipment_id=r.equipment_id,
            equipment_type=r.equipment_type,
            failure_risk_score=r.failure_risk_score,
            risk_level=r.risk_level,  # type: ignore[arg-type]
            warning=r.warning,
            contributing_factors=r.contributing_factors,
            recommended_action=r.recommended_action,
            metrics=r.metrics,
            assessed_at=r.assessed_at,
        )
        for r in records
    ]


async def get_high_risk_equipment(
    db: AsyncSession,
    plant_id: Optional[int] = None,
    min_score: float = 60.0,
    limit: int = 50,
) -> List[HighRiskEquipmentResponse]:
    """Retrieve equipment units classified as HIGH or CRITICAL risk."""
    query = (
        select(EquipmentMaintenanceAssessment)
        .where(EquipmentMaintenanceAssessment.failure_risk_score >= min_score)
        .order_by(EquipmentMaintenanceAssessment.failure_risk_score.desc())
    )
    if plant_id is not None:
        query = query.where(EquipmentMaintenanceAssessment.plant_id == plant_id)
    query = query.limit(limit)

    result = await db.execute(query)
    records = list(result.scalars().all())

    return [
        HighRiskEquipmentResponse(
            plant_id=r.plant_id,
            equipment_id=r.equipment_id,
            equipment_type=r.equipment_type,
            failure_risk_score=r.failure_risk_score,
            risk_level=r.risk_level,  # type: ignore[arg-type]
            warning=r.warning,
            recommended_action=r.recommended_action,
            assessed_at=r.assessed_at,
        )
        for r in records
    ]


async def get_maintenance_recommendations(
    db: AsyncSession,
    plant_id: int,
) -> MaintenanceRecommendationResponse:
    """Retrieve actionable maintenance recommendations for plant equipment."""
    assessments = await get_maintenance_assessments(db, plant_id=plant_id, limit=10)

    recommendations: List[MaintenanceRecommendationItem] = []
    for a in assessments:
        priority_map = {
            "CRITICAL": "IMMEDIATE",
            "HIGH": "URGENT",
            "MEDIUM": "SCHEDULED",
            "LOW": "ROUTINE",
        }
        recommendations.append(
            MaintenanceRecommendationItem(
                plant_id=a.plant_id,
                equipment_id=a.equipment_id,
                risk_level=a.risk_level,
                priority=priority_map.get(a.risk_level, "ROUTINE"),  # type: ignore[arg-type]
                recommended_action=a.recommended_action,
                contributing_factors=a.contributing_factors,
                assessed_at=a.assessed_at,
            )
        )

    return MaintenanceRecommendationResponse(
        plant_id=plant_id,
        total_recommendations=len(recommendations),
        recommendations=recommendations,
    )
