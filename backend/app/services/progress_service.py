"""Learner progress use cases.

Two rules hold everywhere in this module:

* the caller supplies ``user_id``, and it is the id resolved from the bearer
  token by ``get_current_user`` -- never a value from the request body, query
  string, or path, so no request can address another learner's progress;
* every read and write is filtered by that ``user_id``, so two learners working
  the same problem keep entirely separate records.

This module tracks what a learner reports doing. It is deliberately not a
submission pipeline: there is no execution, no test run, and no verdict
inferred from source code. Attempt and solve states are self-reported until a
sandboxed runner can confirm them.
"""

from datetime import date, timedelta

from database.models import Problem, Progress
from database.models.progress import ProgressStatus, as_utc, normalize_status, utc_now
from sqlalchemy import Text, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.schemas.progress import (
    ProblemProgressListResponse,
    ProblemProgressResponse,
    ProgressSummaryResponse,
)


class DuplicateProgressError(RuntimeError):
    """Raised when a concurrent writer wins the unique (user_id, problem_id) race."""


# --------------------------------------------------------------------- lookups


def get_progress_row(session: Session, user_id: int, problem_id: int) -> Progress | None:
    return session.scalar(
        select(Progress).where(Progress.user_id == user_id, Progress.problem_id == problem_id)
    )


def get_user_progress(session: Session, user_id: int) -> list[Progress]:
    """Every stored record for one learner, most recently touched first."""
    return list(
        session.scalars(
            select(Progress)
            .where(Progress.user_id == user_id)
            .order_by(Progress.updated_at.desc(), Progress.id.desc())
        )
    )


# ------------------------------------------------------------------ projections


def _topics_of(problem: Problem) -> list[str]:
    topics = problem.topics
    if not isinstance(topics, list):
        return []
    return [str(topic) for topic in topics if isinstance(topic, (str, int, float))]


def to_response(problem: Problem, progress: Progress | None) -> ProblemProgressResponse:
    """Project a problem plus the caller's record into the public shape.

    A missing record is reported as ``not_started`` with null record timestamps.
    That keeps "never opened" a first-class answer instead of a 404, and avoids
    minting a row for a learner who has done nothing yet.
    """
    if progress is None:
        return ProblemProgressResponse(
            problem_id=problem.id,
            slug=problem.slug,
            title=problem.title,
            difficulty=problem.difficulty,
            topics=_topics_of(problem),
            status=ProgressStatus.NOT_STARTED,
            attempts_count=0,
        )

    status = normalize_status(progress.status)
    return ProblemProgressResponse(
        problem_id=problem.id,
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        topics=_topics_of(problem),
        status=status,
        attempts_count=max(int(progress.attempts_count or 0), 0),
        best_runtime_ms=progress.best_runtime_ms,
        best_memory_mb=progress.best_memory_mb,
        last_attempted_at=as_utc(progress.last_attempted_at),
        solved_at=as_utc(progress.solved_at),
        created_at=as_utc(progress.created_at),
        updated_at=as_utc(progress.updated_at),
    )


