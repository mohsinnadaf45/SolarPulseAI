"""
tests/test_enhancements.py

Comprehensive unit and integration tests for SolarPulse AI:
  - Enhancement 4: Predictive Maintenance & Failure Forecasting
  - Enhancement 5: AI-Based Solar Plant Health Scoring
  - Enhancement 6: Grid Curtailment Prediction & Optimization
  - Pydantic schema validation & error handling
  - Dependency-injected API route verification
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.main import app
from app.models.alert import AnomalyAlert
from app.models.plant import Plant, PlantConfig
from app.models.scada import ScadaReading
from app.models.user import User
from app.schemas.curtailment import (
    CurtailmentHourlyPoint,
    CurtailmentPredictionRequest,
    CurtailmentPredictionResponse,
)
from app.schemas.health import (
    PlantHealthComponents,
    PlantHealthResponse,
)
from app.schemas.maintenance import (
    HighRiskEquipmentResponse,
    MaintenanceAssessmentRequest,
    MaintenanceAssessmentResponse,
)
from app.services.curtailment_service import (
    calculate_single_curtailment,
    classify_curtailment_risk,
    generate_curtailment_recommendation,
)
from app.services.health_service import (
    classify_health_status,
    compute_anomaly_score,
    compute_generation_score,
    compute_inverter_score,
    compute_soiling_score,
)
from app.services.maintenance_service import (
    FailureRiskPredictorBase,
    OperationalRiskScorer,
)


@pytest.fixture
def mock_user() -> User:
    return User(
        id=1,
        username="operator_test",
        email="operator@solarpulse.ai",
        hashed_password="hashed_pw",
        full_name="Solar Operator",
        is_active=True,
    )


@pytest.fixture
def client_with_auth(mock_user: User):
    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


# ==============================================================================
# 1. ENHANCEMENT 4: PREDICTIVE MAINTENANCE UNIT TESTS
# ==============================================================================


def test_predictive_maintenance_normal_conditions():
    """Verify healthy SCADA operational readings result in LOW failure risk."""
    scorer = OperationalRiskScorer()
    now = datetime.now(tz=timezone.utc)

    # 10 readings of normal operation (low temp, nominal efficiency, matching expected power)
    readings = [
        ScadaReading(
            plant_id=1,
            timestamp=now,
            power_kw=800.0,
            inverter_power_kw=768.0,  # 768 / 800 = 0.96 (exact nominal)
            expected_power_kw=800.0,
            module_temperature_c=42.0,  # below 45°C threshold
            temperature_c=28.0,
            irradiance_w_m2=850.0,
        )
        for _ in range(10)
    ]
    alerts: list[AnomalyAlert] = []

    res = scorer.predict_risk(
        equipment_id="INV-001",
        readings=readings,
        alerts=alerts,
        nominal_efficiency=0.96,
        rated_capacity_kw=1000.0,
    )

    assert res["equipment_id"] == "INV-001"
    assert res["risk_level"] == "LOW"
    assert res["failure_risk_score"] < 30.0
    assert "normal" in res["warning"].lower()
    assert len(res["contributing_factors"]) > 0


def test_predictive_maintenance_high_temperature_stress():
    """Verify extreme module temperature triggers elevated thermal risk and contributing factor."""
    scorer = OperationalRiskScorer()
    now = datetime.now(tz=timezone.utc)

    readings = [
        ScadaReading(
            plant_id=1,
            timestamp=now,
            power_kw=800.0,
            inverter_power_kw=768.0,
            expected_power_kw=800.0,
            module_temperature_c=72.0,  # Well above 65°C critical threshold
            temperature_c=45.0,
            irradiance_w_m2=950.0,
        )
    ]
    res = scorer.predict_risk(
        equipment_id="INV-002",
        readings=readings,
        alerts=[],
        nominal_efficiency=0.96,
    )

    assert res["metrics"]["thermal_risk_score"] >= 80.0
    assert any("operating temperature" in f.lower() for f in res["contributing_factors"])
    assert res["failure_risk_score"] > 15.0


def test_predictive_maintenance_conversion_efficiency_derate():
    """Verify degraded inverter conversion efficiency increases risk score."""
    scorer = OperationalRiskScorer()
    now = datetime.now(tz=timezone.utc)

    # Inverter severely derating: only delivering 640 kW from 800 kW DC (efficiency = 0.80 vs 0.96)
    readings = [
        ScadaReading(
            plant_id=1,
            timestamp=now,
            power_kw=800.0,
            inverter_power_kw=640.0,
            expected_power_kw=800.0,
            module_temperature_c=40.0,
            temperature_c=25.0,
        )
    ]
    res = scorer.predict_risk(
        equipment_id="INV-003",
        readings=readings,
        alerts=[],
        nominal_efficiency=0.96,
    )

    assert res["metrics"]["efficiency_derate_score"] >= 70.0
    assert any("conversion degradation" in f.lower() or "efficiency" in f.lower() for f in res["contributing_factors"])


def test_predictive_maintenance_unresolved_critical_anomalies():
    """Verify active unresolved critical anomalies penalize equipment risk score."""
    scorer = OperationalRiskScorer()
    now = datetime.now(tz=timezone.utc)

    critical_alerts = [
        AnomalyAlert(
            plant_id=1,
            timestamp=now,
            alert_type="shortfall",
            severity="CRITICAL",
            message="Severe persistent drop",
            is_resolved=False,
        ),
        AnomalyAlert(
            plant_id=1,
            timestamp=now,
            alert_type="shortfall",
            severity="CRITICAL",
            message="Second trip",
            is_resolved=False,
        ),
    ]

    res = scorer.predict_risk(
        equipment_id="INV-004",
        readings=[],
        alerts=critical_alerts,
        nominal_efficiency=0.96,
    )

    assert res["metrics"]["anomaly_severity_score"] >= 60.0
    assert any("unresolved critical" in f.lower() for f in res["contributing_factors"])


def test_predictive_maintenance_compound_critical_risk():
    """Verify combination of thermal, efficiency, and anomaly factors drives risk to CRITICAL."""
    scorer = OperationalRiskScorer()
    now = datetime.now(tz=timezone.utc)

    readings = [
        ScadaReading(
            plant_id=1,
            timestamp=now,
            power_kw=500.0,
            inverter_power_kw=400.0,  # 0.80 efficiency
            expected_power_kw=800.0,  # 37.5% shortfall
            module_temperature_c=74.0,  # critical overheat
            temperature_c=46.0,
        )
    ]
    alerts = [
        AnomalyAlert(
            plant_id=1,
            timestamp=now,
            alert_type="shortfall",
            severity="CRITICAL",
            message="Overheat shortfall",
            is_resolved=False,
        ),
        AnomalyAlert(
            plant_id=1,
            timestamp=now,
            alert_type="shortfall",
            severity="CRITICAL",
            message="Thermal derate trip",
            is_resolved=False,
        ),
    ]

    res = scorer.predict_risk(
        equipment_id="INV-005",
        readings=readings,
        alerts=alerts,
        nominal_efficiency=0.96,
    )

    assert res["failure_risk_score"] >= 75.0
    assert res["risk_level"] in ("HIGH", "CRITICAL")
    assert "dispatch maintenance" in res["recommended_action"].lower() or "inspect" in res["recommended_action"].lower()


# ==============================================================================
# 2. ENHANCEMENT 5: AI PLANT HEALTH SCORING UNIT TESTS
# ==============================================================================


def test_health_status_classification_boundaries():
    """Verify numeric health scores map to exact operational status tiers."""
    assert classify_health_status(95.0) == "EXCELLENT"
    assert classify_health_status(90.0) == "EXCELLENT"
    assert classify_health_status(89.9) == "GOOD"
    assert classify_health_status(75.0) == "GOOD"
    assert classify_health_status(74.9) == "NEEDS ATTENTION"
    assert classify_health_status(60.0) == "NEEDS ATTENTION"
    assert classify_health_status(59.9) == "POOR"
    assert classify_health_status(40.0) == "POOR"
    assert classify_health_status(39.9) == "CRITICAL"
    assert classify_health_status(10.0) == "CRITICAL"


def test_compute_generation_score():
    """Verify generation performance calculation and shortfall detection."""
    # Readings meeting expected generation (100% score)
    readings_healthy = [
        ScadaReading(plant_id=1, timestamp=datetime.now(tz=timezone.utc), power_kw=500.0, expected_power_kw=500.0)
    ]
    score_h, concerns_h = compute_generation_score(readings_healthy)
    assert score_h == 100.0
    assert len(concerns_h) == 0

    # Readings severely underperforming expected power (50% yield)
    readings_poor = [
        ScadaReading(plant_id=1, timestamp=datetime.now(tz=timezone.utc), power_kw=250.0, expected_power_kw=500.0)
    ]
    score_p, concerns_p = compute_generation_score(readings_poor)
    assert score_p == 50.0
    assert len(concerns_p) > 0


def test_compute_inverter_score():
    """Verify inverter conversion efficiency score calculation."""
    readings_good = [
        ScadaReading(plant_id=1, timestamp=datetime.now(tz=timezone.utc), power_kw=1000.0, inverter_power_kw=960.0)
    ]
    score_g, _ = compute_inverter_score(readings_good, nominal_efficiency=0.96)
    assert score_g == 100.0

    readings_bad = [
        ScadaReading(plant_id=1, timestamp=datetime.now(tz=timezone.utc), power_kw=1000.0, inverter_power_kw=720.0)
    ]
    score_b, concerns_b = compute_inverter_score(readings_bad, nominal_efficiency=0.96)
    assert score_b == pytest.approx(75.0, 0.1)
    assert len(concerns_b) > 0


def test_compute_soiling_score():
    """Verify soiling condition evaluation from dynamic soiling service."""
    reading = ScadaReading(
        plant_id=1,
        timestamp=datetime.now(tz=timezone.utc),
        power_kw=800.0,
        irradiance_w_m2=900.0,
    )
    config = PlantConfig(plant_id=1, soiling_threshold=5.0)

    score, concerns = compute_soiling_score(reading, config)
    assert 0.0 <= score <= 100.0
    assert isinstance(concerns, list)


def test_compute_anomaly_score():
    """Verify anomaly health score deductions for active alerts."""
    # Clean plant with no alerts -> 100
    score_clean, concerns_clean = compute_anomaly_score([])
    assert score_clean == 100.0
    assert len(concerns_clean) == 0

    # Plant with 2 unresolved critical alerts -> 100 - (2 * 20) = 60
    alerts = [
        AnomalyAlert(plant_id=1, timestamp=datetime.now(tz=timezone.utc), alert_type="shortfall", severity="CRITICAL", message="A1", is_resolved=False),
        AnomalyAlert(plant_id=1, timestamp=datetime.now(tz=timezone.utc), alert_type="shortfall", severity="CRITICAL", message="A2", is_resolved=False),
    ]
    score_dirty, concerns_dirty = compute_anomaly_score(alerts)
    assert score_dirty == 60.0
    assert len(concerns_dirty) > 0


# ==============================================================================
# 3. ENHANCEMENT 6: GRID CURTAILMENT UNIT TESTS
# ==============================================================================


def test_calculate_single_curtailment_no_curtailment():
    """Verify generation below export limit results in zero curtailment."""
    c_kw, c_kwh, pct, is_curtailed = calculate_single_curtailment(
        forecast_generation_kw=700.0,
        export_limit_kw=850.0,
        duration_hours=1.0,
    )
    assert c_kw == 0.0
    assert c_kwh == 0.0
    assert pct == 0.0
    assert is_curtailed is False


def test_calculate_single_curtailment_with_excess():
    """Verify generation exceeding export limit correctly calculates curtailed kW and kWh."""
    # Forecast = 1000 kW, Limit = 700 kW -> Excess = 300 kW, 30% curtailment
    c_kw, c_kwh, pct, is_curtailed = calculate_single_curtailment(
        forecast_generation_kw=1000.0,
        export_limit_kw=700.0,
        duration_hours=2.0,
    )
    assert c_kw == 300.0
    assert c_kwh == 600.0  # 300 kW * 2h = 600 kWh
    assert pct == pytest.approx(30.0, 0.1)
    assert is_curtailed is True


def test_classify_curtailment_risk():
    """Verify curtailment risk tier classification."""
    assert classify_curtailment_risk(curtailment_percentage=0.0, curtailed_kw=0.0) == "LOW"
    assert classify_curtailment_risk(curtailment_percentage=3.0, curtailed_kw=20.0) == "LOW"
    assert classify_curtailment_risk(curtailment_percentage=12.0, curtailed_kw=120.0) == "MEDIUM"
    assert classify_curtailment_risk(curtailment_percentage=28.0, curtailed_kw=350.0) == "HIGH"


def test_generate_curtailment_recommendation():
    """Verify decision-support recommendation contains key operational guidance."""
    rec_high = generate_curtailment_recommendation(
        risk_level="HIGH",
        curtailed_kw=300.0,
        curtailed_kwh=1200.0,
        export_limit_kw=700.0,
        peak_time_str="13:00 UTC",
    )
    assert "HIGH Curtailment Risk" in rec_high
    assert "BESS" in rec_high
    assert "300.0 kW" in rec_high

    rec_low = generate_curtailment_recommendation(
        risk_level="LOW",
        curtailed_kw=0.0,
        curtailed_kwh=0.0,
        export_limit_kw=850.0,
    )
    assert "LOW Curtailment Risk" in rec_low


# ==============================================================================
# 4. API ROUTE & SCHEMA VALIDATION TESTS
# ==============================================================================


def test_maintenance_schema_validation():
    """Verify Maintenance Pydantic schemas enforce bounds and valid structure."""
    req = MaintenanceAssessmentRequest(plant_id=1, window_hours=48, persist=False)
    assert req.plant_id == 1
    assert req.window_hours == 48

    resp = MaintenanceAssessmentResponse(
        plant_id=1,
        equipment_id="INV-001",
        equipment_type="inverter",
        failure_risk_score=78.5,
        risk_level="HIGH",
        warning="High thermal stress",
        contributing_factors=["Overheating"],
        recommended_action="Inspect cooling fans",
        metrics={"thermal_score": 85.0},
        assessed_at=datetime.now(tz=timezone.utc),
    )
    assert resp.failure_risk_score == 78.5
    assert resp.risk_level == "HIGH"


def test_plant_health_schema_validation():
    """Verify Plant Health Pydantic schemas enforce bounds and valid structure."""
    comps = PlantHealthComponents(
        generation_performance=92.0,
        inverter_health=95.0,
        soiling_condition=88.5,
        anomaly_health=90.0,
        equipment_health=85.0,
    )
    resp = PlantHealthResponse(
        plant_id=1,
        health_score=90.5,
        health_status="EXCELLENT",
        components=comps,
        major_concerns=[],
        recommendations=["Routine maintenance"],
        assessed_at=datetime.now(tz=timezone.utc),
    )
    assert resp.health_score == 90.5
    assert resp.health_status == "EXCELLENT"


def test_curtailment_schema_validation():
    """Verify Curtailment Pydantic schemas enforce bounds and valid structure."""
    req = CurtailmentPredictionRequest(plant_id=1, export_limit_kw=800.0, horizon_hours=12)
    assert req.export_limit_kw == 800.0

    point = CurtailmentHourlyPoint(
        timestamp=datetime.now(tz=timezone.utc),
        forecast_generation_kw=1000.0,
        export_limit_kw=800.0,
        potential_curtailment_kw=200.0,
        potential_curtailment_kwh=200.0,
        curtailment_percentage=20.0,
        is_curtailed=True,
    )
    resp = CurtailmentPredictionResponse(
        plant_id=1,
        forecast_generation_kw=1000.0,
        export_limit_kw=800.0,
        potential_curtailment_kw=200.0,
        potential_curtailment_kwh=200.0,
        curtailment_percentage=20.0,
        risk_level="HIGH",
        recommendation="Charge battery",
        schedule=[point],
        bess_opportunity={"recommended_charging_power_kw": 200.0},
        assessed_at=datetime.now(tz=timezone.utc),
    )
    assert resp.risk_level == "HIGH"
    assert len(resp.schedule) == 1


# ==============================================================================
# 5. END-TO-END FASTAPI ROUTER INTEGRATION TESTS
# ==============================================================================


def test_api_curtailment_predict_route(client_with_auth: TestClient):
    """Verify POST /api/v1/curtailment/predict endpoint via mock service."""
    now = datetime.now(tz=timezone.utc)
    mock_response = CurtailmentPredictionResponse(
        plant_id=1,
        forecast_generation_kw=1000.0,
        export_limit_kw=700.0,
        potential_curtailment_kw=300.0,
        potential_curtailment_kwh=300.0,
        curtailment_percentage=30.0,
        risk_level="HIGH",
        recommendation="Consider BESS storage charging",
        schedule=[],
        bess_opportunity={"recommended_charging_power_kw": 300.0},
        assessed_at=now,
    )

    with patch("app.services.curtailment_service.predict_curtailment", new_callable=AsyncMock) as mock_predict:
        mock_predict.return_value = mock_response

        response = client_with_auth.post(
            "/api/v1/curtailment/predict",
            json={"plant_id": 1, "export_limit_kw": 700.0, "horizon_hours": 24, "persist": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plant_id"] == 1
        assert data["potential_curtailment_kw"] == 300.0
        assert data["risk_level"] == "HIGH"


def test_api_health_score_route(client_with_auth: TestClient):
    """Verify GET /api/v1/health-score/{plant_id} endpoint via mock service."""
    now = datetime.now(tz=timezone.utc)
    mock_health = PlantHealthResponse(
        plant_id=1,
        health_score=88.0,
        health_status="GOOD",
        components=PlantHealthComponents(
            generation_performance=90.0,
            inverter_health=88.0,
            soiling_condition=92.0,
            anomaly_health=85.0,
            equipment_health=85.0,
        ),
        major_concerns=[],
        recommendations=["Continue routine monitoring"],
        assessed_at=now,
    )

    with patch("app.services.health_service.get_latest_plant_health", new_callable=AsyncMock) as mock_get_health:
        mock_get_health.return_value = mock_health

        response = client_with_auth.get("/api/v1/health-score/1")
        assert response.status_code == 200
        data = response.json()
        assert data["plant_id"] == 1
        assert data["health_score"] == 88.0
        assert data["health_status"] == "GOOD"
        assert "generation_performance" in data["components"]


def test_api_maintenance_assess_route(client_with_auth: TestClient):
    """Verify POST /api/v1/maintenance/assess endpoint via mock service."""
    now = datetime.now(tz=timezone.utc)
    mock_assessment = MaintenanceAssessmentResponse(
        plant_id=1,
        equipment_id="INV-001",
        equipment_type="inverter",
        failure_risk_score=75.0,
        risk_level="HIGH",
        warning="Elevated thermal stress detected",
        contributing_factors=["High module temperature"],
        recommended_action="Inspect inverter cooling fans within 48 hours",
        metrics={"thermal_risk_score": 82.0},
        assessed_at=now,
    )

    with patch("app.services.maintenance_service.assess_equipment_failure_risk", new_callable=AsyncMock) as mock_assess:
        mock_assess.return_value = mock_assessment

        response = client_with_auth.post(
            "/api/v1/maintenance/assess",
            json={"plant_id": 1, "equipment_id": "INV-001", "window_hours": 24, "persist": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["equipment_id"] == "INV-001"
        assert data["failure_risk_score"] == 75.0
        assert data["risk_level"] == "HIGH"
