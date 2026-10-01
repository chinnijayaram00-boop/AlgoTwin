"""Submission use cases: persist a judged attempt and read it back.

Three rules hold everywhere in this module, matching the progress service:

* the caller supplies ``user_id``, and it is the id resolved from the bearer
  token by ``get_current_user`` -- never a value from the request body, query
  string, or path, so no request can address another learner's submissions;
* every read and every listing is filtered by that ``user_id``, so two learners
  working the same problem keep entirely separate histories;
* a submission is written twice. The row is first stored **unjudged**
  (``queued``) and committed, so the learner's code survives even if the process
  dies mid-run; the judge verdict and its measurements are then applied in a
  second commit. A row that reached only the first write stays ``queued``
  forever, which is honest -- it really was stored and never judged -- and is
  never mistaken for a pass.

The judge itself lives in :mod:`backend.app.judge` and is reached through
:mod:`backend.app.services.judge_service`; this module never runs, compiles, or
compares anything. It records what the judge reported and nothing more.
"""

from math import ceil

from database.models import Problem, Submission
from database.models.submission import (
    INITIAL_SUBMISSION_STATUS,
    SubmissionStatus,
    normalize_submission_status,
    utc_now,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.schemas.submissions import (
    SubmissionDetailResponse,
    SubmissionListResponse,
    SubmissionSummaryResponse,
)
from backend.app.services import progress_service
from backend.app.services.judge_service import SubmissionJudgement

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


# ------------------------------------------------------------------- projections


def _summary(submission: Submission) -> SubmissionSummaryResponse:
    """Project a submission into the shape a history list needs.

    Only fields the learner already knows about themselves are copied out. There
    is no ``user_id`` in the projection: the caller already knows the record is
    theirs, and echoing the owner would be one more value to leak by accident.
    """
    problem = submission.problem
    return SubmissionSummaryResponse(
        id=submission.id,
        problem_id=submission.problem_id,
        problem_slug=problem.slug if problem is not None else "",
        problem_title=problem.title if problem is not None else "",
        language=submission.language,
        status=SubmissionStatus(normalize_submission_status(submission.status)),
        test_cases_passed=submission.test_cases_passed,
        test_cases_total=submission.test_cases_total,
        runtime_ms=submission.runtime_ms,
        memory_mb=submission.memory_mb,
        error_message=submission.error_message,
        submitted_at=submission.submitted_at_utc,
        judged_at=submission.judged_at_utc,
    )


def to_detail_response(submission: Submission) -> SubmissionDetailResponse:
    """Project a submission into the detail shape, including its source."""
    return SubmissionDetailResponse(
        **_summary(submission).model_dump(),
        source_code=submission.source_code,
    )


# ----------------------------------------------------------------------- lookups


def get_submission(session: Session, user_id: int, submission_id: int) -> Submission | None:
    """Fetch one submission, but only if the caller owns it.

    The ``user_id`` predicate is part of the lookup, not a check afterwards, so
    there is no code path that can load another learner's row and then decide
    what to do with it. A row that exists but belongs to someone else is
    indistinguishable from one that does not exist: both return ``None``, and the
    router reports both as 404.
    """
    return session.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.user_id == user_id,
        )
    )


# --------------------------------------------------------------------- mutations


