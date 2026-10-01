from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.problems import (
    ProblemDetail,
    ProblemExample,
    ProblemListResponse,
    ProblemSummary,
)
from backend.app.services.problem_service import get_problem_by_slug, list_problems

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("", response_model=ProblemListResponse)
def get_problems(
    difficulty: str | None = Query(default=None, max_length=20),
    topic: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProblemListResponse:
    problems, total = list_problems(db, difficulty=difficulty, topic=topic, limit=limit, offset=offset)
    return ProblemListResponse(
        items=[ProblemSummary.model_validate(problem) for problem in problems],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{slug}", response_model=ProblemDetail)
def get_problem(slug: str, db: Session = Depends(get_db)) -> ProblemDetail:
    """One problem, for the workspace.

    The projection is written out rather than validated straight off the ORM row,
    for two reasons. It keeps ``test_cases`` and ``reference_solutions`` out by
    omission -- a hidden case's input must not be reachable from a public read,
    and the surest way to guarantee that is for the response shape to have no
    field it could arrive in. And it lets the limits be reported as the *clamped*
    values the judge will actually apply, so the number on screen is the number
    the run is held to.
    """
    problem = get_problem_by_slug(db, slug)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return ProblemDetail(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        summary=problem.summary,
        difficulty=problem.difficulty,
        topics=list(problem.topics or []),
        examples=[ProblemExample.model_validate(example) for example in (problem.examples or [])],
        constraints=problem.constraints,
        starter_code=dict(problem.starter_code or {}),
        supported_languages=list(problem.supported_languages or []),
        time_limit_ms=problem.effective_time_limit_ms,
        memory_limit_mb=problem.effective_memory_limit_mb,
        description=problem.description,
        input_format=problem.input_format,
        output_format=problem.output_format,
        expected_time_complexity=problem.expected_time_complexity,
        expected_space_complexity=problem.expected_space_complexity,
    )
