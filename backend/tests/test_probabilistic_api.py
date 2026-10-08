"""
backend/tests/test_probabilistic_api.py

Integration tests for the probabilistic forecast and ramp-risk API endpoint:
GET /api/v1/forecast/{plant_id}/probabilistic
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.api.deps import get_current_active_user, get_db
from app.models.user import User


class MockPlant:
    id = 1
    name = "Desert Sun Plant"
    capacity_kw = 1000.0
    inverter_capacity_kw = 850.0
    latitude = 28.6139
    longitude = 77.2090


class MockPlantConfig:
    tilt = 25.0
    azimuth = 180.0
    efficiency = 0.96


@pytest.fixture
def authed_client():
    """Test client with mock active user and mock DB session."""
    mock_user = User(
        id=1,
        email="operator@solarpulse.ai",
        username="operator",
        full_name="Grid Operator",
        is_active=True,
    )
    mock_db = AsyncMock()
    # Mock execute for SCADA lookup inside generate_probabilistic_forecast
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_scalar

    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    yield client

    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_db, None)


@patch("app.services.plant_service.get_plant", new_callable=AsyncMock)
@patch("app.services.plant_service.get_plant_config", new_callable=AsyncMock)
def test_probabilistic_forecast_endpoint_default(mock_get_config, mock_get_plant, authed_client):
    """Verify GET /api/v1/forecast/1/probabilistic returns structured quantile & ramp data."""
    mock_get_plant.return_value = MockPlant()
    mock_get_config.return_value = MockPlantConfig()

    response = authed_client.get("/api/v1/forecast/1/probabilistic")
    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert data["plant_id"] == 1
    assert data["plant_name"] == "Desert Sun Plant"
    assert data["capacity_kw"] == 1000.0
    assert data["horizon_minutes"] == 240
    assert data["interval_minutes"] == 15
    assert data["model_name"] == "probabilistic_quantile"

    # Points checks
    points = data["points"]
    assert len(points) == 17  # 240/15 + 1
    first_pt = points[0]
    assert "forecast_time" in first_pt
    assert "p10_kw" in first_pt
    assert "p50_kw" in first_pt
    assert "p90_kw" in first_pt
    assert "uncertainty_band_kw" in first_pt
    assert "ramp_rate_kw_per_min" in first_pt
    assert "ramp_direction" in first_pt
    assert "ramp_risk_level" in first_pt
    assert "bess_reserve_recommendation_kw" in first_pt
    assert "reserve_action" in first_pt

    # Quantile monotonicity across all points
    for pt in points:
        assert pt["p10_kw"] <= pt["p50_kw"]
        assert pt["p50_kw"] <= pt["p90_kw"]
        assert pt["uncertainty_band_kw"] >= 0.0
        assert pt["ramp_direction"] in ["up", "down", "stable"]
        assert pt["ramp_risk_level"] in ["low", "medium", "high", "critical"]

    # Summary checks
    summary = data["summary"]
    assert "max_ramp_rate_kw_per_min" in summary
    assert "ramp_risk_score" in summary
    assert 0.0 <= summary["ramp_risk_score"] <= 100.0
    assert summary["highest_risk_level"] in ["low", "medium", "high", "critical"]
    assert "recommended_bess_capacity_kw" in summary
    assert "primary_action_advisory" in summary
    assert len(summary["primary_action_advisory"]) > 5


@patch("app.services.plant_service.get_plant", new_callable=AsyncMock)
@patch("app.services.plant_service.get_plant_config", new_callable=AsyncMock)
def test_probabilistic_forecast_custom_horizon(mock_get_config, mock_get_plant, authed_client):
    """Verify custom horizon and interval parameters."""
    mock_get_plant.return_value = MockPlant()
    mock_get_config.return_value = MockPlantConfig()

    response = authed_client.get(
        "/api/v1/forecast/1/probabilistic?horizon_minutes=60&interval_minutes=30"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["horizon_minutes"] == 60
    assert data["interval_minutes"] == 30
    assert len(data["points"]) == 3  # 0m, 30m, 60m


def test_probabilistic_forecast_validation_limits(authed_client):
    """Verify query validation on negative or excessive horizons."""
    # Under minimum horizon (ge=15)
    res_under = authed_client.get("/api/v1/forecast/1/probabilistic?horizon_minutes=5")
    assert res_under.status_code == 422

    # Over maximum horizon (le=1440)
    res_over = authed_client.get("/api/v1/forecast/1/probabilistic?horizon_minutes=2000")
    assert res_over.status_code == 422
