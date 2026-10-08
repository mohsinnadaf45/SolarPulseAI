"""
backend/tests/test_diagnosis_api.py

Integration tests for AI Root-Cause Diagnosis API endpoints:
- GET /api/v1/diagnosis/taxonomy
- POST /api/v1/diagnosis/diagnose
- GET /api/v1/diagnosis/alert/{alert_id}
- GET /api/v1/diagnosis/plant/{plant_id}
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.models.alert import AnomalyAlert


class MockPlant:
    id = 1
    name = "Bhadla Solar Park"
    capacity_kw = 50000.0
    inverter_capacity_kw = 45000.0
    latitude = 27.5385
    longitude = 71.9161


@pytest.fixture
def authed_client():
    """Client with authenticated mock user and mock DB session."""
    mock_user = User(
        id=1,
        email="diagnostician@solarpulse.ai",
        username="diagnostician",
        full_name="Solar Field Engineer",
        is_active=True,
    )
    mock_db = AsyncMock()
    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    yield client, mock_db

    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_get_taxonomy_endpoint(authed_client):
    """Verify taxonomy endpoint returns standard categories and codes."""
    client, _ = authed_client
    response = client.get("/api/v1/diagnosis/taxonomy")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 8

    item = data[0]
    assert "category" in item
    assert "title" in item
    assert "common_error_codes" in item
    assert "description" in item


@patch("app.services.plant_service.get_plant", new_callable=AsyncMock)
def test_post_diagnose_custom_endpoint(mock_get_plant, authed_client):
    """Verify POST /api/v1/diagnosis/diagnose runs inference and persists diagnosis."""
    client, mock_db = authed_client
    mock_get_plant.return_value = MockPlant()

    payload = {
        "plant_id": 1,
        "inverter_error_code": "F056",
        "expected_power_kw": 40000.0,
        "actual_power_kw": 25000.0,
        "temperature_c": 38.5,
    }

    response = client.post("/api/v1/diagnosis/diagnose", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["plant_id"] == 1
    assert data["root_cause_category"] == "INVERTER_TRIP_OVERTEMP"
    assert data["confidence_score"] >= 90.0
    assert data["estimated_loss_kw"] == 15000.0
    assert data["financial_impact_per_day"] > 0
    assert len(data["technician_steps"]) >= 3
    assert mock_db.add.called
    assert mock_db.commit.called


@patch("app.services.diagnosis_service.run_diagnosis_for_alert", new_callable=AsyncMock)
def test_diagnose_alert_endpoint(mock_run_diag, authed_client):
    """Verify GET /api/v1/diagnosis/alert/{alert_id} triggers automated diagnosis."""
    from app.schemas.diagnosis import DiagnosisResponse, TechnicianStep

    client, _ = authed_client
    mock_run_diag.return_value = DiagnosisResponse(
        id=42,
        plant_id=1,
        plant_name="Bhadla Solar Park",
        alert_id=10,
        timestamp=datetime.now(tz=timezone.utc),
        root_cause_category="GROUND_FAULT_INSULATION",
        root_cause_title="DC Ground Fault / Low Insulation Resistance (Riso)",
        confidence_score=95.0,
        inverter_error_code="F034",
        estimated_loss_kw=12400.0,
        financial_impact_per_day=5456.0,
        urgency_level="CRITICAL",
        summary="AI Diagnosis identified Ground Fault with 95% confidence.",
        root_cause_details="Insulation resistance dropped below statutory threshold.",
        technician_steps=[
            TechnicianStep(step_number=1, action="Isolate inverter", required_tools=["Clamp meter"])
        ],
        created_at=datetime.now(tz=timezone.utc),
    )

    response = client.get("/api/v1/diagnosis/alert/10")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["alert_id"] == 10
    assert data["root_cause_category"] == "GROUND_FAULT_INSULATION"
    assert data["urgency_level"] == "CRITICAL"
