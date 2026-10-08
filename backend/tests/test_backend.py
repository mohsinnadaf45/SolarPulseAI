"""
tests/test_backend.py

Unit and integration tests for Solar Forecast API:
- Health check
- Security and authentication helpers
- Engineering calculation services (soiling, clipping, anomalies)
- Physics worker features & ML inference pipeline
- Schema validations
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.services.soiling_service import calculate_soiling_loss
from app.services.clipping_service import calculate_clipping
from app.services.anomaly_service import calculate_deviation, _classify_severity
from app.workers.physics_worker import compute_physics_features
from app.workers.ml_worker import run_batch_inference
from app.schemas.plant import PlantCreate, PlantConfigUpdate
from app.schemas.alert import AlertThresholdRequest


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint returns 200 and valid status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_security_password_hashing():
    """Verify bcrypt password hashing and constant-time verification."""
    password = "super-secret-password-123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_security_jwt_token_flow():
    """Verify JWT access token issuance and decoding."""
    subject = "user@solarpulse.ai"
    token = create_access_token(subject=subject)
    assert isinstance(token, str) and len(token) > 20
    decoded_sub = decode_access_token(token)
    assert decoded_sub == subject


def test_soiling_service_calculation():
    """Verify soiling loss increases with dry days and resets with rain."""
    res_dry = calculate_soiling_loss(current_power_kw=100.0, days_since_cleaning=14, rainfall_mm=0.0)
    assert res_dry.soiling_loss_percent > 0.0
    assert res_dry.estimated_loss_kw > 0.0

    res_rain = calculate_soiling_loss(current_power_kw=100.0, days_since_cleaning=14, rainfall_mm=15.0)
    assert res_rain.soiling_loss_percent < res_dry.soiling_loss_percent


def test_clipping_service_calculation():
    """Verify inverter clipping triggers when DC power exceeds AC capacity."""
    # Under capacity -> No clipping
    res_normal = calculate_clipping(dc_power_kw=800.0, inverter_capacity_kw=1000.0, efficiency=0.96)
    assert res_normal.is_clipping is False
    assert res_normal.clipping_loss_kw == 0.0

    # Over capacity -> Clipping
    res_clip = calculate_clipping(dc_power_kw=1200.0, inverter_capacity_kw=1000.0, efficiency=0.96)
    assert res_clip.is_clipping is True
    assert res_clip.clipping_loss_kw > 0.0
    assert res_clip.clipped_ac_power_kw == 1000.0


def test_anomaly_detection_logic():
    """Verify power shortfall deviation and threshold classification."""
    dev = calculate_deviation(expected_power_kw=1000.0, actual_power_kw=850.0)
    assert dev == pytest.approx(15.0)

    thresholds = {"warning": 10.0, "critical": 25.0}
    assert _classify_severity(15.0, thresholds) == "WARNING"
    assert _classify_severity(30.0, thresholds) == "CRITICAL"
    assert _classify_severity(5.0, thresholds) is None


def test_physics_feature_computation():
    """Verify solar feature calculations produce reasonable ranges."""
    features = compute_physics_features(
        latitude=28.6139,
        longitude=77.2090,
        tilt=25.0,
        azimuth=180.0,
        capacity_kw=1000.0,
        efficiency=0.96,
        timestamp=datetime.now(tz=timezone.utc),
        irradiance_w_m2=800.0,
        temperature_c=30.0,
    )
    assert "physics_power_kw" in features
    assert features["physics_power_kw"] >= 0.0
    assert features["capacity_kw"] == 1000.0


def test_ml_batch_inference_pipeline():
    """Verify ML worker batch inference runs smoothly with fallback."""
    records = [
        {
            "physics_power_kw": 800.0,
            "capacity_kw": 1000.0,
            "irradiance_w_m2": 850.0,
            "temperature_c": 32.0,
        }
    ]
    result = run_batch_inference(records)
    assert "predictions" in result
    assert result["record_count"] == 1
    assert len(result["predictions"]) == 1
    assert result["predictions"][0] > 0.0


def test_plant_schema_validation():
    """Verify Pydantic models validate input constraints."""
    plant = PlantCreate(
        name="Desert Solar Unit 1",
        latitude=26.9124,
        longitude=75.7873,
        capacity_kw=25000.0,
        inverter_capacity_kw=22000.0,
    )
    assert plant.name == "Desert Solar Unit 1"
    assert plant.capacity_kw == 25000.0

    threshold_req = AlertThresholdRequest(
        plant_id=1,
        warning_threshold_percent=12.5,
        critical_threshold_percent=25.0,
    )
    assert threshold_req.warning_threshold_percent == 12.5


def test_scada_websocket(client):
    """Verify SCADA WebSocket connection and initial handshake frame."""
    with client.websocket_connect("/ws/scada/1") as ws:
        data = ws.receive_json()
        assert data["plant_id"] == 1
        assert data["status"] == "connected"
        assert "_source" in data
