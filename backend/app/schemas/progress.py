"""Request and response contracts for learner progress tracking.

Every response here is a projection. `user_id` is deliberately absent: the
learner is identified by the bearer token on the request, so no response needs
to echo whose record it is, and no client can ask for someone else's.
"""

from datetime import datetime
from typing import Literal

from database.models.progress import PROGRESS_STATUS_VALUES, ProgressStatus
from pydantic import BaseModel, ConfigDict, Field

ProgressStatusInput = Literal["not_started", "attempted", "solved"]

# Runtime and memory bounds. Nothing produces these measurements yet; they are
# guarded so a future runner can never store a nonsense or hostile value.
MAX_RUNTIME_MS = 3_600_000
MAX_MEMORY_MB = 65_536
MAX_ATTEMPTS = 1_000_000


class ProgressUpdateRequest(BaseModel):
    """Body for the progress upsert.

    `status` is optional so a caller can record a runtime measurement without
    also restating the status. Omitting it leaves the current status alone.
    """

    model_config = ConfigDict(extra="forbid")

    status: ProgressStatusInput | None = None
    best_runtime_ms: int | None = Field(default=None, ge=0, le=MAX_RUNTIME_MS)
    best_memory_mb: int | None = Field(default=None, ge=0, le=MAX_MEMORY_MB)


class ProblemProgressResponse(BaseModel):
    """One problem as the requesting learner sees it.

    A problem the learner has never touched is reported as `not_started` with
    null record timestamps: the absence of a row is a real state, not an error.
    """

    problem_id: int
    slug: str
    title: str
    difficulty: str
    topics: list[str] = Field(default_factory=list)
    status: ProgressStatus
    attempts_count: int = 0
    best_runtime_ms: int | None = None
    best_memory_mb: int | None = None
    last_attempted_at: datetime | None = None
    solved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProblemProgressListResponse(BaseModel):
    items: list[ProblemProgressResponse]
    total: int
    limit: int
    offset: int


class ProgressSummaryResponse(BaseModel):
    """Overall standing for the requesting learner across the published catalog.

    `not_started` is derived from the catalog size rather than from stored rows,
    so resetting a record cannot inflate it.
    """

    total_problems: int
    attempted: int
    solved: int
    not_started: int
    completion_percentage: float
    current_streak_days: int
    solved_by_difficulty: dict[str, int] = Field(default_factory=dict)
    total_by_difficulty: dict[str, int] = Field(default_factory=dict)
    solved_by_topic: dict[str, int] = Field(default_factory=dict)
    total_by_topic: dict[str, int] = Field(default_factory=dict)


class ProgressStatusCatalog(BaseModel):
    """The canonical vocabulary, so a client never hard-codes the strings."""

    values: list[str] = Field(default_factory=lambda: list(PROGRESS_STATUS_VALUES))
