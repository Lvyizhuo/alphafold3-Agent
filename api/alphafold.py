"""
AlphaFold 3 推理封装模块。

将 run_alphafold.py 命令行工具封装为 Python 类，提供：
- 输入 JSON 验证
- 子进程调用 run_alphafold.py
- 输出文件解析（ranking_scores.csv、summary_confidences.json、confidences.json）
- 错误处理
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True, kw_only=True)
class PredictionResult:
    """单个预测结果的置信度指标。"""

    seed: int
    sample: int
    ranking_score: float
    ptm: float | None = None
    iptm: float | None = None
    fraction_disordered: float | None = None
    has_clash: bool | None = None
    chain_ptm: list[float | None] | None = None
    chain_iptm: list[float | None] | None = None
    chain_pair_iptm: list[list[float | None]] | None = None
    chain_pair_pae_min: list[list[float | None]] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class InferenceOutput:
    """推理任务的完整输出。"""

    job_name: str
    output_dir: str

    # 最佳预测
    best_seed: int
    best_sample: int
    best_ranking_score: float
    best_ptm: float | None = None
    best_iptm: float | None = None
    best_fraction_disordered: float | None = None
    best_has_clash: bool | None = None
    best_chain_ptm: list[float | None] | None = None
    best_chain_iptm: list[float | None] | None = None
    best_chain_pair_iptm: list[list[float | None]] | None = None
    best_chain_pair_pae_min: list[list[float | None]] | None = None

    # 所有预测
    all_predictions: list[PredictionResult] = field(default_factory=list)

    # 文件路径
    best_model_cif: str | None = None
    best_confidences_json: str | None = None
    best_summary_confidences_json: str | None = None
    data_json: str | None = None
    ranking_scores_csv: str | None = None


# ---------------------------------------------------------------------------
# 输入验证
# ---------------------------------------------------------------------------

def validate_input_json(input_data: dict[str, Any]) -> None:
    """验证 AlphaFold 3 输入 JSON 格式。

    Args:
        input_data: 解析后的 JSON 字典。

    Raises:
        ValueError: 当输入格式不符合规范时。
    """

    # 检查 dialect 字段
    dialect = input_data.get("dialect")
    if dialect is not None and dialect != "alphafold3":
        raise ValueError(
            f"dialect 字段必须为 'alphafold3'，当前值: {dialect!r}"
        )

    # 检查 sequences 字段
    sequences = input_data.get("sequences")
    if not sequences:
        raise ValueError("sequences 字段不能为空")

    # 检查 name 字段
    name = input_data.get("name")
    if not name:
        raise ValueError("name 字段不能为空")

    # 检查 modelSeeds 字段
    model_seeds = input_data.get("modelSeeds")
    if not model_seeds:
        raise ValueError("modelSeeds 字段不能为空")


# ---------------------------------------------------------------------------
# AlphaFoldRunner
# ---------------------------------------------------------------------------

class AlphaFoldRunner:
    """AlphaFold 3 推理执行器。

    封装 run_alphafold.py 的调用，提供同步阻塞的推理接口。

    使用方式::

        runner = AlphaFoldRunner(
            alphafold_dir="/data2/ntt/lvyizhuo/alphafold3",
            model_dir="/root/models",
            input_dir="/app/storage/inputs",
            output_dir="/app/storage/tasks",
        )
        result = runner.run_inference(input_json={...}, task_id="uuid-string")
    """

    def __init__(
        self,
        alphafold_dir: str | Path,
        model_dir: str | Path,
        input_dir: str | Path,
        output_dir: str | Path,
        db_dir: str | Path | None = None,
        python_bin: str = "python",
    ) -> None:
        """初始化 AlphaFoldRunner。

        Args:
            alphafold_dir: AlphaFold 3 代码仓库根目录，run_alphafold.py 所在目录。
            model_dir: 模型权重文件目录。
            input_dir: 用户上传输入文件的临时存放目录。
            output_dir: 推理结果输出的根目录。
            db_dir: 搜索数据库目录。如果为 None，则使用 alphafold_dir 下的默认路径。
            python_bin: Python 解释器路径。
        """
        self._alphafold_dir = Path(alphafold_dir)
        self._model_dir = Path(model_dir)
        self._input_dir = Path(input_dir)
        self._output_dir = Path(output_dir)
        self._db_dir = Path(db_dir) if db_dir else None
        self._python_bin = python_bin

        # run_alphafold.py 的绝对路径
        self._run_script = self._alphafold_dir / "run_alphafold.py"
        if not self._run_script.exists():
            raise FileNotFoundError(
                f"run_alphafold.py 不存在: {self._run_script}"
            )

        # 确保输入目录存在
        self._input_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def alphafold_dir(self) -> Path:
        return self._alphafold_dir

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    @property
    def input_dir(self) -> Path:
        return self._input_dir

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def run_inference(
        self,
        input_json: dict[str, Any],
        task_id: str,
        timeout: int | None = None,
    ) -> InferenceOutput:
        """执行 AlphaFold 3 推理（同步阻塞）。

        流程：
        1. 验证输入 JSON 格式
        2. 保存输入 JSON 到 input_dir
        3. 调用 python run_alphafold.py --json_path ... --output_dir ...
        4. 等待执行完成
        5. 解析输出文件
        6. 返回结果

        Args:
            input_json: AlphaFold 3 格式的输入 JSON 字典。
            task_id: 任务唯一标识。
            timeout: 子进程超时时间（秒）。None 表示无超时限制。

        Returns:
            InferenceOutput 对象，包含推理结果和文件路径。

        Raises:
            ValueError: 输入 JSON 格式无效。
            RuntimeError: 推理执行失败。
            subprocess.TimeoutExpired: 推理超时。
        """
        # 1. 验证输入 JSON
        validate_input_json(input_json)

        job_name = input_json["name"]
        logger.info(
            "开始推理任务: task_id=%s, job_name=%s",
            task_id, job_name,
        )

        # 2. 保存输入 JSON
        input_path = self._input_dir / f"{task_id}.json"
        input_path.write_text(json.dumps(input_json, ensure_ascii=False, indent=2))
        logger.debug("输入 JSON 已保存: %s", input_path)

        # 3. 准备输出目录
        task_output_dir = self._output_dir / task_id / "output"
        task_output_dir.mkdir(parents=True, exist_ok=True)

        # 4. 构建命令
        cmd = self._build_command(input_path, task_output_dir)

        # 5. 执行推理
        start_time = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._alphafold_dir),
            )
        except subprocess.TimeoutExpired:
            logger.error("推理超时: task_id=%s, timeout=%ds", task_id, timeout)
            raise
        except OSError as e:
            logger.error("无法启动推理进程: task_id=%s, error=%s", task_id, e)
            raise RuntimeError(f"无法启动推理进程: {e}") from e

        elapsed = time.monotonic() - start_time
        logger.info(
            "推理进程已完成: task_id=%s, elapsed=%.1fs, returncode=%d",
            task_id, elapsed, result.returncode,
        )

        # 检查执行结果
        if result.returncode != 0:
            error_msg = self._extract_error_message(result)
            logger.error(
                "推理失败: task_id=%s, returncode=%d, stderr=%s",
                task_id, result.returncode, error_msg,
            )
            raise RuntimeError(
                f"AlphaFold 推理失败 (returncode={result.returncode}): "
                f"{error_msg}"
            )

        # 6. 解析输出文件
        return self._parse_output(
            task_output_dir=task_output_dir,
            job_name=job_name,
        )

    def _build_command(
        self,
        input_path: Path,
        output_dir: Path,
    ) -> list[str]:
        """构建 run_alphafold.py 的命令行参数。"""
        cmd = [
            self._python_bin,
            str(self._run_script),
            f"--json_path={input_path}",
            f"--output_dir={output_dir}",
            f"--model_dir={self._model_dir}",
        ]
        if self._db_dir is not None:
            cmd.append(f"--db_dir={self._db_dir}")
        return cmd

    @staticmethod
    def _extract_error_message(result: subprocess.CompletedProcess[str]) -> str:
        """从子进程结果中提取错误信息。"""
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()

        # 优先使用 stderr，其次使用 stdout 的最后几行
        if stderr:
            # 取 stderr 最后 500 字符
            return stderr[-500:]
        if stdout:
            return stdout[-500:]
        return "(无错误输出)"

    def _parse_output(
        self,
        task_output_dir: Path,
        job_name: str,
    ) -> InferenceOutput:
        """解析 AlphaFold 输出文件，构建 InferenceOutput。

        Args:
            task_output_dir: 任务输出目录（含 {job_name}_ranking_scores.csv 等）。
            job_name: 任务名称。

        Returns:
            解析后的 InferenceOutput 对象。

        Raises:
            RuntimeError: 输出文件缺失或格式错误。
        """
        # 读取 ranking_scores.csv
        ranking_csv_path = task_output_dir / f"{job_name}_ranking_scores.csv"
        all_predictions = self._parse_ranking_scores(ranking_csv_path)

        if not all_predictions:
            raise RuntimeError(
                f"ranking_scores.csv 为空或不存在: {ranking_csv_path}"
            )

        # 找到最佳预测
        best = max(all_predictions, key=lambda p: p.ranking_score)

        # 读取最佳预测的 summary_confidences.json
        summary_path = task_output_dir / f"{job_name}_summary_confidences.json"
        summary = self._read_json(summary_path)

        # 从 summary 中补充最佳预测的详细指标
        best_ptm = summary.get("ptm") if summary else best.ptm
        best_iptm = summary.get("iptm") if summary else best.iptm
        best_fraction_disordered = (
            summary.get("fraction_disordered") if summary else None
        )
        # has_clash 在 JSON 中可能存储为 0.0/1.0 (float) 或 bool
        raw_has_clash = summary.get("has_clash") if summary else None
        if raw_has_clash is not None:
            best_has_clash = bool(raw_has_clash)
        else:
            best_has_clash = None
        best_chain_ptm = summary.get("chain_ptm") if summary else None
        best_chain_iptm = summary.get("chain_iptm") if summary else None
        best_chain_pair_iptm = summary.get("chain_pair_iptm") if summary else None
        best_chain_pair_pae_min = (
            summary.get("chain_pair_pae_min") if summary else None
        )

        # 文件路径
        best_model_cif = task_output_dir / f"{job_name}_model.cif"
        best_confidences_json = task_output_dir / f"{job_name}_confidences.json"
        best_summary_confidences_json = summary_path
        data_json = task_output_dir / f"{job_name}_data.json"

        return InferenceOutput(
            job_name=job_name,
            output_dir=str(task_output_dir),
            best_seed=best.seed,
            best_sample=best.sample,
            best_ranking_score=best.ranking_score,
            best_ptm=best_ptm,
            best_iptm=best_iptm,
            best_fraction_disordered=best_fraction_disordered,
            best_has_clash=best_has_clash,
            best_chain_ptm=best_chain_ptm,
            best_chain_iptm=best_chain_iptm,
            best_chain_pair_iptm=best_chain_pair_iptm,
            best_chain_pair_pae_min=best_chain_pair_pae_min,
            all_predictions=all_predictions,
            best_model_cif=str(best_model_cif) if best_model_cif.exists() else None,
            best_confidences_json=(
                str(best_confidences_json)
                if best_confidences_json.exists()
                else None
            ),
            best_summary_confidences_json=(
                str(best_summary_confidences_json)
                if best_summary_confidences_json.exists()
                else None
            ),
            data_json=str(data_json) if data_json.exists() else None,
            ranking_scores_csv=(
                str(ranking_csv_path) if ranking_csv_path.exists() else None
            ),
        )

    @staticmethod
    def _parse_ranking_scores(csv_path: Path) -> list[PredictionResult]:
        """解析 ranking_scores.csv 文件。

        CSV 格式：seed,sample,ranking_score

        Args:
            csv_path: CSV 文件路径。

        Returns:
            PredictionResult 列表。
        """
        if not csv_path.exists():
            return []

        predictions: list[PredictionResult] = []
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    predictions.append(
                        PredictionResult(
                            seed=int(row["seed"]),
                            sample=int(row["sample"]),
                            ranking_score=float(row["ranking_score"]),
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(
                        "跳过 ranking_scores.csv 中的无效行: %s, error=%s",
                        row, e,
                    )
        return predictions

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        """读取 JSON 文件，失败时返回 None。"""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("无法读取 JSON 文件 %s: %s", path, e)
            return None