def create_submission(
    session: Session,
    user_id: int,
    problem: Problem,
    language: str,
    source_code: str,
) -> Submission:
    """Store a submission for the learner and return it unjudged.

    The row is created ``queued`` and committed before any judging happens, so
    the learner's code is durable the moment it is accepted -- even if the judge
    never gets to run. The caller then judges it and calls
    :func:`apply_judgement` with the real result. A submission left at ``queued``
    means exactly "stored, not judged"; it is never read as a pass.
    """
    submission = Submission(
        user_id=user_id,
        problem_id=problem.id,
        language=language,
        source_code=source_code,
        status=INITIAL_SUBMISSION_STATUS,
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


def apply_judgement(session: Session, submission: Submission, judgement: SubmissionJudgement):
    """Write the judge's verdict and measurements onto a stored submission.

    The status comes straight from the judge and is stored verbatim. This
    function does not interpret, soften, or second-guess the verdict: it writes
    what it is told. The two guards it does add are about the *consistency* of
    the record, not its truth:

    * a ``queued``/``running`` status is never written, because a finished
      judgement is never pending -- a submission that has a verdict has left the
      pending states;
    * an ``accepted`` verdict is only stored if it passed every case it ran. A
      truncated run (fewer cases executed than exist) or a run that reports
      fewer passes than the total is demoted to ``failed`` rather than recorded
      as a pass, because "accepted" on a partial or inconsistent report would be
      a claim the measurements on the same row contradict.

    Everything else -- a wrong answer, a timeout, a crash, a memory kill -- is
    recorded as-is.
    """
    status = judgement.verdict
    if status in {SubmissionStatus.QUEUED, SubmissionStatus.RUNNING}:
        # A judgement that still says "pending" is not a judgement. Recording it
        # as-is would leave a finished submission looking unjudged forever.
        status = SubmissionStatus.FAILED
    if status is SubmissionStatus.ACCEPTED:
        # An accepted verdict has to be consistent with the counts stored beside
        # it, or the row would claim a pass it cannot support.
        if (
            judgement.cases_total <= 0
            or judgement.cases_run < judgement.cases_total
            or judgement.cases_passed < judgement.cases_total
        ):
            status = SubmissionStatus.FAILED

    submission.status = status.value
    submission.test_cases_passed = judgement.cases_passed
    submission.test_cases_total = judgement.cases_total
    submission.runtime_ms = judgement.total_runtime_ms
    submission.memory_mb = judgement.rounded_peak_memory_mb
    submission.error_message = judgement.error_message
    submission.judged_at = utc_now()
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


def record_submission_attempt(session: Session, user_id: int, problem: Problem):
    """Count a stored submission as one attempt on the learner's progress record.

    This runs for every submission, accepted or not: sending code to the judge is
    evidence the learner worked on the problem, so the attempt count goes up and
    the problem moves to ``attempted`` if it was untouched. The existing
    ``record_attempt`` keeps an already-solved problem solved.

    This function deliberately does **not** mark a problem solved. Solving is the
    job of :func:`record_accepted_progress`, which runs only when the judge
    returned ``accepted``.
    """
    try:
        return progress_service.record_attempt(session, user_id, problem)
    except progress_service.DuplicateProgressError:
        # `record_attempt` rolled the session back, so the winner's row is now
        # readable and a second call increments it instead of raising again.
        return progress_service.record_attempt(session, user_id, problem)


def record_accepted_progress(
    session: Session,
    user_id: int,
    problem: Problem,
    submission: Submission,
):
    """Mark the problem solved, but only for a stored ``accepted`` verdict.

    Every non-accepted status returns without touching progress. This is the
    single place a submission can make a problem ``solved``, and it is gated on
    the row itself having been stored as ``accepted`` -- not on the learner
    clicking a "mark as solved" button, and not on the submission merely
    existing.

    The gate reads ``submission.status``, the value :func:`apply_judgement`
    actually committed, rather than the judgement it was handed. Those are two
    facts, and :func:`apply_judgement` may demote a judgement it considers
    inconsistent -- an ``accepted`` verdict paired with counts that do not
    support it becomes ``failed``. Gating on the judgement instead would let a
    problem be marked solved off a verdict the submission table had already
    refused to record, which is exactly the kind of claim the demotion exists to
    prevent. Reading the stored row makes the two impossible to disagree.

    The runtime and memory recorded on an accepted submission become the
    learner's best, via the progress service's "only improves" rule: a slower
    later attempt never overwrites a faster earlier one. A ``None`` measurement
    (a platform that could not measure memory) is passed through as ``None`` and
    leaves any existing best untouched rather than overwriting it with nothing.
    """
    if normalize_submission_status(submission.status) != SubmissionStatus.ACCEPTED.value:
        return None
    return progress_service.set_status(
        session,
        user_id,
        problem,
        status=progress_service.ProgressStatus.SOLVED.value,
        best_runtime_ms=submission.runtime_ms,
        best_memory_mb=submission.memory_mb,
    )


# ---------------------------------------------------------------------- listing


def _base_query(
    user_id: int,
    problem_id: int | None = None,
    status: str | None = None,
    language: str | None = None,
):
    """Build the one query shape every history listing shares.

    The ``user_id`` predicate is unconditional. A filter can only narrow the
    result further, so no combination of query parameters can widen it past the
    caller's own history.
    """
    filters = [Submission.user_id == user_id]
    if problem_id is not None:
        filters.append(Submission.problem_id == problem_id)
    if status:
        filters.append(Submission.status == status)
    if language:
        filters.append(Submission.language == language)
    return filters


def list_submissions(
    session: Session,
    user_id: int,
    problem_id: int | None = None,
    status: str | None = None,
    language: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> SubmissionListResponse:
    """One page of the learner's submission history, newest first.

    Pagination is ``page``/``page_size`` rather than limit/offset because a
    history is read as numbered pages: the client can show "page 2" and jump
    back, which an offset cannot express. A ``page`` past the end is an empty
    page with an accurate ``total``, not an error.
    """
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    filters = _base_query(user_id, problem_id, status, language)
    total = int(
        session.scalar(select(func.count()).select_from(Submission).where(*filters)) or 0
    )
    rows = session.scalars(
        select(Submission)
        .where(*filters)
        # Newest first, with the id as a tie-break so two submissions created in
        # the same clock tick still have a stable, total order.
        .order_by(Submission.submitted_at.desc(), Submission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return SubmissionListResponse(
        items=[_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "apply_judgement",
    "create_submission",
    "get_submission",
    "list_submissions",
    "record_accepted_progress",
    "record_submission_attempt",
    "to_detail_response",
]
