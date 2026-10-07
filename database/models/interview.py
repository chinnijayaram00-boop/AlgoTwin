"""Mock interview sessions and their recorded question selections.

An interview is a typed, timed rehearsal built out of the *existing* problem
catalog. Nothing here defines a problem, judges code, or scores anything: the
session row bounds the run (its state, its timer, its selection) and the
question rows record *which* published problems were drawn, in what order,
and what the real judge reported for each. The design rules:

* **The selection is recorded, never lost.** ``interview_questions`` stores the
  problem id and position of every question before a session can be started, so
  an interview can never be recreated from the request that created it. A
  deterministic picker filled these rows; what it picked is durable whether or
  not the session is ever finished.
* **Only the judge produces a verdict.** A question links to the ``submissions``
  row the judge graded (``ON DELETE SET NULL``), so the question's outcome is
  read from the same store every other verdict comes from. No request can name a
  verdict; it can only submit code and receive whatever the judge returned.
* **The timer is a server-side timestamp, not a client claim.** ``started_at``
  and ``expires_at`` are written when a session starts, and every read or write
  checks wall-clock time against ``expires_at``. There is no client-supplied
  remaining time anywhere; a session that ran out of time is finalised on the
  server when it is next touched.
* **The lifecycle is closed.** A session moves ``created`` -> ``in_progress``
  -> ``completed``/``abandoned``. States are a real CHECK constraint so a direct
  SQL session cannot store a state the API cannot read back.
* **The score is deterministic.** ``score`` is 0-100, computed at completion
  from the stored question rows (accepted / total, the same division the report
  shows). It is never written by a client and never guessed by a model.

Every row is scoped to one ``user_id`` and the foreign keys cascade, so a
removed account or problem leaves nothing behind.
"""

import enum
from datetime import datetime
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
from database.models.progress import as_utc, utc_now

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.problem import Problem
    from database.models.submission import Submission
    from database.models.user import User


class InterviewStatus(str, enum.Enum):
    """The only states a mock interview session may be in.

    ``created`` is a session that has its questions recorded but no clock yet.
    ``in_progress`` is a started session whose timer is running (or has run out,
    which the next touch will finalise). ``completed`` and ``abandoned`` are the
    two terminal states; the former always carries a recorded score.
    """

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


INTERVIEW_STATUS_VALUES: tuple[str, ...] = tuple(status.value for status in InterviewStatus)

#: States in which a session is still being worked on. Used to enforce one active
#: session per learner, matching the "active session" surface the UI builds on.
ACTIVE_INTERVIEW_STATUSES: frozenset[str] = frozenset(
    {InterviewStatus.CREATED.value, InterviewStatus.IN_PROGRESS.value}
)

#: States a session reaches after the clock is set. Only these may be touched by
#: the timer, so an abandoned or completed session is never "expired" again.
TIMED_INTERVIEW_STATUSES: frozenset[str] = frozenset({InterviewStatus.IN_PROGRESS.value})


class InterviewQuestionStatus(str, enum.Enum):
    """The state of one recorded interview question.

    ``pending`` is the state at creation: the problem is recorded but nothing has
    been submitted for it. ``submitted`` means at least one submission is linked;
    whether it passed is the linked submission's verdict, never a value invented
    here.
    """

    PENDING = "pending"
    SUBMITTED = "submitted"


INTERVIEW_QUESTION_STATUS_VALUES: tuple[str, ...] = tuple(
    status.value for status in InterviewQuestionStatus
)

#: How many questions an interview may hold, and the platform defaults.
MIN_QUESTION_COUNT: int = 1
MAX_QUESTION_COUNT: int = 10
DEFAULT_QUESTION_COUNT: int = 3

#: The session timer bounds, in whole seconds. ``duration_seconds`` is stored and
#: the API accepts minutes; the conversion happens once, at creation.
MIN_DURATION_SECONDS: int = 300  # 5 minutes
MAX_DURATION_SECONDS: int = 7_200  # 2 hours
DEFAULT_DURATION_SECONDS: int = 1_800  # 30 minutes

#: Free-form calibration fields. Sizes are generous but bounded: a role or topic
#: is a short label, and an unbounded string is an unbounded payload.
MAX_ROLE_LENGTH: int = 80
MAX_LEVEL_LENGTH: int = 30
MAX_TOPIC_LENGTH: int = 80
MAX_DIFFICULTY_LENGTH: int = 20

#: A completed score is a percentage and nothing else.
MIN_SCORE: int = 0
MAX_SCORE: int = 100


