"""Async database engine, session factory, and initialization for SQLite.

Uses SQLAlchemy 2.0 async API with aiosqlite as the driver.
Provides:
  - get_db: FastAPI dependency injection for database sessions
  - init_db: create tables on startup
  - close_db: dispose engine on shutdown
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from loguru import logger

from api.config import settings
from api.models import Base

# Async engine and session factory (initialized in init_db)
_engine = None
_session_factory = None


async def get_db():
    """FastAPI dependency that yields an async database session."""
    if _session_factory is None:
        raise RuntimeError("Database has not been initialised. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create the async engine and all tables if they don't exist."""
    global _engine, _session_factory

    db_url = f"sqlite+aiosqlite:///{settings.DATABASE_PATH}"
    logger.info("Initialising database at {}", settings.DATABASE_PATH)
    settings.ensure_directories()

    _engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialised successfully")


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")
