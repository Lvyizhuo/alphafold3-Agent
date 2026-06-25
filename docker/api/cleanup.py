"""Scheduled cleanup task for removing expired task data.

Deletes tasks older than DATA_RETENTION_DAYS (default 30) from both the
SQLite database and the filesystem.  Uses APScheduler to run once per day
at 03:00 (server local time).

Typical usage (in the FastAPI lifespan)::

    from api.cleanup import start_cleanup, stop_cleanup

    @asynccontextmanager
    async def lifespan(app):
        ...
        start_cleanup()
        yield
        stop_cleanup()
        ...
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from api.config import settings
from api.database import get_db

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None


# ---------------------------------------------------------------------------
# Core cleanup logic
# ---------------------------------------------------------------------------

async def cleanup_old_tasks() -> int:
    """Delete tasks and their files that exceed the retention period.

    Returns the number of tasks deleted.
    """
    retention_days = settings.DATA_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    logger.info(
        "Starting cleanup: removing tasks created before {} (retention={} days)",
        cutoff_iso,
        retention_days,
    )

    db = await get_db()

    # 1. Query expired tasks
    cursor = await db.execute(
        "SELECT id, job_name, output_path FROM tasks WHERE created_at < ?",
        (cutoff_iso,),
    )
    rows = await cursor.fetchall()

    if not rows:
        logger.info("Cleanup finished: no expired tasks found")
        return 0

    deleted_count = 0
    failed_count = 0

    for row in rows:
        task_id: str = row["id"]
        job_name: str = row["job_name"]
        output_path: str | None = row["output_path"]

        # 2. Delete task directory from filesystem
        task_dir = Path(settings.STORAGE_PATH) / "tasks" / task_id
        if task_dir.exists():
            try:
                shutil.rmtree(task_dir)
                logger.debug("Deleted task directory: {}", task_dir)
            except OSError as exc:
                logger.error(
                    "Failed to delete directory for task {} ({}): {}",
                    task_id,
                    job_name,
                    exc,
                )
                failed_count += 1
                continue  # keep DB record so it can be retried next run

        # 3. Delete database record
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        deleted_count += 1
        logger.debug("Deleted DB record for task {} ({})", task_id, job_name)

    await db.commit()

    logger.info(
        "Cleanup finished: deleted={}, failed={}",
        deleted_count,
        failed_count,
    )
    return deleted_count


# ---------------------------------------------------------------------------
# APScheduler integration
# ---------------------------------------------------------------------------

def start_cleanup() -> None:
    """Initialise and start the APScheduler with the daily cleanup job."""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Cleanup scheduler already running, skipping start")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        cleanup_old_tasks,
        trigger=CronTrigger(hour=3, minute=0),  # daily at 03:00 UTC
        id="cleanup_old_tasks",
        name="Cleanup expired tasks",
        replace_existing=True,
        misfire_grace_time=3600,  # allow 1-hour grace window
    )
    _scheduler.start()
    logger.info("Cleanup scheduler started (daily at 03:00 UTC)")


def stop_cleanup() -> None:
    """Shut down the APScheduler gracefully."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Cleanup scheduler stopped")
