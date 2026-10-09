"""Request and response contracts for the personalized coach.

Every shape here is a projection of one learner's own persisted rows: the
published catalog, that learner's progress records, that learner's submissions,
and that learner's mock interviews. The profile reuses the same deterministic
computations the analytics and learning-path endpoints already run, so the coach
cannot disagree with those pages about how many problems a learner has solved or
which problem comes next.

Like every other learner-scoped contract, ``user_id`` is deliberately absent.
The learner is identified by the bearer token on the request, so no response has
to echo whose profile it is and no client can ask for somebody else's.

The mentor guidance is *not* a stored insight. It is derived fresh from the
profile on every request, which is why the request schema is tiny and the
response carries the grounding inline: a mentor's advice should reflect the
learner's state now, not a cached reading of it from some earlier moment.
"""

from datetime import date, datetime
from typing import Any, Literal

from database.models.progress import ProgressStatus
from pydantic import BaseModel, ConfigDict, Field

#: How many signals (strengths or weaknesses) the profile names. A short,
#: ranked list is more useful than an exhaustive one, and the ranking is
#: deterministic so two reads of the same state agree.
MAX_SIGNALS = 6

#: How many next-step recommendations the profile offers, starting with the
#: learning path's own single recommendation and following it with the other
#: unsolved problems in the same stage.
MAX_RECOMMENDATIONS = 5

#: How many focus areas the profile names, ordered weakest-first so the list
#: reads as "what to work on" rather than "what exists".
MAX_FOCUS_AREAS = 6

#: What a mentor request may ask the coach to centre on. A closed vocabulary so
#: the emphasis is selected, never free text a caller could smuggle content
#: through -- matching the ``focus`` parameter on the problem-explanation route.
MentorFocus = Literal["overview", "strengths", "weaknesses", "next_steps"]

#: The default focus when a caller asks for guidance without naming one.
DEFAULT_MENTOR_FOCUS = "overview"

# --- strength codes. Machine-readable so a client switches on them instead of
# --- parsing prose, and asserted by the tests so the vocabulary cannot drift.
STRENGTH_SOLVED_VOLUME = "solved_volume"
STRENGTH_HIGH_ACCEPTANCE = "high_acceptance"
STRENGTH_PRACTICE_STREAK = "practice_streak"
STRENGTH_DIFFICULTY_MASTERY = "difficulty_mastery"
STRENGTH_TOPIC_MASTERY = "topic_mastery"
STRENGTH_INTERVIEW_PERFORMANCE = "interview_performance"

# --- weakness codes.
WEAKNESS_NOT_STARTED = "not_started"
WEAKNESS_NO_SUBMISSIONS = "no_submissions"
WEAKNESS_UNFINISHED_ATTEMPTS = "unfinished_attempts"
WEAKNESS_LOW_ACCEPTANCE = "low_acceptance"
WEAKNESS_WEAK_TOPICS = "weak_topics"
WEAKNESS_INTERVIEW_QUESTIONS = "interview_questions"

# --- degraded reasons the mentor response reports when it could not reach a
# --- provider. Kept as a closed vocabulary for the same reason as the focus.
DEGRADED_PROVIDER_NOT_CONFIGURED = "provider_not_configured"
DEGRADED_PROVIDER_TIMEOUT = "provider_timeout"
DEGRADED_PROVIDER_ERROR = "provider_error"
DEGRADED_RATE_LIMITED = "rate_limited"


class ProfileOverview(BaseModel):
    """The headline numbers behind every signal the profile reports.

    Two evidence groups, exactly as the analytics overview splits them: the
    catalog plus progress rows answer the first half, the learner's submissions
    and interview sessions answer the second. Nothing is estimated -- a rate is
    a division of two counts both reported beside it, and a value with no
    evidence is ``0`` or ``None`` rather than a plausible default.
    """

    total_problems: int
    solved: int
    attempted: int
    not_started: int
    completion_percentage: float
    current_streak_days: int

    total_submissions: int
    judged_submissions: int
    accepted_submissions: int
    acceptance_rate: float
    problems_submitted: int

    interviews_completed: int = 0
    questions_answered: int = 0
    questions_accepted: int = 0
    average_interview_score: float | None = None


