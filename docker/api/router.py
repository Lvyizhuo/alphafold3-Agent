"""API router registration.

All v1 routers are collected here and mounted on a single ``APIRouter``
so that ``main.py`` only needs a single ``include_router`` call.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

# ---------------------------------------------------------------------------
# Health / Stats (always available)
# ---------------------------------------------------------------------------

@router.get("/health", tags=["system"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "api": {"status": "up"},
        },
    }


@router.get("/stats", tags=["system"])
async def system_stats():
    """Placeholder for system statistics."""
    return {"message": "Stats endpoint – not yet implemented"}


# ---------------------------------------------------------------------------
# Predict (placeholder – will be implemented in predict.py)
# ---------------------------------------------------------------------------

@router.post("/predict", tags=["predict"], status_code=501)
async def predict_placeholder():
    """Placeholder for synchronous prediction endpoint."""
    return {"message": "Predict endpoint – not yet implemented"}


# ---------------------------------------------------------------------------
# Tasks (placeholder – will be implemented in tasks.py)
# ---------------------------------------------------------------------------

@router.get("/tasks", tags=["tasks"])
async def list_tasks_placeholder():
    """Placeholder for task list endpoint."""
    return {"message": "Tasks list endpoint – not yet implemented"}


@router.get("/tasks/{task_id}", tags=["tasks"])
async def get_task_placeholder(task_id: str):
    """Placeholder for single task detail endpoint."""
    return {"task_id": task_id, "message": "Task detail endpoint – not yet implemented"}


@router.get("/tasks/{task_id}/results", tags=["results"])
async def get_results_placeholder(task_id: str):
    """Placeholder for task results endpoint."""
    return {"task_id": task_id, "message": "Results endpoint – not yet implemented"}


@router.get("/tasks/{task_id}/results/confidences", tags=["results"])
async def get_confidences_placeholder(task_id: str):
    """Placeholder for detailed confidence endpoint."""
    return {"task_id": task_id, "message": "Confidences endpoint – not yet implemented"}


@router.get("/tasks/{task_id}/files/{filename:path}", tags=["files"])
async def download_file_placeholder(task_id: str, filename: str):
    """Placeholder for file download endpoint."""
    return {"task_id": task_id, "filename": filename, "message": "File download endpoint – not yet implemented"}


@router.get("/tasks/{task_id}/download", tags=["files"])
async def download_zip_placeholder(task_id: str):
    """Placeholder for ZIP download endpoint."""
    return {"task_id": task_id, "message": "ZIP download endpoint – not yet implemented"}
