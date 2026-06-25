"""FastAPI API router for AlphaFold 3 inference service.

Defines all REST API endpoints with dependency injection, input validation,
error handling, and proper HTTP status codes.

Endpoints:
    POST /api/v1/predict              - Synchronous inference (blocking)
    GET  /api/v1/tasks                - Task list with pagination
    GET  /api/v1/tasks/{task_id}      - Task detail
    GET  /api/v1/tasks/{task_id}/results - Results detail
    DELETE /api/v1/tasks/{task_id}    - Delete task
    GET  /api/v1/tasks/{task_id}/download/{filename} - Download file
    GET  /api/v1/stats                - System statistics
    GET  /health                      - Health check
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.schemas import (
    ErrorResponse,
    StatsResponse,
    TaskDetail,
    TaskListResponse,
)
from api.service import TaskService
from api.alphafold import AlphaFoldRunner

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Dependency injection: AlphaFoldRunner & TaskService singletons
# ---------------------------------------------------------------------------

_runner: AlphaFoldRunner | None = None
_service: TaskService | None = None


def _get_runner() -> AlphaFoldRunner:
    """Lazily create and return the global AlphaFoldRunner singleton."""
    global _runner
    if _runner is None:
        _runner = AlphaFoldRunner(
            alphafold_dir=settings.ALPHAFOLD_DIR,
            model_dir=settings.MODEL_DIR,
            input_dir=settings.INPUT_DIR,
            output_dir=settings.OUTPUT_DIR,
            db_dir=settings.DB_DIR,
        )
    return _runner


def get_service() -> TaskService:
    """FastAPI dependency that returns the global TaskService singleton."""
    global _service
    if _service is None:
        _service = TaskService(
            runner=_get_runner(),
            storage_path=settings.STORAGE_PATH,
        )
    return _service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(status_code: int, code: str, message: str, details: str | None = None) -> HTTPException:
    """Build an HTTPException with the standard ErrorResponse body."""
    body = ErrorResponse(
        error={"code": code, "message": message, "details": details}
    ).model_dump()
    return HTTPException(status_code=status_code, detail=body)


# File extension to Content-Type mapping for downloads
_CONTENT_TYPES: dict[str, str] = {
    ".cif": "chemical/x-mmcif",
    ".json": "application/json",
    ".csv": "text/csv",
    ".zip": "application/zip",
    ".md": "text/markdown",
}


def _guess_content_type(filename: str) -> str:
    """Return the MIME type for *filename* based on its extension."""
    suffix = Path(filename).suffix.lower()
    return _CONTENT_TYPES.get(suffix, "application/octet-stream")


# ---------------------------------------------------------------------------
# POST /api/v1/predict
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/predict",
    response_model=TaskDetail,
    status_code=200,
    summary="提交预测任务（同步推理）",
    description=(
        "接收 AlphaFold 3 格式的 JSON 文件，同步执行推理并返回完整结果。"
        "客户端阻塞等待推理完成，无超时限制。"
    ),
    responses={
        400: {"model": ErrorResponse, "description": "输入格式错误"},
        413: {"model": ErrorResponse, "description": "文件过大"},
        500: {"model": ErrorResponse, "description": "推理失败"},
    },
)
async def predict(
    file: Annotated[UploadFile, File(description="AlphaFold 3 格式的 JSON 文件")],
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> TaskDetail:
    """Synchronous prediction endpoint.

    Flow:
    1. Read and validate the uploaded JSON file (<= 10 MB).
    2. Parse JSON, check dialect / sequences.
    3. Create task record in DB.
    4. Run AlphaFold 3 inference (blocking).
    5. Return full task detail including predictions.
    """
    # --- 1. Read file content ---
    content = await file.read()

    # Check file size (10 MB)
    max_bytes = settings.upload_size_bytes
    if len(content) > max_bytes:
        raise _error_response(
            status_code=413,
            code="FILE_TOO_LARGE",
            message="文件大小超过限制",
            details=f"最大允许 {settings.MAX_UPLOAD_SIZE_MB}MB，当前文件 {len(content) / 1024 / 1024:.1f}MB",
        )

    # --- 2. Parse JSON ---
    try:
        input_json: Dict[str, Any] = json.loads(content)
    except (json.JSONDecodeError, ValueError) as exc:
        raise _error_response(
            status_code=400,
            code="INVALID_JSON",
            message="输入文件不是有效的 JSON 格式",
            details=str(exc)[:500],
        )

    # --- 3. Generate task ID and create task ---
    task_id = str(uuid.uuid4())
    logger.info("收到预测请求: task_id=%s, filename=%s", task_id, file.filename)

    try:
        task = await service.create_task(db, input_json, task_id)
    except ValueError as exc:
        raise _error_response(
            status_code=400,
            code="INVALID_INPUT",
            message="输入 JSON 格式不符合 AlphaFold 3 规范",
            details=str(exc)[:500],
        )

    # --- 4. Run inference (blocking) ---
    task = await service.run_inference(db, task, input_json)

    # --- 5. Build response ---
    detail = await service.get_task(db, task_id)
    if detail is None:
        # Should never happen, but guard against race conditions
        raise _error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="任务创建成功但无法读取结果",
        )

    logger.info(
        "预测请求完成: task_id=%s, status=%s",
        task_id, task.status,
    )
    return detail


# ---------------------------------------------------------------------------
# GET /api/v1/tasks
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/tasks",
    response_model=TaskListResponse,
    summary="获取历史任务列表",
    description="获取历史任务列表，支持分页。按创建时间倒序排列。",
)
async def list_tasks(
    page: Annotated[int, Query(ge=1, description="页码（从 1 开始）")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> TaskListResponse:
    """Return a paginated list of historical tasks."""
    return await service.list_tasks(db, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/{task_id}
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/tasks/{task_id}",
    response_model=TaskDetail,
    summary="查询历史任务详情",
    description="根据任务 ID 查询历史任务详情，包含预测列表。",
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
    },
)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> TaskDetail:
    """Return full details for a single task."""
    detail = await service.get_task(db, task_id)
    if detail is None:
        raise _error_response(
            status_code=404,
            code="TASK_NOT_FOUND",
            message="任务不存在",
            details=f"task_id={task_id}",
        )
    return detail


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/{task_id}/results
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/tasks/{task_id}/results",
    response_model=TaskDetail,
    summary="获取推理结果详情",
    description="获取历史任务的完整推理结果，包含所有预测的排名和置信度指标。",
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
    },
)
async def get_task_results(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> TaskDetail:
    """Return full results for a completed task."""
    detail = await service.get_task_results(db, task_id)
    if detail is None:
        raise _error_response(
            status_code=404,
            code="TASK_NOT_FOUND",
            message="任务不存在",
            details=f"task_id={task_id}",
        )
    return detail


# ---------------------------------------------------------------------------
# DELETE /api/v1/tasks/{task_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/api/v1/tasks/{task_id}",
    summary="删除任务",
    description="删除指定任务及其所有结果文件和数据库记录。",
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
    },
)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> Dict[str, Any]:
    """Delete a task and its associated files."""
    deleted = await service.delete_task(db, task_id)
    if not deleted:
        raise _error_response(
            status_code=404,
            code="TASK_NOT_FOUND",
            message="任务不存在",
            details=f"task_id={task_id}",
        )
    logger.info("任务已删除: task_id=%s", task_id)
    return {"message": "任务已删除", "task_id": task_id}


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/{task_id}/download/{filename}
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/tasks/{task_id}/download/{filename}",
    summary="下载结果文件",
    description="下载指定任务的结果文件。支持的文件类型：model.cif、confidences.json、summary_confidences.json、data.json、ranking_scores.csv。",
    responses={
        404: {"model": ErrorResponse, "description": "任务或文件不存在"},
    },
)
async def download_file(
    task_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> FileResponse:
    """Download a result file for a given task.

    Security: path traversal is prevented by checking that the resolved
    path stays inside the task's output directory.
    """
    # --- Look up task ---
    detail = await service.get_task(db, task_id)
    if detail is None:
        raise _error_response(
            status_code=404,
            code="TASK_NOT_FOUND",
            message="任务不存在",
            details=f"task_id={task_id}",
        )

    # --- Locate output directory ---
    # The output_path is stored in the DB; reconstruct from storage_path
    task_output_dir = Path(settings.STORAGE_PATH) / "tasks" / task_id / "output"
    if not task_output_dir.exists():
        raise _error_response(
            status_code=404,
            code="FILE_NOT_FOUND",
            message="结果文件不存在",
            details=f"任务输出目录不存在: {task_output_dir}",
        )

    # --- Resolve and validate file path ---
    file_path = (task_output_dir / filename).resolve()

    # Prevent path traversal
    if not str(file_path).startswith(str(task_output_dir.resolve())):
        raise _error_response(
            status_code=400,
            code="INVALID_INPUT",
            message="非法的文件名",
            details="文件名包含路径遍历字符",
        )

    if not file_path.is_file():
        raise _error_response(
            status_code=404,
            code="FILE_NOT_FOUND",
            message="结果文件不存在",
            details=f"filename={filename}",
        )

    # --- Determine content type and download name ---
    content_type = _guess_content_type(filename)
    # Prefix with job name if available for a friendlier download name
    download_name = filename

    logger.info("文件下载: task_id=%s, filename=%s", task_id, filename)
    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=download_name,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/stats
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/stats",
    response_model=StatsResponse,
    summary="获取系统统计信息",
    description="获取系统运行统计信息，包括任务总数、完成数、失败数。",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_service),
) -> StatsResponse:
    """Return system-level statistics."""
    return await service.get_stats(db)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    summary="健康检查",
    description="检查系统各组件状态：API、数据库、存储。",
)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Check system health.

    Probes:
    - api: always up if this endpoint responds.
    - database: execute a trivial query.
    - storage: check that the storage directory exists.
    """
    components: Dict[str, Any] = {}

    # API
    components["api"] = {"status": "up"}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = {"status": "up"}
    except Exception as exc:
        logger.error("健康检查 - 数据库异常: %s", exc)
        components["database"] = {"status": "down", "error": str(exc)[:200]}

    # Storage
    storage_path = Path(settings.STORAGE_PATH)
    if storage_path.exists() and storage_path.is_dir():
        components["storage"] = {"status": "up"}
    else:
        components["storage"] = {"status": "down", "error": f"目录不存在: {storage_path}"}

    # Overall status
    all_up = all(c.get("status") == "up" for c in components.values())
    overall_status = "healthy" if all_up else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
