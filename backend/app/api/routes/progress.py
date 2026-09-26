"""Learner progress endpoints.

Every route on this router is authenticated with ``CurrentUser``, the same
``get_current_user`` guard the auth routes use. The learner's identity comes
only from the bearer token: there is no ``user_id`` parameter, query field, or
body field anywhere in this module, so a caller cannot address another
learner's progress by guessing an id.
"""

from database.models import Problem, ProgressStatus
from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.schemas.progress import (
    ProblemProgressListResponse,
    ProblemProgressResponse,
    ProgressSummaryResponse,
    ProgressUpdateRequest,
)
from backend.app.services import progress_service
from backend.app.services.problem_service import get_published_problem_by_id

router = APIRouter(prefix="/progress", tags=["progress"])


def _resolve_problem(db: Session, problem_id: int) -> Problem:
    """Resolve a published problem or fail with 404.

    Progress cannot be recorded against a problem that is not in the catalog,
    so an unknown or unpublished id is reported the same way: not found.
    """
    problem = get_published_problem_by_id(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return problem


def _conflict(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Progress for this problem already exists.",
    )


@router.get("/me", response_model=ProgressSummaryResponse)
def read_my_progress(db: DbSession, current_user: CurrentUser) -> ProgressSummaryResponse:
    """Overall progress for the authenticated learner.

    Counts against the published catalog, so a learner who has not started
    anything still gets real numbers instead of an empty object.
    """
    return progress_service.get_progress_summary(db, current_user.id)


@router.get("/problems", response_model=ProblemProgressListResponse)
def list_my_progress(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: ProgressStatus | None = Query(
        default=None,
        alias="status",
        description="Filter to one status: not_started, attempted, or solved.",
    ),
    difficulty: str | None = Query(default=None, max_length=20),
    topic: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProblemProgressListResponse:
    """Every published problem annotated with the authenticated learner's status.

    Problems the learner has never opened are included as ``not_started`` so the
    client can render a complete list from a single request. An unrecognised
    ``status`` is rejected with 422 rather than being coerced, because silently
    answering a different question than the one asked is worse than an error.
    """
    return progress_service.list_progress(
        db,
        current_user.id,
        status=status_filter.value if status_filter else None,
        difficulty=difficulty,
        topic=topic,
        limit=limit,
        offset=offset,
    )


@router.get("/problems/{problem_id}", response_model=ProblemProgressResponse)
def read_problem_progress(
    db: DbSession,
    current_user: CurrentUser,
    problem_id: int = Path(ge=1),
) -> ProblemProgressResponse:
    """The authenticated learner's record for one problem.

    Answers ``not_started`` when the learner has no record yet; only a problem
    outside the published catalog is a 404.
    """
    problem = _resolve_problem(db, problem_id)
    return progress_service.get_problem_progress(db, current_user.id, problem)


@router.put("/problems/{problem_id}", response_model=ProblemProgressResponse)
def update_problem_progress(
    payload: ProgressUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
    problem_id: int = Path(ge=1),
) -> ProblemProgressResponse:
    """Set the authenticated learner's status for one problem.

    Idempotent: the same status twice leaves one record, not two. The unique
    ``(user_id, problem_id)`` constraint is what makes that true even under
    concurrent requests. Omitting ``status`` only records measurements.
    """
    problem = _resolve_problem(db, problem_id)
    try:
        progress_service.set_status(
            db,
            current_user.id,
            problem,
            status=payload.status,
            best_runtime_ms=payload.best_runtime_ms,
            best_memory_mb=payload.best_memory_mb,
        )
    except progress_service.DuplicateProgressError as error:
        raise _conflict(error) from error
    return progress_service.get_problem_progress(db, current_user.id, problem)


@router.post("/problems/{problem_id}/attempt", response_model=ProblemProgressResponse)
def create_attempt(
    db: DbSession,
    current_user: CurrentUser,
    problem_id: int = Path(ge=1),
    payload: ProgressUpdateRequest | None = None,
) -> ProblemProgressResponse:
    """Record that the learner worked on a problem again.

    This is a progress marker, not a submission: nothing is compiled, run, or
    graded here. It increments the attempt count, stamps the last activity time,
    and moves a fresh problem to ``attempted``. A problem already marked
    ``solved`` stays solved, because re-reading a solution is not a regression.
    """
    problem = _resolve_problem(db, problem_id)
    metrics = payload or ProgressUpdateRequest()
    try:
        progress_service.record_attempt(
            db,
            current_user.id,
            problem,
            best_runtime_ms=metrics.best_runtime_ms,
            best_memory_mb=metrics.best_memory_mb,
        )
    except progress_service.DuplicateProgressError as error:
        raise _conflict(error) from error
    return progress_service.get_problem_progress(db, current_user.id, problem)
