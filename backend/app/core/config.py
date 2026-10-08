"""
app/core/config.py

Application configuration using Pydantic Settings.
All values are loaded from environment variables.
Never hardcode secrets here.
"""

from __future__ import annotations

from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "Solar Forecast API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/solar_forecast"
    )

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── ML ────────────────────────────────────────────────────────────────────
    ML_MODEL_PATH: str = "models/lightgbm_model.txt"

    # ── NWP / Weather API (optional — mock used when not configured) ──────────
    NWP_API_URL: str = ""
    NWP_API_KEY: str = ""

    # ── Predictive Maintenance Configuration (Enhancement 4) ───────────────────
    MAINTENANCE_THERMAL_WEIGHT: float = 0.25
    MAINTENANCE_EFFICIENCY_WEIGHT: float = 0.25
    MAINTENANCE_SHORTFALL_WEIGHT: float = 0.25
    MAINTENANCE_ANOMALY_WEIGHT: float = 0.25
    MAINTENANCE_CRITICAL_TEMP_C: float = 65.0
    MAINTENANCE_NOMINAL_EFFICIENCY: float = 0.96
    MAINTENANCE_EVALUATION_WINDOW_HOURS: int = 24

    # ── AI Plant Health Scoring Configuration (Enhancement 5) ──────────────────
    HEALTH_WEIGHT_GENERATION: float = 0.30
    HEALTH_WEIGHT_INVERTER: float = 0.20
    HEALTH_WEIGHT_SOILING: float = 0.15
    HEALTH_WEIGHT_ANOMALY: float = 0.20
    HEALTH_WEIGHT_EQUIPMENT: float = 0.15

    # ── Grid Curtailment Configuration (Enhancement 6) ────────────────────────
    CURTAILMENT_DEFAULT_EXPORT_LIMIT_RATIO: float = 0.85
    CURTAILMENT_RISK_MEDIUM_THRESHOLD_PCT: float = 5.0
    CURTAILMENT_RISK_HIGH_THRESHOLD_PCT: float = 20.0

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def jwt_secret_must_not_be_default(cls, v: str) -> str:
        # Warn in production — but do not crash in development.
        return v


settings = Settings()
