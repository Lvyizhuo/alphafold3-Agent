"""SQLite database connection management using aiosqlite."""

import aiosqlite
from loguru import logger

from api.config import settings

# Module-level connection reference
_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Return the active database connection. Raises RuntimeError if not initialised."""
    if _db is None:
        raise RuntimeError("Database has not been initialised. Call init_db() first.")
    return _db


async def init_db() -> None:
    """Open the database connection and create tables if they don't exist."""
    global _db
    logger.info("Initialising database at {}", settings.DATABASE_PATH)
    settings.ensure_directories()

    _db = await aiosqlite.connect(settings.DATABASE_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    await _db.executescript(_SCHEMA_SQL)
    await _db.commit()
    logger.info("Database initialised successfully")


async def close_db() -> None:
    """Close the database connection gracefully."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("Database connection closed")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',

    -- input
    input_json TEXT NOT NULL,
    input_summary TEXT,

    -- output
    output_path TEXT,
    best_seed INTEGER,
    best_sample INTEGER,
    best_ranking_score REAL,
    best_ptm REAL,
    best_iptm REAL,

    -- stats
    num_seeds INTEGER,
    num_samples INTEGER,

    -- timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,

    -- error
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
"""
