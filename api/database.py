"""Async database engine, session factory, and initialization for SQLite.

Uses SQLAlchemy 2.0 async API with aiosqlite as the driver.
Provides:
  - get_db: FastAPI dependency injection for database sessions
  - init_db: creates all tables defined in models.py
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.models import Base

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/app/data/alphafold3.db")

# aiosqlite requires the sqlite+aiosqlite:// scheme
DATABASE_URL: str = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # SQLite-specific: allow same connection across threads is not needed
    # with aiosqlite since each task gets its own connection.
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Usage in a route::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables defined in models.Base metadata.

    Should be called once during application startup (lifespan event).
    Tables are created only if they do not already exist.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

async def close_db() -> None:
    """Dispose of the engine connection pool.

    Should be called during application shutdown.
    """
    await engine.dispose()
