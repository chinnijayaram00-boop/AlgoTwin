"""One learner's record of code they submitted for a problem.

A submission is created the moment a learner sends code, and it is created
*unjudged*: the row exists so the attempt, the language, and the source are
durable before anything runs. Nothing in this module executes code, and no
field here is invented to look like a verdict.

Two column groups, and the distinction matters:

* ``language`` and ``source_code`` are what the learner sent. They are known at
  creation time and are never written by anything else.
* ``status`` plus the measurement columns describe a *judged* run. Every
  submission created through the API starts at :data:`INITIAL_SUBMISSION_STATUS`
  and the judge is the only thing that may move a row out of that state. A row
  that reaches only the first write stays ``queued`` forever, which is honest --
  it really was stored and never judged -- and only a real ``accepted`` result
  may mark a problem solved.

A row is always scoped to exactly one ``user_id`` and one ``problem_id``. There
is no shared or global submission, and both foreign keys cascade so a removed
account or problem leaves nothing behind.
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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.progress import as_utc, utc_now

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.problem import Problem
    from database.models.user import User


class SubmissionStatus(str, enum.Enum):
    """The only states a submission may be in.

    ``QUEUED`` and ``RUNNING`` are pre-verdict states: the code has been accepted
    for processing but nothing has decided its fate yet. Every other member is a
    verdict and can only be written by an execution service, never by the
    request that created the submission.
    """

    QUEUED = "queued"
    RUNNING = "running"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    FAILED = "failed"


SUBMISSION_STATUS_VALUES: tuple[str, ...] = tuple(status.value for status in SubmissionStatus)

#: Statuses that mean "stored, but not judged yet". A submission created through
#: the API is in one of these and stays there until a runner reports a verdict.
PENDING_SUBMISSION_STATUSES: frozenset[str] = frozenset(
    {SubmissionStatus.QUEUED.value, SubmissionStatus.RUNNING.value}
)

#: The status a newly created submission is given. Deliberately not ``accepted``:
#: AlgoTwin does not execute code, so it cannot know whether the code is correct.
INITIAL_SUBMISSION_STATUS: str = SubmissionStatus.QUEUED.value

#: Languages the workspace offers and the seeded problems ship starter code for.
#: A submission in any other language could not be run by a future runner either,
#: so the API refuses it rather than storing something unusable.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("javascript", "python")

# Payload guards. A submission is the largest thing a learner can send, so the
# ceiling is explicit: an editor buffer is a few kilobytes, and 64 KB leaves room
# for a long solution without letting one request carry a payload fit for abuse.
MAX_SOURCE_CODE_LENGTH: int = 65_536
MAX_ERROR_MESSAGE_LENGTH: int = 2_000
MAX_RUNTIME_MS: int = 3_600_000
MAX_MEMORY_MB: int = 65_536
MAX_TEST_CASES: int = 10_000


def normalize_submission_status(value: str | None) -> str:
    """Map any stored status onto the canonical vocabulary.

    The pre-release table shipped without a status constraint, so a row written
    before this release may hold a label the API cannot express. An unreadable
    value is reported as ``failed`` rather than as ``queued``: claiming the code
    is awaiting a run would be an assertion AlgoTwin cannot back up, while
    reporting a broken or unknown record as unusable is the safe reading. A
    verdict is never invented, and ``accepted`` is never the fallback.
    """
    if not value:
        return SubmissionStatus.FAILED.value
    candidate = value.strip().lower()
    if candidate in SUBMISSION_STATUS_VALUES:
        return candidate
    return SubmissionStatus.FAILED.value


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        # The vocabulary is a real constraint, not only an application rule, so a
        # direct SQL session or a future import cannot store a status the API
        # cannot read back.
        CheckConstraint(
            "status IN ('queued', 'running', 'accepted', 'wrong_answer', 'runtime_error',"
            " 'compilation_error', 'time_limit_exceeded', 'memory_limit_exceeded', 'failed')",
            name="ck_submissions_status",
        ),
        # A run cannot have passed more cases than it ran. The two may both be
        # null while a submission is still queued, so the rule is written to
        # permit that rather than to force a measurement that does not exist.
        CheckConstraint(
            "(test_cases_passed IS NULL OR test_cases_passed >= 0)"
            " AND (test_cases_total IS NULL OR test_cases_total >= 0)"
            " AND (test_cases_passed IS NULL OR test_cases_total IS NULL"
            " OR test_cases_passed <= test_cases_total)",
            name="ck_submissions_test_case_counts",
        ),
        CheckConstraint(
            "runtime_ms IS NULL OR runtime_ms >= 0", name="ck_submissions_runtime_ms"
        ),
        CheckConstraint(
            "memory_mb IS NULL OR memory_mb >= 0", name="ck_submissions_memory_mb"
        ),
        # The history list is always "this learner, newest first", so the
        # composite index matches the query exactly instead of letting the engine
        # filter on user_id after scanning every learner's submissions.
        Index("ix_submissions_user_submitted_at", "user_id", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(40), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=INITIAL_SUBMISSION_STATUS, index=True
    )

    # Everything below is filled in only by a future execution service. It stays
    # null on a submission created through the API, and nothing here is derived
    # from reading the source code.
    test_cases_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    test_cases_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # `submitted_at` is when the learner sent the code. `judged_at` is when the
    # judge answered for it, which is a different instant and can be a different
    # amount of time later: a run that spent most of a second in a worker should
    # not look instantaneous on the record. Null on a submission that was stored
    # but never judged -- a legacy row, or a run the platform could not complete.
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")

    @property
    def is_pending(self) -> bool:
        """True while the submission has not been judged."""
        return normalize_submission_status(self.status) in PENDING_SUBMISSION_STATUSES

    @property
    def submitted_at_utc(self) -> datetime:
        """The submission time as an aware UTC datetime.

        SQLite drops the offset on the way in, so this normalises the value the
        same way the progress module does rather than assuming it survived.
        """
        return as_utc(self.submitted_at)

    @property
    def judged_at_utc(self) -> datetime | None:
        """The judging time as an aware UTC datetime, or ``None`` if never judged."""
        if self.judged_at is None:
            return None
        return as_utc(self.judged_at)


__all__ = [
    "INITIAL_SUBMISSION_STATUS",
    "MAX_ERROR_MESSAGE_LENGTH",
    "MAX_MEMORY_MB",
    "MAX_RUNTIME_MS",
    "MAX_SOURCE_CODE_LENGTH",
    "MAX_TEST_CASES",
    "PENDING_SUBMISSION_STATUSES",
    "SUBMISSION_STATUS_VALUES",
    "SUPPORTED_LANGUAGES",
    "Submission",
    "SubmissionStatus",
    "normalize_submission_status",
]
