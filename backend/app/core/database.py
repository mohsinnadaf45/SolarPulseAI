"""
app/core/database.py

SQLAlchemy 2.x async database setup.
- AsyncEngine
- async_sessionmaker
- AsyncSession
- DeclarativeBase
- get_db dependency
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session.
    The session is automatically closed after the request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Database initialisation helper (development only)
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """
    Create all tables based on current metadata.

    Call this explicitly from a startup script or migration helper.
    It does NOT drop existing tables.
    """
    async with engine.begin() as conn:
        # Import all models so metadata is populated before create_all
        import app.models  # noqa: F401  # ensures all models are registered
        await conn.run_sync(Base.metadata.create_all)