class InterviewSession(Base):
    """One timed mock interview owned by one learner."""

    __tablename__ = "interview_sessions"
    __table_args__ = (
        # The lifecycle as a real constraint, not only an application rule.
        CheckConstraint(
            "status IN ('created', 'in_progress', 'completed', 'abandoned')",
            name="ck_interview_sessions_status",
        ),
        # A score is a percentage written once at completion.
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_interview_sessions_score",
        ),
        CheckConstraint(
            f"question_count >= {MIN_QUESTION_COUNT} AND question_count <= {MAX_QUESTION_COUNT}",
            name="ck_interview_sessions_question_count",
        ),
        CheckConstraint(
            f"duration_seconds >= {MIN_DURATION_SECONDS} AND duration_seconds <= {MAX_DURATION_SECONDS}",
            name="ck_interview_sessions_duration_seconds",
        ),
        # The position the UI should present next. Never negative, and always in
        # range for the session's question count by construction (the service
        # clamps it on every write).
        CheckConstraint("current_index >= 0", name="ck_interview_sessions_current_index"),
        Index("ix_interview_sessions_user_status", "user_id", "status"),
        Index("ix_interview_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(
        String(30), default=InterviewStatus.CREATED.value, nullable=False, index=True
    )

    # Calibration. `difficulty`/`topic` record which filters produced the
    # selection; `role`/`level` are the learner's own framing and do not change
    # what was selected.
    role: Mapped[str] = mapped_column(String(MAX_ROLE_LENGTH), nullable=False)
    level: Mapped[str | None] = mapped_column(String(MAX_LEVEL_LENGTH), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(MAX_DIFFICULTY_LENGTH), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(MAX_TOPIC_LENGTH), nullable=True)

    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_QUESTION_COUNT)
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DURATION_SECONDS
    )
    #: The first unanswered question's position, maintained by the service.
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: 0-100, written only when the session completes. Null while the session is
    #: unfinished, which is the honest "no result yet" rather than a zero.
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    #: Filled by ``start``. ``expires_at`` is the single source of truth for the
    #: remaining time; the API never accepts a client-computed remaining time.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: When the session reached a terminal state: the learner finished, the timer
    #: ran out (in which case this equals ``expires_at``), or the learner
    #: abandoned it.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="interview_sessions")
    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InterviewQuestion.position",
    )

    # ------------------------------------------------------------------ readers

    @property
    def created_at_utc(self) -> datetime:
        return as_utc(self.created_at)

    @property
    def started_at_utc(self) -> datetime | None:
        return as_utc(self.started_at)

    @property
    def expires_at_utc(self) -> datetime | None:
        return as_utc(self.expires_at)

    @property
    def completed_at_utc(self) -> datetime | None:
        return as_utc(self.completed_at)

    @property
    def was_timed_out(self) -> bool:
        """Whether a completed session ended because the timer ran out.

        A session that was finished or abandoned is ``False``; only a completion
        whose timestamp is at or beyond ``expires_at`` counts as timed out. This
        is derived from two stored timestamps, so it cannot disagree with the
        timer that governed the session.
        """
        if not self.is_completed:
            return False
        completed = self.completed_at_utc
        expires = self.expires_at_utc
        return completed is not None and expires is not None and completed >= expires

    @property
    def is_created(self) -> bool:
        return self.status == InterviewStatus.CREATED.value

    @property
    def is_in_progress(self) -> bool:
        return self.status == InterviewStatus.IN_PROGRESS.value

    @property
    def is_completed(self) -> bool:
        return self.status == InterviewStatus.COMPLETED.value

    @property
    def is_abandoned(self) -> bool:
        return self.status == InterviewStatus.ABANDONED.value

    @property
    def is_active(self) -> bool:
        """True while the session is still being worked on before its timer runs."""
        return self.status in ACTIVE_INTERVIEW_STATUSES


class InterviewQuestion(Base):
    """One recorded problem in one interview, with its judged outcome.

    ``position`` is the order the learner is shown, starting at zero. The two
    unique constraints are both deliberate: a position is only ever assigned to
    one question in a session, and a problem can only be drawn once per session,
    so a corrupted selection cannot silently duplicate either.
    """

    __tablename__ = "interview_questions"
    __table_args__ = (
        # One question per position, one problem per session.
        UniqueConstraint("session_id", "position", name="uq_interview_questions_session_position"),
        UniqueConstraint("session_id", "problem_id", name="uq_interview_questions_session_problem"),
        CheckConstraint(
            "position >= 0",
            name="ck_interview_questions_position",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_interview_questions_attempts",
        ),
        CheckConstraint(
            "status IN ('pending', 'submitted')",
            name="ck_interview_questions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=InterviewQuestionStatus.PENDING.value, nullable=False
    )
    #: The judge's row for the latest submission to this question, or ``None``
    #: while the question is still pending or if the submission no longer exists.
    #: ``SET NULL`` keeps the question meaningful when the submission record it
    #: pointed at is gone. A question's verdict always comes from here.
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    #: Submissions made to this question. Counts every attempt, accepted or not.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["InterviewSession"] = relationship(back_populates="questions")
    problem: Mapped["Problem"] = relationship()
    submission: Mapped["Submission | None"] = relationship()

    @property
    def is_submitted(self) -> bool:
        return self.status == InterviewQuestionStatus.SUBMITTED.value

    @property
    def answered_at_utc(self) -> datetime | None:
        return as_utc(self.answered_at)


__all__ = [
    "ACTIVE_INTERVIEW_STATUSES",
    "DEFAULT_DURATION_SECONDS",
    "DEFAULT_QUESTION_COUNT",
    "INTERVIEW_QUESTION_STATUS_VALUES",
    "INTERVIEW_STATUS_VALUES",
    "MAX_DIFFICULTY_LENGTH",
    "MAX_DURATION_SECONDS",
    "MAX_LEVEL_LENGTH",
    "MAX_QUESTION_COUNT",
    "MAX_ROLE_LENGTH",
    "MAX_SCORE",
    "MAX_TOPIC_LENGTH",
    "MIN_DURATION_SECONDS",
    "MIN_QUESTION_COUNT",
    "MIN_SCORE",
    "TIMED_INTERVIEW_STATUSES",
    "InterviewQuestion",
    "InterviewQuestionStatus",
    "InterviewSession",
    "InterviewStatus",
]