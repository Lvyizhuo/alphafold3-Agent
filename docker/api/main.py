"""FastAPI application entry point for AlphaFold 3 Inference API.

Responsibilities
----------------
- Create the FastAPI application instance
- Configure CORS middleware
- Register all v1 API routes (from ``router.py``)
- Startup event  -> initialise SQLite database (``database.init_db``)
- Shutdown event -> close database connection  (``database.close_db``)
- Configure structured logging via loguru
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from api.config import settings
from api.cleanup import start_cleanup, stop_cleanup
from api.database import init_db, close_db
from api.router import router as v1_router


# ---------------------------------------------------------------------------
# Logging configuration (loguru)
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Set up loguru with console + file sinks."""
    logger.remove()  # remove default stderr handler

    # Console sink
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File sink with rotation and retention
    logger.add(
        settings.LOG_FILE,
        level=settings.LOG_LEVEL,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        ),
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="gz",
        encoding="utf-8",
    )

    logger.info(
        "Logging configured: level={}, file={}",
        settings.LOG_LEVEL,
        settings.LOG_FILE,
    )


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    _configure_logging()
    logger.info(
        "Starting {} v{} (host={}, port={})",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.HOST,
        settings.PORT,
    )
    await init_db()
    start_cleanup()
    logger.info("Application startup complete")
    yield
    stop_cleanup()
    await close_db()
    logger.info("Application shutdown complete")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RESTful API wrapping AlphaFold 3 protein-structure prediction",
    lifespan=lifespan,
)

# --- CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register v1 routes ---
app.include_router(v1_router)


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["root"])
async def root():
    """Service information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_prefix": "/api/v1",
    }


# ---------------------------------------------------------------------------
# Direct execution (development convenience)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
