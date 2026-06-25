"""Pydantic schemas for AlphaFold 3 inference service API.

Defines request/response models for API validation and serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    """Request schema for creating a new prediction task.

    Used when the client submits input data via POST /api/v1/predict.
    Accepts structured input fields (name, sequences, modelSeeds) that
    mirror the AlphaFold 3 JSON input format.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Task name, derived from the AlphaFold 3 input JSON 'name' field.",
        examples=["test_protein"],
    )
    sequences: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description=(
            "List of sequence definitions from the AlphaFold 3 input JSON. "
            "Each entry is a dict with a 'protein', 'rna', 'dna', or 'ligand' key."
        ),
        examples=[
            [
                {
                    "protein": {
                        "id": "A",
                        "sequence": "GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGLFARYLRASGYPISILDREDWAVAESILANADVVIVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHTGAVLGLHPMFGADIASMAKQVVVRCDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLSKQPINLANLLALSSPIYRLELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKVRDWFGDYSEQFLKESRQLLQQANDLKQG",
                    }
                }
            ]
        ],
    )
    modelSeeds: Optional[List[int]] = Field(
        default=None,
        description="Optional list of random seeds for reproducibility. Defaults to [0] if not provided.",
        examples=[[42]],
    )

    @field_validator("sequences")
    @classmethod
    def validate_sequences_not_empty(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not v:
            raise ValueError("sequences must not be empty")
        return v


class DNAPredictRequest(BaseModel):
    """Request schema for DNA structure prediction from EVO2 output.

    Accepts a DNA sequence (from EVO2 generation) and automatically:
    1. Generates the reverse-complement strand (B chain).
    2. Builds the AlphaFold 3 input JSON for double-strand DNA prediction.
    """

    sequence: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="DNA 正向链序列（仅包含 A/T/C/G 碱基）。互补链自动生成。",
        examples=["ATCGATCGATCGATCG"],
    )
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="任务名称。不填则自动生成。",
        examples=["dna_evo2_prediction"],
    )
    modelSeeds: Optional[List[int]] = Field(
        default=None,
        description="随机种子列表。不填则默认使用 [42]。",
        examples=[[42]],
    )

    @field_validator("sequence")
    @classmethod
    def validate_dna_sequence(cls, v: str) -> str:
        v = v.strip().upper()
        valid_bases = set("ATCG")
        invalid = set(v) - valid_bases
        if invalid:
            raise ValueError(
                f"DNA 序列包含非法字符: {invalid}。仅允许 A/T/C/G。"
            )
        return v


# ---------------------------------------------------------------------------
# Prediction response schemas
# ---------------------------------------------------------------------------

class PredictionResponse(BaseModel):
    """Response schema for a single prediction within a task.

    Maps to the 'predictions' table in the database.
    URL fields are constructed from stored file paths at response time.
    """

    id: int = Field(
        ...,
        description="Prediction auto-increment ID.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed used for this prediction.",
    )
    sample_idx: int = Field(
        ...,
        description="Sample index within the seed.",
    )
    cif_url: Optional[str] = Field(
        default=None,
        description="URL to download the CIF structure file.",
    )
    confidences_url: Optional[str] = Field(
        default=None,
        description="URL to download the full confidences JSON.",
    )
    summary_url: Optional[str] = Field(
        default=None,
        description="URL to download the summary confidences JSON.",
    )
    ranking_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Ranking score for this prediction (0-1).",
    )
    ptm: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Predicted TM-score (pTM) for this prediction.",
    )
    iptm: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Interface predicted TM-score (ipTM) for this prediction.",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Task response schemas
# ---------------------------------------------------------------------------

class TaskResponse(BaseModel):
    """Response schema for a task in list views.

    Contains summary information suitable for the task list endpoint
    (GET /api/v1/tasks).
    """

    id: str = Field(
        ...,
        description="Task UUID.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    name: str = Field(
        ...,
        description="Task name from input JSON.",
        examples=["test_protein"],
    )
    status: str = Field(
        ...,
        description="Task status: 'completed' or 'failed'.",
        examples=["completed"],
    )
    created_at: datetime = Field(
        ...,
        description="Task creation timestamp.",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Task completion timestamp.",
    )
    best_ptm: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Best prediction pTM score.",
    )
    best_iptm: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Best prediction ipTM score.",
    )
    ranking_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Best prediction ranking score.",
    )

    model_config = {"from_attributes": True}


class TaskDetail(TaskResponse):
    """Extended task response including predictions list.

    Used for the task detail endpoint (GET /api/v1/tasks/{task_id}) and
    the predict response (POST /api/v1/predict).
    """

    error_message: Optional[str] = Field(
        default=None,
        description="Error message if the task failed.",
    )
    predictions: List[PredictionResponse] = Field(
        default_factory=list,
        description="List of all predictions for this task.",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Paginated list schema
# ---------------------------------------------------------------------------

class TaskListResponse(BaseModel):
    """Paginated task list response for GET /api/v1/tasks."""

    items: List[TaskResponse] = Field(
        ...,
        description="List of tasks on the current page.",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of tasks matching the query.",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number.",
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page.",
    )


# ---------------------------------------------------------------------------
# Error response schema
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str = Field(
        ...,
        description="Machine-readable error code.",
        examples=["INVALID_JSON"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message.",
        examples=["Input JSON format does not conform to AlphaFold 3 specification."],
    )
    details: Optional[str] = Field(
        default=None,
        description="Additional error context.",
        examples=["sequences field must not be empty"],
    )


class ErrorResponse(BaseModel):
    """Standard error response for all API endpoints."""

    error: ErrorDetail = Field(
        ...,
        description="Error information.",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats response schema
# ---------------------------------------------------------------------------

class TaskStats(BaseModel):
    """Task-related statistics."""

    total: int = Field(
        ...,
        ge=0,
        description="Total number of tasks.",
    )
    completed: int = Field(
        ...,
        ge=0,
        description="Number of completed tasks.",
    )
    failed: int = Field(
        ...,
        ge=0,
        description="Number of failed tasks.",
    )


class StatsResponse(BaseModel):
    """System statistics response for GET /api/v1/stats."""

    tasks: TaskStats = Field(
        ...,
        description="Task statistics.",
    )

    model_config = {"from_attributes": True}
