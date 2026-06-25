"""SQLAlchemy ORM models for AlphaFold 3 inference service."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class Task(Base):
    """Represents an AlphaFold 3 prediction task.

    Maps to the 'tasks' table defined in the PRD (section 7.1).
    Stores task metadata, input data, and best prediction summary.
    """

    __tablename__ = "tasks"

    # Primary key: UUID string
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Task name from input JSON 'name' field
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Task status: 'completed' or 'failed'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Error message (populated when status == 'failed')
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Raw input JSON string
    input_data: Mapped[str] = mapped_column(Text, nullable=False)

    # Input summary as JSON string (sequences info, num_seeds, num_samples)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # modelSeeds array stored as JSON string, e.g. "[42]"
    model_seeds: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Output directory path on the filesystem
    output_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Best prediction confidence metrics
    best_seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    best_sample: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    best_ptm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_iptm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ranking_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Inference parameters
    num_seeds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_samples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship: one Task has many Predictions
    predictions: Mapped[List["Prediction"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Task(id={self.id!r}, name={self.name!r}, "
            f"status={self.status!r})>"
        )


class Prediction(Base):
    """Represents a single prediction result within a task.

    Each task may produce multiple predictions across different seeds and
    samples. This model stores per-prediction file paths and ranking score.
    """

    __tablename__ = "predictions"

    # Auto-increment primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to parent task
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )

    # Seed value for this prediction
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Sample index within the seed
    sample_idx: Mapped[int] = mapped_column(Integer, nullable=False)

    # File paths relative to the task output directory
    cif_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    confidences_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    summary_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    # Ranking score for this specific prediction
    ranking_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Additional confidence metrics (from summary_confidences.json)
    ptm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iptm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship back to parent task
    task: Mapped["Task"] = relationship(back_populates="predictions")

    __table_args__ = (
        Index("idx_predictions_task_id", "task_id"),
        Index("idx_predictions_task_sample", "task_id", "seed", "sample_idx"),
    )

    def __repr__(self) -> str:
        return (
            f"<Prediction(id={self.id}, task_id={self.task_id!r}, "
            f"seed={self.seed}, sample_idx={self.sample_idx})>"
        )
