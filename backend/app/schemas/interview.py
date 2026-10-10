"""Request and response contracts for mock interviews.

Like the progress and submission contracts, `user_id` is deliberately absent from
every shape here: the learner is identified by the bearer token on the request,
so no payload or response needs to name whose session it is, and no client can
address another learner's interview by sending an id. `extra="forbid"` on the
request models makes that impossible even by accident.

Nothing here describes a judge. A request carries only calibration fields and,
for an answer, code in a language; the verdict, the pass counts, the runtime,
and ``submission_id`` are written by the judge and reported read-only in the
response. A client can never name a verdict, a score, or a submission.

Test cases, reference solutions, and starter code are absent for the same reason
they are absent from every other learner-facing contract: interview questions
are submitted through the same judge the rest of the platform uses, and the
proposition that the hidden suite stays hidden is a platform property, not an
interview property.
"""

from datetime import datetime
from typing import Literal

from database.models.interview import (
    DEFAULT_DURATION_SECONDS,
    DEFAULT_QUESTION_COUNT,
    INTERVIEW_QUESTION_STATUS_VALUES,
    INTERVIEW_STATUS_VALUES,
    MAX_DURATION_SECONDS,
    MAX_LEVEL_LENGTH,
    MAX_QUESTION_COUNT,
    MAX_ROLE_LENGTH,
    MAX_SCORE,
    MAX_TOPIC_LENGTH,
    MIN_DURATION_SECONDS,
    MIN_QUESTION_COUNT,
)
from database.models.submission import (
    MAX_SOURCE_CODE_LENGTH,
    SUPPORTED_LANGUAGES,
    SubmissionStatus,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Difficulty filter values the catalog recognises. The catalog spells its
#: difficulties with a capital letter (``Easy``/``Medium``/``Hard``), and the
#: selection matches exactly, so the published contract uses the same spelling.
InterviewDifficultyInput = Literal["Easy", "Medium", "Hard"]

#: Languages the judge can run, mirrored from the submission vocabulary so the
#: interview answer contract cannot offer a language the judge will refuse.
SupportedLanguage = Literal[*SUPPORTED_LANGUAGES]

#: Status values a history listing may be filtered by, from the session model's
#: vocabulary so the route and the storage cannot disagree.
InterviewStatusInput = Literal["created", "in_progress", "completed", "abandoned"]


class InterviewCreateRequest(BaseModel):
    """Body for creating a mock interview session.

    Everything is optional except the empty body itself, so a learner can start
    a default interview with `{}`; the values that are present only narrow the
    deterministic selection. ``question_count`` and ``duration_minutes`` are
    bounded by the same limits the model enforces. ``extra="forbid"`` is the
    security-relevant part: a payload carrying ``user_id``, ``problem_ids``, or
    any scoring field is rejected with 422 rather than silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    role: str = Field(
        default="Software Engineer",
        min_length=1,
        max_length=MAX_ROLE_LENGTH,
        description="What role the learner is rehearsing for.",
    )
    level: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_LEVEL_LENGTH,
        description="Optional self-described seniority, e.g. `mid` or `senior`.",
    )
    difficulty: InterviewDifficultyInput | None = Field(
        default=None, description="Restrict the selection to one difficulty tier."
    )
    topic: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_TOPIC_LENGTH,
        description="Restrict the selection to problems carrying this topic.",
    )
    question_count: int = Field(
        default=DEFAULT_QUESTION_COUNT,
        ge=MIN_QUESTION_COUNT,
        le=MAX_QUESTION_COUNT,
        description=f"Problems to draw, between {MIN_QUESTION_COUNT} and {MAX_QUESTION_COUNT}.",
    )
    duration_minutes: int = Field(
        default=DEFAULT_DURATION_SECONDS // 60,
        ge=MIN_DURATION_SECONDS // 60,
        le=MAX_DURATION_SECONDS // 60,
        description="How long the learner has, in whole minutes.",
    )

    @field_validator("role", "level", "topic")
    @classmethod
    def reject_blank(cls, value: str | None) -> str | None:
        """Reject whitespace-only calibration fields.

        A role or topic of spaces would otherwise pass ``min_length`` while
        carrying no meaning at all, and a filter of spaces would match nothing.
        """
        if value is not None and not value.strip():
            raise ValueError("must contain text.")
        return value


class InterviewAnswerRequest(BaseModel):
    """Body for submitting code for one question.

    Only ``language`` and ``source_code`` are accepted. The problem is the one
    already recorded for that question's position, so the client sends no id and
    cannot ask for a problem that was never drawn. ``extra="forbid"`` rejects any
    attempt to name a verdict, a status, or a score.
    """

    model_config = ConfigDict(extra="forbid")

    language: SupportedLanguage = Field(description="Language the source is written in.")
    source_code: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_CODE_LENGTH,
        description="The learner's source. Stored as sent; run only by the judge.",
    )

    @field_validator("source_code")
    @classmethod
    def reject_blank_source(cls, value: str) -> str:
        """Reject whitespace-only source, matching the submission contract."""
        if not value.strip():
            raise ValueError("source_code must contain the learner's code.")
        return value


class InterviewQuestionResponse(BaseModel):
    """One recorded question as the session exposes it.

    A projection of the drawn problem plus the judge's linked outcome. The
    statement fields a learner needs to answer (``description``, examples, …) are
    served by the existing published problem endpoints; this contract identifies
    the problem and reports the outcome and never carries test material.
    """

    position: int
    problem_id: int
    slug: str
    title: str
    summary: str
    difficulty: str
    topics: list[str] = Field(default_factory=list)
    primary_topic: str
    status: Literal["pending", "submitted"]
    #: The judge's verdict for the latest submission, or ``None`` while pending.
    verdict: SubmissionStatus | None = None
    submission_id: int | None = None
    accepted: bool = False
    attempts: int = 0
    runtime_ms: int | None = None
    answered_at: datetime | None = None
    #: The language the latest submission was written in, from the judged
    #: submission row. ``None`` while the question is still pending.
    language: str | None = None


class InterviewSessionResponse(BaseModel):
    """A session and its recorded questions, as the routes return it.

    ``remaining_seconds`` is computed server-side from the stored ``expires_at``
    against the server clock -- never taken from the client -- and is ``None``
    once the session is not actively running. ``timed_out`` is derived from the
    stored timestamps, so a completion at or after ``expires_at`` is reported
    honestly as the clock having run out.
    """

    id: int
    status: str
    role: str
    level: str | None = None
    difficulty: str | None = None
    topic: str | None = None
    question_count: int
    duration_seconds: int
    current_index: int
    score: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    remaining_seconds: int | None = None
    timed_out: bool = False
    questions: list[InterviewQuestionResponse] = Field(default_factory=list)


class InterviewSummaryResponse(BaseModel):
    """One session as it appears in a history list.

    Enough for a row -- when it was run, its calibration, its outcome -- without
    the per-question breakdown, which belongs to the report.
    """

    id: int
    status: str
    role: str
    level: str | None = None
    difficulty: str | None = None
    question_count: int
    #: How long the session was calibrated for, in seconds -- the same unit the
    #: session body uses. Present so a history row can state the session's
    #: duration, not just its question count.
    duration_seconds: int
    score: int | None = None
    timed_out: bool = False
    created_at: datetime
    completed_at: datetime | None = None


class InterviewListResponse(BaseModel):
    """A page of one learner's interview history."""

    items: list[InterviewSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class InterviewReportQuestion(InterviewQuestionResponse):
    """One question inside an interview report, with its judge measurements."""

    test_cases_passed: int | None = None
    test_cases_total: int | None = None
    memory_mb: int | None = None
    #: Whole seconds from the session start to the question's first answer,
    #: derived from the stored timestamps. ``None`` while the question is
    #: unanswered, which is the honest "not answered" rather than a zero.
    answered_seconds_into_session: int | None = None


class InterviewReportResponse(BaseModel):
    """The post-session report for a completed interview.

    Score and every headline number are computed from the stored question rows,
    so the report is a deterministic reading of what actually happened and never
    a guess.
    """

    id: int
    role: str
    level: str | None = None
    difficulty: str | None = None
    topic: str | None = None
    status: Literal["completed"]
    question_count: int
    duration_seconds: int
    score: int = Field(ge=0, le=MAX_SCORE)
    timed_out: bool = False
    started_at: datetime
    completed_at: datetime
    duration_used_seconds: int = 0
    questions_answered: int = 0
    questions_accepted: int = 0
    questions: list[InterviewReportQuestion] = Field(default_factory=list)


__all__ = [
    "INTERVIEW_QUESTION_STATUS_VALUES",
    "INTERVIEW_STATUS_VALUES",
    "InterviewAnswerRequest",
    "InterviewCreateRequest",
    "InterviewDifficultyInput",
    "InterviewListResponse",
    "InterviewQuestionResponse",
    "InterviewReportQuestion",
    "InterviewReportResponse",
    "InterviewSessionResponse",
    "InterviewStatusInput",
    "InterviewSummaryResponse",
    "SupportedLanguage",
]