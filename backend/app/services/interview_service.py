"""Mock interview use cases.

The rules hold everywhere in this module, matching the progress and submission
services:

* the caller supplies ``user_id``, resolved from the bearer token by
  ``get_current_user`` -- never a value from a request, so no request can reach
  another learner's interviews;
* every read is filtered by that ``user_id``, so a session that exists but
  belongs to someone else is indistinguishable from one that does not exist;
* a verdict, a pass count, a runtime, and a score are **never** client-sent.
  Submitting runs the real judge and stores the real result; scoring is a pure
  read of the stored question rows at completion time.

Two interview-specific rules follow:

* **the selection is deterministic and durable.** :func:`select_interview_questions`
  is a pure function of the published catalog and the request's filters; what it
  picks is written as ``interview_questions`` rows *before* the session can be
  started, so an interview can never be recreated from its creation request and
  never drawn randomly at read time.
* **the timer is a server-side timestamp.** ``started_at``/``expires_at`` are
  written when a session starts; every read and write checks the server clock
  against ``expires_at``; and a session whose clock has run out is finalised on
  the next touch. The API never accepts a client-computed remaining time.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil

from database.models import Problem
from database.models.interview import (
    ACTIVE_INTERVIEW_STATUSES,
    INTERVIEW_STATUS_VALUES,
    InterviewQuestion,
    InterviewQuestionStatus,
    InterviewSession,
    InterviewStatus,
)
from database.models.progress import utc_now
from database.models.submission import SubmissionStatus, normalize_submission_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.schemas.interview import (
    InterviewListResponse,
    InterviewQuestionResponse,
    InterviewReportQuestion,
    InterviewReportResponse,
    InterviewSessionResponse,
    InterviewSummaryResponse,
)
from backend.app.services import judge_service, submission_service
from backend.app.services.judge_service import SubmissionJudgement

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

#: The tier order for the deterministic selection. Difficulty is the primary
#: ordering key: the catalog's own display sorts ``Easy -> Medium -> Hard``, so a
#: selection that mixes tiers should read the same way, left to right.
DIFFICULTY_ORDER = ("Easy", "Medium", "Hard")

_DIFFICULTY_RANK = {"Easy": 0, "Medium": 1, "Hard": 2}
#: A difficulty the catalog does not spell with a capital letter sorts after the
#: three known tiers, so an unusual tier can never outrank an ``Easy`` problem.
_UNKNOWN_DIFFICULTY_RANK = 3


class NotEnoughProblemsError(ValueError):
    """The catalog cannot supply the requested selection.

    Reported as a conflict rather than silently serving a shorter interview:
    a session whose question budget was not honoured would surprise the learner
    at the end, and a filter that matches nothing should say so.
    """


class ActiveSessionError(RuntimeError):
    """The learner already has a session that is created or running.

    A learner gets one active session; creating a second one is a conflict, not
    a new session, because two timers running in parallel would be two
    interviews the learner never agreed to.
    """


class SessionStateError(RuntimeError):
    """A lifecycle transition was attempted from the wrong state."""


class SessionExpiredError(SessionStateError):
    """The timer ran out before the attempt.

    Separate from a generic state error so the API can say so honestly: the
    session did not reject the answer because it was finished -- it rejected it
    because the clock ran out.
    """


# ----------------------------------------------------------------------- helpers


def _topics_of(problem: Problem) -> list[str]:
    topics = problem.topics
    if not isinstance(topics, list):
        return []
    return [str(topic) for topic in topics if isinstance(topic, (str, int, float))]


def _difficulty_rank(problem: Problem) -> int:
    """Stable sort key for difficulty, with an escape hatch for odd spellings."""
    return _DIFFICULTY_RANK.get(problem.difficulty, _UNKNOWN_DIFFICULTY_RANK)


def select_interview_questions(
    problems: list[Problem],
    question_count: int,
    difficulty: str | None = None,
    topic: str | None = None,
) -> list[Problem]:
    """Pick, in order, the problems one interview will ask.

    Pure and deterministic. ``difficulty`` matches the catalog's own spelling
    exactly (``Easy``/``Medium``/``Hard``; validated by the request schema), and
    ``topic`` matches a problem topic case-insensitively. Problems are taken from
    the published catalog only.

    Ordering is a round-robin across the difficulty tiers (`Easy, then Medium,
    then Hard`), each tier sorted by id so two identical filters always pick the
    same problems in the same order. The round-robin spreads the difficulties
    through the session the way a real interview does, rather than front-loading
    every easy problem.

    The function never throws when the catalog is too small: it returns what it
    could pick, ordered as described, and the caller decides whether the count is
    acceptable.
    """
    wanted_difficulty = difficulty
    wanted_topic = topic.strip().lower() if topic else None

    tiers: dict[str, list[Problem]] = {level: [] for level in DIFFICULTY_ORDER}
    unknown: list[Problem] = []
    for problem in problems:
        if not problem.is_published:
            continue
        if wanted_difficulty and problem.difficulty != wanted_difficulty:
            continue
        if wanted_topic and not any(
            str(value).strip().lower() == wanted_topic for value in _topics_of(problem)
        ):
            continue
        if problem.difficulty in tiers:
            tiers[problem.difficulty].append(problem)
        else:
            unknown.append(problem)

    for tier in tiers.values():
        tier.sort(key=lambda problem: (problem.id, problem.slug))
    unknown.sort(key=lambda problem: (_difficulty_rank(problem), problem.id))
    tier_order = [tiers[level] for level in DIFFICULTY_ORDER] + [unknown]

    selected: list[Problem] = []
    cursors = [0] * len(tier_order)
    while len(selected) < question_count:
        progressed = False
        for index, tier in enumerate(tier_order):
            if cursors[index] >= len(tier):
                continue
            selected.append(tier[cursors[index]])
            cursors[index] += 1
            progressed = True
            if len(selected) >= question_count:
                break
        if not progressed:
            break
    return selected[:question_count]


def _pending_positions(interview: InterviewSession) -> list[int]:
    return [
        question.position
        for question in interview.questions
        if question.status == InterviewQuestionStatus.PENDING.value
    ]


def _question_verdict(question: InterviewQuestion) -> SubmissionStatus | None:
    """The judge's verdict for a question, or ``None`` while it has none.

    A question with no linked submission has no verdict, and the verdict always
    comes from the stored submission row -- never from a value a request sent.
    """
    if not question.is_submitted or question.submission is None:
        return None
    canonical = normalize_submission_status(question.submission.status)
    try:
        return SubmissionStatus(canonical)
    except ValueError:  # pragma: no cover - defensive against a legacy label
        return SubmissionStatus.FAILED


def _question_accepted(question: InterviewQuestion) -> bool:
    return _question_verdict(question) is SubmissionStatus.ACCEPTED


def compute_score(questions: list[InterviewQuestion]) -> int:
    """The deterministic 0-100 score for a finished session.

    ``round(100 * accepted / total)`` over the stored question rows. Python's
    ``round`` is documented -- a half stays even -- so a 1/2 session scores 50,
    a 1/3 session scores 33, and a 2/3 session scores 67; whatever the division
    does, it does the same every time it runs.
    """
    total = len(questions)
    if not total:
        return 0
    accepted = sum(1 for question in questions if _question_accepted(question))
    return int(round(accepted / total * 100))


def _load_interview(db: Session, user_id: int, interview_id: int) -> InterviewSession | None:
    """One interview, but only if the caller owns it.

    The ``user_id`` predicate is part of the lookup, exactly like
    ``submission_service.get_submission``: "not yours" and "does not exist" are
    the same answer. The questions and their problems and judged submissions are
    loaded eagerly so the projections that follow never need a lazy load.
    """
    return db.scalar(
        select(InterviewSession)
        .where(
            InterviewSession.id == interview_id,
            InterviewSession.user_id == user_id,
        )
        .options(
            selectinload(InterviewSession.questions).selectinload(InterviewQuestion.problem),
            selectinload(InterviewSession.questions).selectinload(InterviewQuestion.submission),
        )
    )


def _expire_if_needed(
    db: Session, interview: InterviewSession, now: datetime | None = None
) -> None:
    """Finalise a running session whose clock has run out, once.

    Idempotent: only an ``in_progress`` session is even considered, and once it
    is completed it is not in_progress, so a completed session is never
    "expired" again. The completion timestamp is ``expires_at`` itself -- the
    moment the timer ran out -- which is also what makes
    ``was_timed_out`` true for exactly these sessions.
    """
    if not interview.is_in_progress:
        return
    expires = interview.expires_at_utc
    if expires is None:
        return
    if (now or utc_now()) < expires:
        return
    _finalise(db, interview, InterviewStatus.COMPLETED.value, when=expires)


def _finalise(
    db: Session,
    interview: InterviewSession,
    target_status: str,
    when: datetime,
) -> None:
    """Move a session to a terminal state and write the score with it.

    A ``completed`` transition computes and stores the deterministic score; an
    ``abandoned`` transition never scores, so an abandoned interview honestly has
    ``score=None`` rather than the harvest of a partial run.
    """
    interview.status = target_status
    interview.completed_at = when
    if target_status == InterviewStatus.COMPLETED.value:
        interview.score = compute_score(interview.questions)
    db.add(interview)
    db.commit()


# ------------------------------------------------------------------- mutations


def create_interview(
    db: Session,
    user_id: int,
    *,
    question_count: int,
    duration_seconds: int,
    role: str,
    level: str | None,
    difficulty: str | None,
    topic: str | None,
) -> InterviewSession:
    """Create a session with its questions already recorded.

    One active session is enforced as a conflict: a learner who has a created or
    running session cannot open a second timer. The questions are selected
    deterministically from the published catalog, stored, and *then* the session
    is committed, so the selection survives whatever happens next.
    """
    active = db.scalar(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status.in_(ACTIVE_INTERVIEW_STATUSES),
        )
        .order_by(InterviewSession.id.desc())
        .limit(1)
    )
    if active is not None:
        raise ActiveSessionError(
            f"A session is already active (interview {active.id}). Finish or abandon it "
            "before creating another."
        )

    catalog = list(
        db.scalars(
            select(Problem).where(Problem.is_published.is_(True)).order_by(Problem.id)
        )
    )
    selected = select_interview_questions(
        catalog,
        question_count,
        difficulty=difficulty,
        topic=topic,
    )
    if len(selected) < question_count:
        raise NotEnoughProblemsError(
            f"The published catalog can supply {len(selected)} problems for these filters; "
            f"{question_count} were asked for. Widen the filters or lower question_count."
        )

    interview = InterviewSession(
        user_id=user_id,
        status=InterviewStatus.CREATED.value,
        role=role.strip(),
        level=level.strip() if level else None,
        difficulty=difficulty,
        topic=topic.strip() if topic else None,
        question_count=question_count,
        duration_seconds=duration_seconds,
        current_index=0,
    )
    db.add(interview)
    db.flush()
    for position, problem in enumerate(selected):
        db.add(
            InterviewQuestion(
                session_id=interview.id,
                problem_id=problem.id,
                position=position,
                status=InterviewQuestionStatus.PENDING.value,
                attempts=0,
            )
        )
    db.commit()
    loaded = _load_interview(db, user_id, interview.id)
    assert loaded is not None  # freshly created and owned, so this cannot miss
    return loaded


def start_interview(
    db: Session,
    user_id: int,
    interview_id: int,
    now: datetime | None = None,
) -> InterviewSession | None:
    """Start the clock on a created session.

    ``started_at`` and ``expires_at`` are written here, from the server clock.
    A session that is not ``created`` -- because it is already running, already
    finished, or was abandoned -- is a state error, because starting a session
    twice would restart its timer and an abandoned session must not resurrect.
    """
    interview = _load_interview(db, user_id, interview_id)
    if interview is None:
        return None
    now = now or utc_now()
    _expire_if_needed(db, interview, now)
    if interview.was_timed_out:
        raise SessionExpiredError("This interview's time already ran out.")
    if not interview.is_created:
        raise SessionStateError("Only a created interview can be started.")

    interview.status = InterviewStatus.IN_PROGRESS.value
    interview.started_at = now
    interview.expires_at = now + timedelta(seconds=max(int(interview.duration_seconds), 0))
    pending = _pending_positions(interview)
    interview.current_index = pending[0] if pending else 0
    db.add(interview)
    db.commit()
    loaded = _load_interview(db, user_id, interview.id)
    assert loaded is not None
    return loaded


def submit_answer(
    db: Session,
    user_id: int,
    interview_id: int,
    position: int,
    language: str,
    source_code: str,
    settings,
    now: datetime | None = None,
) -> tuple[InterviewSession | None, InterviewQuestion | None]:
    """Judge the learner's code for one recorded question.

    The problem comes from the recorded ``interview_questions`` row, never from
    the request, so a client can only answer a question that was actually drawn.
    The language is resolved against what that problem supports (an unknown or
    unsupported language is ``UnsupportedLanguageError``, a 422, *before*
    anything is stored), and the answer then goes through the same durable,
    judge-produced pipeline as a normal submission: store the row unjudged,
    count an attempt, run the judge over the full case set, store the verdict,
    record accepted progress if the judge said so -- and only then link the
    submission to the question.

    Stopping the clock is the service's job, not the submitter's: a submission
    at or after ``expires_at`` is refused as ``SessionExpiredError`` after the
    session has been finalised as completed (timed out). The client is never
    asked how much time is left.

    The last submission in a session completes it with its deterministic score.
    """
    interview = _load_interview(db, user_id, interview_id)
    if interview is None:
        return None, None
    now = now or utc_now()
    _expire_if_needed(db, interview, now)
    if interview.was_timed_out:
        raise SessionExpiredError("This interview's time has run out.")
    if not interview.is_in_progress:
        raise SessionStateError("Only a running interview accepts answers.")

    question = next(
        (candidate for candidate in interview.questions if candidate.position == position),
        None,
    )
    if question is None:
        return None, None
    problem = question.problem
    language_spec = judge_service.resolve_language(problem, language, settings)

    submission = submission_service.create_submission(
        db, user_id, problem, language, source_code
    )
    submission_service.record_submission_attempt(db, user_id, problem)
    judgement: SubmissionJudgement = judge_service.judge_submission(
        problem, language_spec, source_code, settings
    )
    submission = submission_service.apply_judgement(db, submission, judgement)
    submission_service.record_accepted_progress(db, user_id, problem, submission)

    question.status = InterviewQuestionStatus.SUBMITTED.value
    question.submission = submission
    question.submission_id = submission.id
    question.attempts = int(question.attempts or 0) + 1
    question.answered_at = question.answered_at_utc or now
    db.add(question)

    pending = _pending_positions(interview)
    if not pending:
        _finalise(db, interview, InterviewStatus.COMPLETED.value, when=now)
    else:
        interview.current_index = min(pending)
        db.add(interview)
        db.commit()

    loaded = _load_interview(db, user_id, interview_id)
    return loaded, question


def finish_interview(
    db: Session,
    user_id: int,
    interview_id: int,
    now: datetime | None = None,
) -> InterviewSession | None:
    """End a running session early and score what was answered.

    Finishing before the clock runs out completes the session with
    ``was_timed_out=False``; a session whose clock already ran out raises
    ``SessionExpiredError`` instead, because the timer -- not the learner --
    already ended it and the learner cannot claim the late finish.
    """
    interview = _load_interview(db, user_id, interview_id)
    if interview is None:
        return None
    now = now or utc_now()
    _expire_if_needed(db, interview, now)
    if interview.was_timed_out:
        raise SessionExpiredError("This interview's time has run out.")
    if not interview.is_in_progress:
        raise SessionStateError("Only a running interview can be finished.")
    _finalise(db, interview, InterviewStatus.COMPLETED.value, when=now)
    loaded = _load_interview(db, user_id, interview_id)
    assert loaded is not None
    return loaded


def abandon_interview(
    db: Session,
    user_id: int,
    interview_id: int,
    now: datetime | None = None,
) -> InterviewSession | None:
    """Discard a created or running session, leaving it unscored.

    An abandoned session is ``abandoned`` with ``score=None`` and
    ``completed_at`` stamped now. A session the timer already ended raises
    ``SessionExpiredError``: it was not abandoned -- it finished, and the honest
    term for that is ``completed``.
    """
    interview = _load_interview(db, user_id, interview_id)
    if interview is None:
        return None
    now = now or utc_now()
    _expire_if_needed(db, interview, now)
    if interview.was_timed_out:
        raise SessionExpiredError("This interview's time has run out.")
    if not interview.is_active:
        raise SessionStateError("Only an active interview can be abandoned.")
    interview.status = InterviewStatus.ABANDONED.value
    interview.completed_at = now
    db.add(interview)
    db.commit()
    loaded = _load_interview(db, user_id, interview_id)
    assert loaded is not None
    return loaded


# --------------------------------------------------------------------- lookups


def load_session(
    db: Session,
    user_id: int,
    interview_id: int,
    now: datetime | None = None,
) -> InterviewSession | None:
    """One owned interview, finalising it if its clock ran out.

    Reads have the same side effect as writes because the timer is a server
    timestamp: the first read after ``expires_at`` is the moment the session is
    honestly complete. A subsequent read is a pure read.
    """
    interview = _load_interview(db, user_id, interview_id)
    if interview is None:
        return None
    _expire_if_needed(db, interview, now)
    return interview


def get_active_interview(
    db: Session,
    user_id: int,
    now: datetime | None = None,
) -> InterviewSession | None:
    """The learner's active session, if any.

    "Active" means created or running; a session whose clock ran out is
    finalised here and returned, so the caller sees the real terminal state
    rather than a session pretending its timer still stands.
    """
    interview = db.scalar(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status.in_(ACTIVE_INTERVIEW_STATUSES),
        )
        .order_by(InterviewSession.id.desc())
        .limit(1)
    )
    if interview is None:
        return None
    _expire_if_needed(db, interview, now)
    return interview


def list_interviews(
    db: Session,
    user_id: int,
    status: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> InterviewListResponse:
    """One page of the learner's interview history, newest first.

    The optional ``status`` filter can only narrow the result, and any other
    value is a ``ValueError`` (a 422) rather than a silent empty page.
    """
    page = max(int(page), 1)
    page_size = min(max(int(page_size), 1), MAX_PAGE_SIZE)
    filters = [InterviewSession.user_id == user_id]
    if status is not None:
        if status not in INTERVIEW_STATUS_VALUES:
            raise ValueError(f"Unsupported interview status: {status!r}.")
        filters.append(InterviewSession.status == status)

    total = int(db.scalar(select(func.count()).select_from(InterviewSession).where(*filters)) or 0)
    rows = db.scalars(
        select(InterviewSession)
        .where(*filters)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return InterviewListResponse(
        items=[_to_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


# ---------------------------------------------------------------- projections


def to_session_response(
    interview: InterviewSession,
    now: datetime | None = None,
) -> InterviewSessionResponse:
    """The session as the API publishes it, time checked server-side.

    ``remaining_seconds`` is derived from the stored ``expires_at`` and the
    server clock at projection time -- never from anything the client sent -- and
    is ``None`` once the session is not actively running.
    """
    now = now or utc_now()
    return InterviewSessionResponse(
        id=interview.id,
        status=interview.status,
        role=interview.role,
        level=interview.level,
        difficulty=interview.difficulty,
        topic=interview.topic,
        question_count=interview.question_count,
        duration_seconds=interview.duration_seconds,
        current_index=interview.current_index,
        score=interview.score,
        created_at=interview.created_at_utc,
        started_at=interview.started_at_utc,
        expires_at=interview.expires_at_utc,
        completed_at=interview.completed_at_utc,
        remaining_seconds=_remaining_seconds(interview, now),
        timed_out=interview.was_timed_out,
        questions=[_question_response(question) for question in interview.questions],
    )


def to_report_response(
    interview: InterviewSession,
    now: datetime | None = None,
) -> InterviewReportResponse:
    """The report for a completed interview.

    Every number is a read of the stored session and question rows: the score is
    the stored completion score, the answered/accepted counts are derived from
    the question statuses and linked verdicts, and ``duration_used_seconds`` is
    the stored completion minus start. Nothing here is estimated.
    """
    completed = interview.completed_at_utc or (now or utc_now())
    started = interview.started_at_utc
    answered = [q for q in interview.questions if q.is_submitted]
    accepted = [q for q in answered if _question_accepted(q)]
    duration_used = (
        max(0, int((completed - started).total_seconds())) if started is not None else 0
    )
    return InterviewReportResponse(
        id=interview.id,
        role=interview.role,
        level=interview.level,
        difficulty=interview.difficulty,
        topic=interview.topic,
        status=InterviewStatus.COMPLETED.value,
        question_count=interview.question_count,
        duration_seconds=interview.duration_seconds,
        score=int(interview.score or compute_score(interview.questions)),
        timed_out=interview.was_timed_out,
        started_at=started,
        completed_at=completed,
        duration_used_seconds=duration_used,
        questions_answered=len(answered),
        questions_accepted=len(accepted),
        questions=[_to_report_question(question) for question in interview.questions],
    )


def _remaining_seconds(interview: InterviewSession, now: datetime) -> int | None:
    """Whole seconds left, or ``None`` when no timer is running."""
    if not interview.is_in_progress:
        return None
    expires = interview.expires_at_utc
    if expires is None:
        return None
    return max(0, ceil((expires - now).total_seconds()))


def _question_response(question: InterviewQuestion) -> InterviewQuestionResponse:
    """One recorded question: the problem's public identity, its outcome, never
    its test material."""
    problem = question.problem
    topics = _topics_of(problem)
    submission = question.submission
    return InterviewQuestionResponse(
        position=question.position,
        problem_id=problem.id,
        slug=problem.slug,
        title=problem.title,
        summary=problem.summary,
        difficulty=problem.difficulty,
        topics=topics,
        primary_topic=topics[0] if topics else "Uncategorised",
        status=question.status,
        verdict=_question_verdict(question),
        submission_id=question.submission_id,
        accepted=_question_accepted(question),
        attempts=int(question.attempts or 0),
        runtime_ms=submission.runtime_ms if submission is not None else None,
        answered_at=question.answered_at_utc,
    )


def _to_report_question(question: InterviewQuestion) -> InterviewReportQuestion:
    """The report's view of one question: the session view plus the judge's
    measurements."""
    base = _question_response(question).model_dump()
    submission = question.submission
    base.update(
        test_cases_passed=submission.test_cases_passed if submission is not None else None,
        test_cases_total=submission.test_cases_total if submission is not None else None,
        memory_mb=submission.memory_mb if submission is not None else None,
    )
    return InterviewReportQuestion(**base)


def _to_summary(interview: InterviewSession) -> InterviewSummaryResponse:
    """The compact history-row projection."""
    return InterviewSummaryResponse(
        id=interview.id,
        status=interview.status,
        role=interview.role,
        level=interview.level,
        difficulty=interview.difficulty,
        question_count=interview.question_count,
        score=interview.score,
        timed_out=interview.was_timed_out,
        created_at=interview.created_at_utc,
        completed_at=interview.completed_at_utc,
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ActiveSessionError",
    "NotEnoughProblemsError",
    "SessionExpiredError",
    "SessionStateError",
    "abandon_interview",
    "compute_score",
    "create_interview",
    "finish_interview",
    "get_active_interview",
    "list_interviews",
    "load_session",
    "select_interview_questions",
    "start_interview",
    "submit_answer",
    "to_report_response",
    "to_session_response",
]