class ProfileSignal(BaseModel):
    """One explainable strength or weakness.

    The ``evidence`` string is the fact that produced the signal, so the claim
    is checkable rather than asserted: a client can render the title, and a
    reviewer can see the measurement it came from.
    """

    code: str
    title: str
    detail: str
    evidence: str


class PersonalizationRecommendation(BaseModel):
    """One problem the coach suggests next, and why.

    The first recommendation is the learning path's own choice, carrying its
    ``reason_code`` and ``reason`` verbatim. The rest are the other unsolved
    problems in the same stage, so the list never leaves the stage the learner
    is standing in.
    """

    problem_id: int
    slug: str
    title: str
    difficulty: str
    topics: list[str] = Field(default_factory=list)
    primary_topic: str
    status: ProgressStatus
    reason_code: str
    reason: str
    #: The learning-path priority for the primary recommendation; zero for the
    #: follow-on suggestions, which are ordered by their position in the stage.
    priority: int = 0


class FocusArea(BaseModel):
    """One topic and how much of it the learner has finished.

    Ordered weakest-first, so the first row is the most productive place to
    spend the next session.
    """

    topic: str
    solved: int
    attempted: int
    total: int
    completion_percentage: float


class PersonalizationProfileResponse(BaseModel):
    """The whole personalized profile in one read."""

    overview: ProfileOverview
    strengths: list[ProfileSignal] = Field(default_factory=list)
    weaknesses: list[ProfileSignal] = Field(default_factory=list)
    recommendations: list[PersonalizationRecommendation] = Field(default_factory=list)
    focus_areas: list[FocusArea] = Field(default_factory=list)
    #: The day the profile was computed for, so a client can say "as of" and a
    #: test can pin it.
    as_of: date


class MentorGuidanceRequest(BaseModel):
    """What a mentor request may select. Nothing else is accepted.

    ``extra="forbid"`` matters here as much as on every other request schema: a
    caller cannot smuggle a statement, a verdict, or any other context into the
    prompt, because there is no field to put it in.
    """

    model_config = ConfigDict(extra="forbid")

    focus: MentorFocus = DEFAULT_MENTOR_FOCUS


class MentorGuidanceResponse(BaseModel):
    """Grounded coaching, with the deterministic fallback made explicit.

    ``fallback`` is ``True`` when no model answered and the text was derived
    from the profile by :mod:`backend.app.services.personalization_service`.
    ``degraded_reason`` names why the provider was not used, so a client can
    explain the difference rather than presenting rules-based text as a model's.
    """

    focus: str
    content: str
    provider: str
    model: str
    grounding: dict[str, Any] = Field(default_factory=dict)
    fallback: bool = False
    degraded_reason: str | None = None
    is_demo_output: bool = False
    generated_at: datetime


__all__ = [
    "DEFAULT_MENTOR_FOCUS",
    "DEGRADED_PROVIDER_ERROR",
    "DEGRADED_PROVIDER_NOT_CONFIGURED",
    "DEGRADED_PROVIDER_TIMEOUT",
    "DEGRADED_RATE_LIMITED",
    "MAX_FOCUS_AREAS",
    "MAX_RECOMMENDATIONS",
    "MAX_SIGNALS",
    "STRENGTH_DIFFICULTY_MASTERY",
    "STRENGTH_HIGH_ACCEPTANCE",
    "STRENGTH_INTERVIEW_PERFORMANCE",
    "STRENGTH_PRACTICE_STREAK",
    "STRENGTH_SOLVED_VOLUME",
    "STRENGTH_TOPIC_MASTERY",
    "WEAKNESS_INTERVIEW_QUESTIONS",
    "WEAKNESS_LOW_ACCEPTANCE",
    "WEAKNESS_NOT_STARTED",
    "WEAKNESS_NO_SUBMISSIONS",
    "WEAKNESS_UNFINISHED_ATTEMPTS",
    "WEAKNESS_WEAK_TOPICS",
    "FocusArea",
    "MentorFocus",
    "MentorGuidanceRequest",
    "MentorGuidanceResponse",
    "PersonalizationProfileResponse",
    "PersonalizationRecommendation",
    "ProfileOverview",
    "ProfileSignal",
]