def list_progress(
    session: Session,
    user_id: int,
    status: str | None = None,
    difficulty: str | None = None,
    topic: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ProblemProgressListResponse:
    """List the published catalog annotated with one learner's status.

    Every published problem appears, including ones the learner has never
    opened, so a client can render "Not Started" without a second request. The
    optional filters narrow the same catalog; none of them can widen it beyond
    what the learner is allowed to see.
    """
    filters = [Problem.is_published.is_(True)]
    if difficulty:
        filters.append(Problem.difficulty == difficulty)
    if topic:
        filters.append(cast(Problem.topics, Text).ilike(f"%{topic}%"))

    rows = session.execute(
        select(Problem, Progress)
        .outerjoin(
            Progress,
            (Progress.problem_id == Problem.id) & (Progress.user_id == user_id),
        )
        .where(*filters)
        .order_by(Problem.difficulty, Problem.title)
    ).all()
    items = [to_response(problem, progress) for problem, progress in rows]

    if status:
        wanted = normalize_status(status)
        items = [item for item in items if item.status == wanted]

    total = len(items)
    return ProblemProgressListResponse(
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_problem_progress(
    session: Session, user_id: int, problem: Problem
) -> ProblemProgressResponse:
    return to_response(problem, get_progress_row(session, user_id, problem.id))


# ------------------------------------------------------------------- mutations


def _lock_or_create(session: Session, user_id: int, problem_id: int) -> Progress:
    """Return this learner's row for the problem, inserting it on first use."""
    progress = get_progress_row(session, user_id, problem_id)
    if progress is not None:
        return progress

    progress = Progress(
        user_id=user_id,
        problem_id=problem_id,
        status=ProgressStatus.NOT_STARTED.value,
        attempts_count=0,
    )
    session.add(progress)
    try:
        # Claim the (user_id, problem_id) slot immediately so a concurrent
        # writer loses here rather than at flush time with a partial object.
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateProgressError("Progress for this problem already exists.") from error
    return progress


def _record_best(
    progress: Progress, best_runtime_ms: int | None, best_memory_mb: int | None
) -> None:
    """Keep the fastest runtime and the smallest memory footprint ever reported."""
    if best_runtime_ms is not None:
        if progress.best_runtime_ms is None or best_runtime_ms < progress.best_runtime_ms:
            progress.best_runtime_ms = best_runtime_ms
    if best_memory_mb is not None:
        if progress.best_memory_mb is None or best_memory_mb < progress.best_memory_mb:
            progress.best_memory_mb = best_memory_mb


def _commit(session: Session, progress: Progress) -> Progress:
    try:
        session.commit()
    except IntegrityError as error:
        # Lost a race on the unique constraint. The winner's row is the truth.
        session.rollback()
        raise DuplicateProgressError("Progress for this problem already exists.") from error
    session.refresh(progress)
    return progress


def record_attempt(
    session: Session,
    user_id: int,
    problem: Problem,
    best_runtime_ms: int | None = None,
    best_memory_mb: int | None = None,
) -> Progress:
    """Record that the learner worked on the problem again.

    This counts an attempt; it does not judge the attempt. A learner who has
    already solved the problem stays solved, because re-reading a solution is
    not a regression.
    """
    progress = _lock_or_create(session, user_id, problem.id)
    progress.attempts_count = min(int(progress.attempts_count or 0) + 1, 1_000_000)
    progress.last_attempted_at = utc_now()
    if normalize_status(progress.status) == ProgressStatus.NOT_STARTED.value:
        progress.status = ProgressStatus.ATTEMPTED.value
    _record_best(progress, best_runtime_ms, best_memory_mb)
    return _commit(session, progress)


def set_status(
    session: Session,
    user_id: int,
    problem: Problem,
    status: str | None = None,
    best_runtime_ms: int | None = None,
    best_memory_mb: int | None = None,
) -> Progress:
    """Move the learner's record for a problem to an explicit status.

    ``status=None`` records measurements only and leaves the status alone, so a
    future runner can report a measurement without restating the verdict.

    Timestamp side effects follow the transition so the record never
    contradicts itself: claiming a solve stamps ``solved_at`` and counts at
    least one attempt, and returning to ``not_started`` clears the trail instead
    of leaving a stale solve date behind.

    A value outside the vocabulary raises before anything is written, so a
    rejected request never leaves a stray record behind.
    """
    if status is not None and status not in {member.value for member in ProgressStatus}:
        # Deliberately not run through ``normalize_status``: that maps a legacy
        # label such as "completed", which is right for reading a stored row but
        # wrong for a caller-supplied value that does not exist.
        raise ValueError(f"Unsupported progress status: {status!r}.")

    now = utc_now()
    progress = _lock_or_create(session, user_id, problem.id)
    previous = normalize_status(progress.status)

    if status is None:
        _record_best(progress, best_runtime_ms, best_memory_mb)
        progress.updated_at = now
        return _commit(session, progress)

    target = status

    if target == ProgressStatus.NOT_STARTED.value:
        progress.status = target
        progress.attempts_count = 0
        progress.last_attempted_at = None
        progress.solved_at = None
        progress.best_runtime_ms = None
        progress.best_memory_mb = None
    else:
        progress.status = target
        if target == ProgressStatus.ATTEMPTED.value and previous == ProgressStatus.SOLVED.value:
            # Undoing a self-reported solve: the solve date must not survive it.
            progress.solved_at = None
        if target == ProgressStatus.SOLVED.value and previous != ProgressStatus.SOLVED.value:
            progress.solved_at = now
        if int(progress.attempts_count or 0) < 1:
            # Claiming an attempt or a solve implies at least one attempt.
            progress.attempts_count = 1
        progress.last_attempted_at = progress.last_attempted_at or now
        _record_best(progress, best_runtime_ms, best_memory_mb)

    return _commit(session, progress)


# --------------------------------------------------------------------- summary


def _activity_dates(rows: list[Progress]) -> set[date]:
    """The calendar days on which the learner recorded any activity.

    Derived only from timestamps the learner actually produced, so the streak
    reflects recorded work rather than an inferred habit.
    """
    days: set[date] = set()
    for row in rows:
        for stamp in (as_utc(row.last_attempted_at), as_utc(row.solved_at)):
            if stamp is not None:
                days.add(stamp.date())
    return days


def current_streak_days(rows: list[Progress], today: date | None = None) -> int:
    """Consecutive days of recorded activity ending today or yesterday.

    Yesterday still counts: a streak is alive until a full day passes with no
    activity, which is what a learner expects at the end of a long session.
    """
    days = _activity_dates(rows)
    if not days:
        return 0

    reference = today or utc_now().date()
    if reference not in days and (reference - timedelta(days=1)) not in days:
        return 0

    streak = 0
    cursor = reference if reference in days else reference - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_progress_summary(
    session: Session, user_id: int, today: date | None = None
) -> ProgressSummaryResponse:
    """Overall standing for one learner across the published catalog.

    The catalog defines the denominator, so a learner with no rows at all
    reports a real `not_started` count rather than an empty object.
    """
    problems = list(
        session.scalars(
            select(Problem).where(Problem.is_published.is_(True)).order_by(Problem.id)
        )
    )
    progress_by_problem: dict[int, Progress] = {}
    if problems:
        for row in session.scalars(
            select(Progress).where(
                Progress.user_id == user_id,
                Progress.problem_id.in_([problem.id for problem in problems]),
            )
        ):
            progress_by_problem[row.problem_id] = row

    attempted = 0
    solved = 0
    total_by_difficulty: dict[str, int] = {}
    solved_by_difficulty: dict[str, int] = {}
    total_by_topic: dict[str, int] = {}
    solved_by_topic: dict[str, int] = {}

    for problem in problems:
        total_by_difficulty[problem.difficulty] = total_by_difficulty.get(problem.difficulty, 0) + 1
        for topic in _topics_of(problem):
            total_by_topic[topic] = total_by_topic.get(topic, 0) + 1

        row = progress_by_problem.get(problem.id)
        if row is None:
            continue
        status = normalize_status(row.status)
        if status == ProgressStatus.ATTEMPTED.value:
            attempted += 1
        elif status == ProgressStatus.SOLVED.value:
            solved += 1
            solved_by_difficulty[problem.difficulty] = (
                solved_by_difficulty.get(problem.difficulty, 0) + 1
            )
            for topic in _topics_of(problem):
                solved_by_topic[topic] = solved_by_topic.get(topic, 0) + 1

    total = len(problems)
    return ProgressSummaryResponse(
        total_problems=total,
        # A solved problem is also an attempted one, so this is a strict count
        # of rows that are neither solved nor untouched.
        attempted=attempted,
        solved=solved,
        not_started=max(total - attempted - solved, 0),
        completion_percentage=round(solved / total * 100, 2) if total else 0.0,
        current_streak_days=current_streak_days(
            list(progress_by_problem.values()), today=today
        ),
        total_by_difficulty=dict(sorted(total_by_difficulty.items())),
        solved_by_difficulty=dict(sorted(solved_by_difficulty.items())),
        total_by_topic=dict(sorted(total_by_topic.items())),
        solved_by_topic=dict(sorted(solved_by_topic.items())),
    )


def progress_counts_by_status(
    session: Session, user_id: int
) -> dict[str, int]:
    """Raw per-status row counts for the learner, keyed by canonical status."""
    rows = session.execute(
        select(Progress.status, func.count(Progress.id))
        .where(Progress.user_id == user_id)
        .group_by(Progress.status)
    ).all()
    counts = {status.value: 0 for status in ProgressStatus}
    for status, count in rows:
        counts[normalize_status(status)] = int(count)
    return counts


__all__ = [
    "DuplicateProgressError",
    "ProblemProgressListResponse",
    "ProblemProgressResponse",
    "ProgressSummaryResponse",
    "current_streak_days",
    "get_progress_row",
    "get_progress_summary",
    "get_problem_progress",
    "get_user_progress",
    "list_progress",
    "progress_counts_by_status",
    "record_attempt",
    "set_status",
    "to_response",
]
