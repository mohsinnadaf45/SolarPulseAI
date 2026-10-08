"""
app/main.py

FastAPI application entry point.

Registers:
- CORS middleware
- All API v1 routers
- SCADA WebSocket
- Health endpoint
- Lifespan (startup / shutdown) events
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import (
    alerts,
    anomaly,
    auth,
    curtailment,
    diagnosis,
    forecast,
    health,
    maintenance,
    plants,
    weather,
)
from app.api.websockets.scada_ws import scada_ws_handler
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown logic."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Ensure database tables exist and seed demo plants if empty
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("Database tables initialized successfully.")

        from app.scripts.seed_data import seed
        await seed()
        logger.info("Demo plants and operational data verified/seeded.")
    except Exception as exc:
        logger.warning(f"Could not automatically initialize/seed database: {exc}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")


# ── Application factory ───────────────────────────────────────────────────────


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Solar Power Plant Forecasting and Monitoring API. "
            "Provides real-time SCADA data, physics-informed and ML forecasting, "
            "automated inverter diagnosis, predictive maintenance, AI plant health scoring, "
            "and grid curtailment optimization."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API v1 routers ────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(plants.router, prefix=api_prefix)
    app.include_router(forecast.router, prefix=api_prefix)
    app.include_router(anomaly.router, prefix=api_prefix)
    app.include_router(alerts.router, prefix=api_prefix)
    app.include_router(diagnosis.router, prefix=api_prefix)
    app.include_router(weather.router, prefix=api_prefix)
    app.include_router(maintenance.router, prefix=api_prefix)
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(curtailment.router, prefix=api_prefix)

    # ── WebSocket ─────────────────────────────────────────────────────────────
    @app.websocket("/ws/scada/{plant_id}")
    async def scada_websocket(websocket: WebSocket, plant_id: int) -> None:
        """Real-time SCADA WebSocket stream for a specific plant."""
        await scada_ws_handler(websocket, plant_id)

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health_check() -> dict:
        """Returns 200 when the API is running."""
        return {"status": "healthy", "version": settings.APP_VERSION}

    return app


app = create_application()
