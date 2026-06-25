"""
业务逻辑层：TaskService 类。

封装所有任务相关的业务操作，包括：
- 创建任务记录
- 调用 AlphaFoldRunner 执行推理并更新数据库
- 获取任务详情和列表
- 获取任务结果详情
- 删除任务及其文件
- 获取系统统计信息
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.alphafold import AlphaFoldRunner, InferenceOutput, validate_input_json
from api.models import Prediction, Task
from api.schemas import (
    PredictionResponse,
    TaskDetail,
    TaskListResponse,
    TaskResponse,
    StatsResponse,
    TaskStats,
)

logger = logging.getLogger(__name__)


class TaskService:
    """AlphaFold 3 推理任务业务逻辑服务。

    职责：
    1. 协调 AlphaFoldRunner 与数据库之间的数据流转
    2. 封装文件系统操作（创建/删除任务目录）
    3. 提供分页查询和统计聚合
    """

    def __init__(self, runner: AlphaFoldRunner, storage_path: str) -> None:
        """初始化 TaskService。

        Args:
            runner: AlphaFoldRunner 实例，用于执行推理。
            storage_path: 任务文件存储根目录（如 /app/storage）。
        """
        self._runner = runner
        self._storage_path = Path(storage_path)

    # ------------------------------------------------------------------
    # create_task
    # ------------------------------------------------------------------

    async def create_task(
        self,
        db: AsyncSession,
        input_json: Dict[str, Any],
        task_id: str,
    ) -> Task:
        """创建任务记录并保存输入文件。

        流程：
        1. 验证输入 JSON 格式
        2. 构建输入摘要
        3. 创建 Task ORM 对象并持久化
        4. 保存输入 JSON 到文件系统

        Args:
            db: 异步数据库会话。
            input_json: AlphaFold 3 格式的输入 JSON 字典。
            task_id: 任务唯一标识（UUID）。

        Returns:
            创建的 Task ORM 对象。

        Raises:
            ValueError: 输入 JSON 格式无效。
        """
        # 验证输入 JSON
        validate_input_json(input_json)

        job_name: str = input_json["name"]
        model_seeds: List[int] = input_json.get("modelSeeds", [0])
        sequences: List[Dict[str, Any]] = input_json.get("sequences", [])

        # 构建输入摘要
        input_summary = self._build_input_summary(input_json)

        # 创建任务目录
        task_dir = self._storage_path / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # 保存输入 JSON 到任务目录
        input_file_path = task_dir / "input.json"
        input_file_path.write_text(
            json.dumps(input_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 创建 ORM 对象
        task = Task(
            id=task_id,
            name=job_name,
            status="completed",  # 默认状态，推理失败时更新为 failed
            input_data=json.dumps(input_json, ensure_ascii=False),
            input_summary=json.dumps(input_summary, ensure_ascii=False),
            model_seeds=json.dumps(model_seeds),
            created_at=datetime.now(timezone.utc),
        )

        db.add(task)
        await db.flush()
        logger.info("任务已创建: task_id=%s, name=%s", task_id, job_name)

        return task

    # ------------------------------------------------------------------
    # run_inference
    # ------------------------------------------------------------------

    async def run_inference(
        self,
        db: AsyncSession,
        task: Task,
        input_json: Dict[str, Any],
    ) -> Task:
        """调用 AlphaFoldRunner 执行推理，完成后更新数据库。

        流程：
        1. 调用 runner.run_inference 同步执行推理
        2. 成功时：解析结果，更新 Task 和创建 Prediction 记录
        3. 失败时：更新 Task 状态为 failed 并记录错误信息

        Args:
            db: 异步数据库会话。
            task: 已创建的 Task ORM 对象。
            input_json: AlphaFold 3 格式的输入 JSON 字典。

        Returns:
            更新后的 Task ORM 对象。
        """
        task_id = task.id
        start_time = time.monotonic()

        try:
            # 执行推理（同步阻塞）
            output: InferenceOutput = self._runner.run_inference(
                input_json=input_json,
                task_id=task_id,
            )

            elapsed = time.monotonic() - start_time

            # 更新 Task 记录
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            task.output_path = output.output_dir
            task.best_seed = output.best_seed
            task.best_sample = output.best_sample
            task.ranking_score = output.best_ranking_score
            task.best_ptm = output.best_ptm
            task.best_iptm = output.best_iptm

            model_seeds = input_json.get("modelSeeds", [0])
            # num_samples 通过 all_predictions 的数量除以种子数推算
            num_predictions = len(output.all_predictions)
            task.num_seeds = len(model_seeds)
            task.num_samples = (
                num_predictions // len(model_seeds) if model_seeds else num_predictions
            )

            # 创建 Prediction 记录
            await self._create_predictions(db, task_id, output)

            await db.flush()
            logger.info(
                "推理完成: task_id=%s, elapsed=%.1fs, best_ranking_score=%.4f",
                task_id, elapsed, output.best_ranking_score,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            error_msg = str(exc)[:2000]  # 截断过长的错误信息

            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            task.error_message = error_msg

            await db.flush()
            logger.error(
                "推理失败: task_id=%s, elapsed=%.1fs, error=%s",
                task_id, elapsed, error_msg,
            )

        return task

    # ------------------------------------------------------------------
    # get_task
    # ------------------------------------------------------------------

    async def get_task(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> Optional[TaskDetail]:
        """获取任务详情（含预测列表）。

        Args:
            db: 异步数据库会话。
            task_id: 任务唯一标识。

        Returns:
            TaskDetail 对象，如果任务不存在则返回 None。
        """
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            return None

        return self._task_to_detail(task)

    # ------------------------------------------------------------------
    # list_tasks
    # ------------------------------------------------------------------

    async def list_tasks(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> TaskListResponse:
        """列出任务（支持分页、状态过滤）。

        Args:
            db: 异步数据库会话。
            page: 页码（从 1 开始）。
            page_size: 每页数量。
            status: 可选的状态过滤（completed / failed）。

        Returns:
            TaskListResponse 分页结果。
        """
        # 基础查询
        base_query = select(Task)
        count_query = select(func.count()).select_from(Task)

        if status is not None:
            base_query = base_query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询，按创建时间倒序
        offset = (page - 1) * page_size
        stmt = (
            base_query
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        items = [self._task_to_response(t) for t in tasks]

        return TaskListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # get_task_results
    # ------------------------------------------------------------------

    async def get_task_results(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> Optional[TaskDetail]:
        """获取任务结果详情（与 get_task 相同，语义区分）。

        Args:
            db: 异步数据库会话。
            task_id: 任务唯一标识。

        Returns:
            TaskDetail 对象，如果任务不存在则返回 None。
        """
        return await self.get_task(db, task_id)

    # ------------------------------------------------------------------
    # delete_task
    # ------------------------------------------------------------------

    async def delete_task(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> bool:
        """删除任务及其文件。

        流程：
        1. 从数据库查询任务
        2. 删除文件系统中的任务目录
        3. 删除数据库记录（级联删除 predictions）

        Args:
            db: 异步数据库会话。
            task_id: 任务唯一标识。

        Returns:
            True 如果删除成功，False 如果任务不存在。
        """
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            return False

        # 删除文件系统中的任务目录
        task_dir = self._storage_path / "tasks" / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)
            logger.info("已删除任务目录: %s", task_dir)

        # 删除数据库记录（cascade 会自动删除 predictions）
        await db.delete(task)
        await db.flush()
        logger.info("已删除任务记录: task_id=%s", task_id)

        return True

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    async def get_stats(
        self,
        db: AsyncSession,
    ) -> StatsResponse:
        """获取系统统计信息。

        统计项：
        - 任务总数、完成数、失败数

        Args:
            db: 异步数据库会话。

        Returns:
            StatsResponse 统计信息。
        """
        # 总任务数
        total_stmt = select(func.count()).select_from(Task)
        total_result = await db.execute(total_stmt)
        total = total_result.scalar() or 0

        # 完成任务数
        completed_stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.status == "completed")
        )
        completed_result = await db.execute(completed_stmt)
        completed = completed_result.scalar() or 0

        # 失败任务数
        failed_stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.status == "failed")
        )
        failed_result = await db.execute(failed_stmt)
        failed = failed_result.scalar() or 0

        return StatsResponse(
            tasks=TaskStats(
                total=total,
                completed=completed,
                failed=failed,
            ),
        )

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    async def _create_predictions(
        self,
        db: AsyncSession,
        task_id: str,
        output: InferenceOutput,
    ) -> None:
        """为推理输出中的每个预测创建 Prediction 记录。

        Args:
            db: 异步数据库会话。
            task_id: 任务唯一标识。
            output: 推理输出对象。
        """
        output_dir = Path(output.output_dir)
        job_name = output.job_name

        for pred in output.all_predictions:
            # 计算每个预测的文件路径
            seed_dir_name = f"seed-{pred.seed}_sample-{pred.sample}"
            seed_dir = output_dir / seed_dir_name

            cif_path = None
            confidences_path = None
            summary_path = None

            # 预测级别的文件（在 seed_sample 子目录下）
            cif_file = seed_dir / f"{job_name}_{seed_dir_name}_model.cif"
            if cif_file.exists():
                cif_path = str(cif_file)

            confidences_file = seed_dir / f"{job_name}_{seed_dir_name}_confidences.json"
            if confidences_file.exists():
                confidences_path = str(confidences_file)

            summary_file = seed_dir / f"{job_name}_{seed_dir_name}_summary_confidences.json"
            if summary_file.exists():
                summary_path = str(summary_file)

            # 如果是最佳预测且子目录下没有文件，使用顶层文件
            is_best = (
                pred.seed == output.best_seed
                and pred.sample == output.best_sample
            )
            if is_best:
                if cif_path is None and output.best_model_cif:
                    cif_path = output.best_model_cif
                if confidences_path is None and output.best_confidences_json:
                    confidences_path = output.best_confidences_json
                if summary_path is None and output.best_summary_confidences_json:
                    summary_path = output.best_summary_confidences_json

            prediction = Prediction(
                task_id=task_id,
                seed=pred.seed,
                sample_idx=pred.sample,
                cif_path=cif_path,
                confidences_path=confidences_path,
                summary_path=summary_path,
                ranking_score=pred.ranking_score,
                ptm=pred.ptm,
                iptm=pred.iptm,
            )
            db.add(prediction)

    @staticmethod
    def _build_input_summary(input_json: Dict[str, Any]) -> Dict[str, Any]:
        """从输入 JSON 构建摘要信息。

        Args:
            input_json: 原始输入 JSON。

        Returns:
            摘要字典，包含 name、sequences 简化信息、num_seeds、num_samples。
        """
        sequences_summary = []
        for seq_def in input_json.get("sequences", []):
            for seq_type in ("protein", "rna", "dna", "ligand"):
                if seq_type in seq_def:
                    seq_data = seq_def[seq_type]
                    chain_id = seq_data.get("id", "?")
                    # 对于蛋白质和核酸，有序列字段；配体有 SMILES
                    sequence = seq_data.get("sequence", "")
                    length = len(sequence) if sequence else 0
                    sequences_summary.append({
                        "type": seq_type,
                        "id": chain_id,
                        "length": length,
                    })
                    break

        model_seeds = input_json.get("modelSeeds", [0])

        return {
            "name": input_json.get("name", ""),
            "sequences": sequences_summary,
            "num_seeds": len(model_seeds),
        }

    @staticmethod
    def _task_to_response(task: Task) -> TaskResponse:
        """将 Task ORM 对象转换为 TaskResponse schema。

        Args:
            task: Task ORM 对象。

        Returns:
            TaskResponse schema 对象。
        """
        return TaskResponse(
            id=task.id,
            name=task.name,
            status=task.status,
            created_at=task.created_at,
            completed_at=task.completed_at,
            best_ptm=task.best_ptm,
            best_iptm=task.best_iptm,
            ranking_score=task.ranking_score,
        )

    @staticmethod
    def _task_to_detail(task: Task) -> TaskDetail:
        """将 Task ORM 对象转换为 TaskDetail schema（含预测列表）。

        Args:
            task: Task ORM 对象。

        Returns:
            TaskDetail schema 对象。
        """
        predictions: List[PredictionResponse] = []
        for pred in task.predictions:
            predictions.append(
                PredictionResponse(
                    id=pred.id,
                    seed=pred.seed,
                    sample_idx=pred.sample_idx,
                    cif_url=pred.cif_path,
                    confidences_url=pred.confidences_path,
                    summary_url=pred.summary_path,
                    ranking_score=pred.ranking_score,
                    ptm=pred.ptm,
                    iptm=pred.iptm,
                )
            )

        return TaskDetail(
            id=task.id,
            name=task.name,
            status=task.status,
            created_at=task.created_at,
            completed_at=task.completed_at,
            best_ptm=task.best_ptm,
            best_iptm=task.best_iptm,
            ranking_score=task.ranking_score,
            error_message=task.error_message,
            predictions=predictions,
        )
