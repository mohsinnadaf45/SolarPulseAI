"""
app/scripts/seed_data.py

Seeds the database with initial roles, permissions, a default admin user,
two demo solar plants with configurations, 48-hour forecast curves,
SCADA readings, and anomaly alerts.

Usage:
    python -m app.scripts.seed_data
"""

import asyncio
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal, init_db
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.user import Role, User
from app.models.plant import Plant, PlantConfig
from app.models.forecast import ForecastRecord
from app.models.alert import AnomalyAlert
from app.models.scada import ScadaReading

logger = get_logger(__name__)


def generate_diurnal_power(hour_float: float, peak_kw: float) -> float:
    """Generate realistic solar generation curve based on hour of day (0-24)."""
    # Sun shines approximately 6:00 to 18:30
    sunrise = 6.0
    sunset = 18.5
    if hour_float <= sunrise or hour_float >= sunset:
        return 0.0
    # Solar noon around 12.25
    solar_noon = 12.25
    # Normalize to half-sine curve
    phase = (hour_float - sunrise) / (sunset - sunrise) * math.pi
    power = peak_kw * math.sin(phase) ** 1.3
    return max(0.0, round(power, 2))


async def seed() -> None:
    logger.info("Initializing tables before seeding...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # ── 1. Roles ──────────────────────────────────────────────────────────
        role_admin = await session.scalar(select(Role).where(Role.name == "admin"))
        if not role_admin:
            role_admin = Role(name="admin")
            role_operator = Role(name="operator")
            role_viewer = Role(name="viewer")
            session.add_all([role_admin, role_operator, role_viewer])
            await session.flush()
            logger.info("Created roles: admin, operator, viewer")

        # ── 2. Admin User ──────────────────────────────────────────────────────
        admin_user = await session.scalar(select(User).where(User.email == "admin@solarpulse.ai"))
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@solarpulse.ai",
                hashed_password=hash_password("admin12345"),
                full_name="SolarPulse Administrator",
                role_id=role_admin.id,
                is_active=True,
            )
            session.add(admin_user)
            logger.info("Created default admin user: admin@solarpulse.ai / admin12345")

        # ── 3. Demo Plant 1: Bhadla Solar Park ────────────────────────────────
        plant_1 = await session.scalar(select(Plant).where(Plant.name == "Bhadla Solar Park - Block A"))
        if not plant_1:
            plant_1 = Plant(
                name="Bhadla Solar Park - Block A",
                location="Phalodi, Rajasthan, India",
                latitude=27.5385,
                longitude=71.9161,
                timezone="Asia/Kolkata",
                capacity_kw=50000.0,
                inverter_capacity_kw=45000.0,
                module_count=130000,
                is_active=True,
            )
            session.add(plant_1)
            await session.flush()

            config_1 = PlantConfig(
                plant_id=plant_1.id,
                tilt=26.0,
                azimuth=180.0,
                efficiency=0.195,
                soiling_threshold=5.0,
                clipping_threshold=95.0,
                forecast_horizon_minutes=60,
            )
            session.add(config_1)
            logger.info(f"Created demo plant: {plant_1.name} (ID: {plant_1.id})")
        else:
            logger.info(f"Existing plant found: {plant_1.name} (ID: {plant_1.id})")

        # ── 4. Demo Plant 2: Pavagada Solar Park ──────────────────────────────
        plant_2 = await session.scalar(select(Plant).where(Plant.name == "Pavagada Solar Park - Sector 2"))
        if not plant_2:
            plant_2 = Plant(
                name="Pavagada Solar Park - Sector 2",
                location="Tumakuru, Karnataka, India",
                latitude=14.1030,
                longitude=77.2794,
                timezone="Asia/Kolkata",
                capacity_kw=25000.0,
                inverter_capacity_kw=22500.0,
                module_count=65000,
                is_active=True,
            )
            session.add(plant_2)
            await session.flush()

            config_2 = PlantConfig(
                plant_id=plant_2.id,
                tilt=15.0,
                azimuth=180.0,
                efficiency=0.202,
                soiling_threshold=4.5,
                clipping_threshold=95.0,
                forecast_horizon_minutes=60,
            )
            session.add(config_2)
            logger.info(f"Created demo plant: {plant_2.name} (ID: {plant_2.id})")

        # ── 5. Seed Forecast Records for Demo Plants ─────────────────────────
        now = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
        
        # Check existing forecasts for plant_1
        existing_fc = await session.scalar(
            select(ForecastRecord.id).where(ForecastRecord.plant_id == plant_1.id)
        )
        if not existing_fc:
            logger.info("Generating realistic 48-hour forecast series...")
            forecasts = []
            # 24 hours in past to 24 hours in future (48 hourly points)
            for i in range(-24, 25):
                t = now + timedelta(hours=i)
                hour_val = (t.hour + t.minute / 60.0)
                pred_1 = generate_diurnal_power(hour_val, peak_kw=43200.0)
                actual_1 = (
                    round(pred_1 * 0.96 + (math.sin(i * 1.5) * 800.0), 2)
                    if i <= 0 and pred_1 > 0
                    else (0.0 if i <= 0 else None)
                )

                forecasts.append(
                    ForecastRecord(
                        plant_id=plant_1.id,
                        forecast_time=t,
                        generated_at=now - timedelta(hours=24),
                        predicted_power_kw=pred_1,
                        actual_power_kw=actual_1,
                        confidence_lower=round(max(0.0, pred_1 * 0.88), 2),
                        confidence_upper=round(pred_1 * 1.08, 2),
                        model_name="SolarPulse-Hybrid-Ensemble",
                        model_version="2.1.0",
                        physics_power_kw=round(pred_1 * 0.98, 2),
                        ml_power_kw=pred_1,
                    )
                )

                # Plant 2 forecasts
                pred_2 = generate_diurnal_power(hour_val, peak_kw=21800.0)
                actual_2 = (
                    round(pred_2 * 0.98 + (math.cos(i * 1.2) * 450.0), 2)
                    if i <= 0 and pred_2 > 0
                    else (0.0 if i <= 0 else None)
                )
                forecasts.append(
                    ForecastRecord(
                        plant_id=plant_2.id,
                        forecast_time=t,
                        generated_at=now - timedelta(hours=24),
                        predicted_power_kw=pred_2,
                        actual_power_kw=actual_2,
                        confidence_lower=round(max(0.0, pred_2 * 0.89), 2),
                        confidence_upper=round(pred_2 * 1.07, 2),
                        model_name="SolarPulse-Hybrid-Ensemble",
                        model_version="2.1.0",
                        physics_power_kw=round(pred_2 * 0.99, 2),
                        ml_power_kw=pred_2,
                    )
                )

            session.add_all(forecasts)
            logger.info(f"Inserted {len(forecasts)} forecast records.")

        # ── 6. Seed Anomaly Alerts ───────────────────────────────────────────
        existing_alerts = await session.scalar(
            select(AnomalyAlert.id).where(AnomalyAlert.plant_id == plant_1.id)
        )
        if not existing_alerts:
            alerts = [
                AnomalyAlert(
                    plant_id=plant_1.id,
                    timestamp=now - timedelta(hours=2, minutes=15),
                    alert_type="shortfall",
                    severity="CRITICAL",
                    message="Inverter Station 3 trip: 12.4 MW sudden deficit detected during high irradiance",
                    expected_power_kw=42500.0,
                    actual_power_kw=30100.0,
                    deviation_percent=29.18,
                    is_resolved=False,
                ),
                AnomalyAlert(
                    plant_id=plant_1.id,
                    timestamp=now - timedelta(hours=5),
                    alert_type="soiling",
                    severity="WARNING",
                    message="Sub-array 4B soiling deficit: Sustained 14.8% power shortfall against physical clear-sky model",
                    expected_power_kw=38200.0,
                    actual_power_kw=32550.0,
                    deviation_percent=14.79,
                    is_resolved=False,
                ),
                AnomalyAlert(
                    plant_id=plant_2.id,
                    timestamp=now - timedelta(hours=1, minutes=10),
                    alert_type="clipping",
                    severity="WARNING",
                    message="Inverter capacity saturation: AC clipping detected on Inverters 1-4 at 22.5 MW threshold",
                    expected_power_kw=23800.0,
                    actual_power_kw=22500.0,
                    deviation_percent=5.46,
                    is_resolved=False,
                ),
                AnomalyAlert(
                    plant_id=plant_1.id,
                    timestamp=now - timedelta(days=1, hours=3),
                    alert_type="curtailment",
                    severity="INFO",
                    message="Scheduled grid frequency curtailment resolved; plant output restored to nominal dispatch",
                    expected_power_kw=35000.0,
                    actual_power_kw=35000.0,
                    deviation_percent=0.0,
                    is_resolved=True,
                    resolved_at=now - timedelta(days=1),
                ),
            ]
            session.add_all(alerts)
            logger.info(f"Inserted {len(alerts)} sample anomaly alerts.")

        # ── 7. Seed Recent SCADA Telemetry ───────────────────────────────────
        existing_scada = await session.scalar(
            select(ScadaReading.id).where(ScadaReading.plant_id == plant_1.id)
        )
        if not existing_scada:
            readings = []
            for m in range(0, 180, 10):  # Last 3 hours, every 10 min
                t = now - timedelta(minutes=m)
                h = t.hour + t.minute / 60.0
                gen = generate_diurnal_power(h, peak_kw=43000.0)
                irr = round(gen / 50.0 + 20.0, 1) if gen > 0 else 0.0
                readings.append(
                    ScadaReading(
                        plant_id=plant_1.id,
                        timestamp=t,
                        power_kw=gen,
                        irradiance_w_m2=irr,
                        temperature_c=34.2,
                        wind_speed_m_s=3.4,
                        module_temperature_c=48.5 if gen > 0 else 28.0,
                        inverter_power_kw=round(gen * 0.985, 2),
                        expected_power_kw=gen,
                    )
                )
            session.add_all(readings)
            logger.info(f"Inserted {len(readings)} SCADA telemetry points.")

        await session.commit()
        logger.info("Demo powerplant seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
