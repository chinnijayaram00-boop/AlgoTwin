"""Request and response contracts for the learner's learning path.

The learning path is a projection of three real things: the published catalog,
the caller's stored progress rows, and a fixed curriculum order over primary
topics. Nothing here is generated, sampled, or model-authored, so the same
catalog plus the same progress always produces the same path.

Like the progress contracts, `user_id` is deliberately absent: the learner is
identified by the bearer token on the request, so no response needs to say
whose path it is and no client can ask for someone else's. Test cases, reference
solutions, and starter code are absent for the same reason they are absent from
every other learner-facing contract -- this response never carries them.
"""

from typing import Literal

from database.models.progress import ProgressStatus
from pydantic import BaseModel, Field

#: Where a stage sits relative to the learner right now. ``current`` is the
#: first stage the learner still owes work on; a stage is never reported as
#: locked, because the path advises rather than gates -- every problem stays
#: reachable from the catalog.
LearningPathStageState = Literal["complete", "current", "upcoming"]

#: Machine-readable explanations for the recommended next problem. A client
#: switches on these instead of parsing prose, and the prose is derived from
#: them so the two can never drift apart.
REASON_FIRST_STEP = "first_step"
REASON_ATTEMPTED_PENDING = "attempted_pending"
REASON_NEXT_DIFFICULTY = "next_difficulty"
REASON_CONTINUE_STAGE = "continue_stage"
REASON_PREREQUISITE_MET = "prerequisite_met"
REASON_NEXT_STAGE = "next_stage"

REASON_CODES: tuple[str, ...] = (
    REASON_ATTEMPTED_PENDING,
    REASON_FIRST_STEP,
    REASON_NEXT_DIFFICULTY,
    REASON_CONTINUE_STAGE,
    REASON_PREREQUISITE_MET,
    REASON_NEXT_STAGE,
)

#: How many under-done topics the response names. Ordered by how much is left
#: to do, then alphabetically, so a client can show a short "topics to shore up"
#: list without re-deriving or re-sorting it.
MAX_WEAK_TOPICS = 6


class LearningPathProblem(BaseModel):
    """One problem as it appears in the path.

    A projection, not a problem detail: enough for a card (what it is called,
    how hard it is, which topics it exercises, whether this learner has done
    it) and nothing that would let a client reconstruct a test case.
    """

    problem_id: int
    slug: str
    title: str
    summary: str
    difficulty: str
    topics: list[str] = Field(default_factory=list)
    primary_topic: str
    status: ProgressStatus
    attempts_count: int = 0
    #: Zero-based position within its stage, already in Easy-to-Hard order.
    position: int = 0


class LearningPathStage(BaseModel):
    """One curriculum stage: every published problem whose primary topic matches."""

    index: int
    #: URL-safe form of ``title``, so a client can anchor without re-deriving it.
    key: str
    title: str
    state: LearningPathStageState
    #: Title of the stage immediately before this one in the curriculum.
    prerequisite_title: str | None = None
    #: Whether the learner has done work in an earlier stage. Advisory only:
    #: an unready stage is discouraged, never hidden or blocked.
    prerequisite_ready: bool
    problem_count: int
    solved_count: int
    attempted_count: int
    completion_percentage: float
    problems: list[LearningPathProblem] = Field(default_factory=list)


class LearningPathRecommendation(BaseModel):
    """The single next problem the path advises, and why."""

    reason_code: str
    reason: str
    #: The computed priority. Exposed so a test and a reviewer can see the
    #: ordering was produced by the documented formula rather than asserted.
    score: int
    stage_index: int
    stage_title: str
    problem: LearningPathProblem


class LearningPathResponse(BaseModel):
    """The whole path for the requesting learner."""

    total_problems: int
    solved_problems: int
    attempted_problems: int
    completion_percentage: float
    stages_total: int
    stages_complete: int
    #: ``None`` only when every published problem is solved.
    current_stage_index: int | None = None
    current_stage_title: str | None = None
    #: Topics the learner has started but not finished, most outstanding work
    #: first. Empty for a learner who has not begun, and for one who has
    #: finished everything.
    weak_topics: list[str] = Field(default_factory=list)
    #: ``None`` when there is nothing left to recommend.
    recommendation: LearningPathRecommendation | None = None
    stages: list[LearningPathStage] = Field(default_factory=list)
