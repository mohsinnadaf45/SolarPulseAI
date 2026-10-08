import asyncio
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.plant import Plant, PlantConfig
from app.models.user import User
from app.models.forecast import ForecastRecord
from app.models.anomaly import AnomalyAlert

async def main():
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()
        print(f"Users ({len(users)}):")
        for u in users:
            print(f"  ID={u.id}, Email={u.email}, Active={u.is_active}")

        plants = (await session.execute(select(Plant))).scalars().all()
        print(f"Plants ({len(plants)}):")
        for p in plants:
            print(f"  ID={p.id}, Name={p.name}, Cap={p.capacity_kw}kW, Loc={p.location}")

        forecasts = (await session.execute(select(ForecastRecord))).scalars().all()
        print(f"Forecasts count: {len(forecasts)}")

        alerts = (await session.execute(select(AnomalyAlert))).scalars().all()
        print(f"Alerts count: {len(alerts)}")

if __name__ == "__main__":
    asyncio.run(main())
