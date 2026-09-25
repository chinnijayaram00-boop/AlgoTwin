from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.problems import ProblemDetail, ProblemListResponse, ProblemSummary
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
    problem = get_problem_by_slug(db, slug)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return ProblemDetail.model_validate(problem)
