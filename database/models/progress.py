"""Per-learner progress on a single DSA problem.

A row exists only for a learner who has engaged with a problem, and it is
always scoped to one ``user_id``. There is no global progress: two learners
working the same problem keep completely independent records.
"""

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.problem import Problem
    from database.models.user import User


class ProgressStatus(str, enum.Enum):
    """The only three states a learner-facing problem status can take."""

    NOT_STARTED = "not_started"
    ATTEMPTED = "attempted"
    SOLVED = "solved"


PROGRESS_STATUS_VALUES: tuple[str, ...] = tuple(status.value for status in ProgressStatus)

# The pre-release `progress` table shipped a different vocabulary. Reading a
# legacy row must not raise or silently report a status the API cannot express.
LEGACY_STATUS_MAP: dict[str, str] = {
    "in_progress": ProgressStatus.ATTEMPTED.value,
    "started": ProgressStatus.ATTEMPTED.value,
    "completed": ProgressStatus.SOLVED.value,
    "complete": ProgressStatus.SOLVED.value,
    "not_started": ProgressStatus.NOT_STARTED.value,
    "attempted": ProgressStatus.ATTEMPTED.value,
    "solved": ProgressStatus.SOLVED.value,
}


def utc_now() -> datetime:
    """Single source of "now" so every timestamp in this module agrees."""
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Normalise a stored timestamp to an aware UTC datetime.

    SQLite drops the timezone on the way in, so a row read back is naive. Every
    comparison and subtraction in this module goes through here instead of
    assuming the database preserved the offset.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def normalize_status(value: str | None) -> str:
    """Map any known stored status onto the canonical vocabulary."""
    if not value:
        return ProgressStatus.NOT_STARTED.value
    return LEGACY_STATUS_MAP.get(value.strip().lower(), ProgressStatus.NOT_STARTED.value)


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        # One record per learner per problem. The service upserts against this,
        # so a repeated attempt updates the row instead of inserting a rival.
        UniqueConstraint("user_id", "problem_id", name="uq_progress_user_problem"),
        CheckConstraint(
            "status IN ('not_started', 'attempted', 'solved')",
            name="ck_progress_status",
        ),
        # The summary query filters a learner's rows by status; a composite
        # index keeps that from degrading into a full scan per request.
        Index("ix_progress_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=ProgressStatus.NOT_STARTED.value)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Populated once a sandboxed runner reports measurements. No execution
    # service is wired up yet, so these stay null rather than being invented.
    best_runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_memory_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="progress_entries")
    problem: Mapped["Problem"] = relationship(back_populates="progress_entries")
