from database.models import Problem
from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session

from backend.app.schemas.problems import DashboardSummary


def list_problems(
    session: Session,
    difficulty: str | None = None,
    topic: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Problem], int]:
    filters = [Problem.is_published.is_(True)]
    if difficulty:
        filters.append(Problem.difficulty == difficulty)
    if topic:
        filters.append(cast(Problem.topics, Text).ilike(f"%{topic}%"))

    total = session.scalar(select(func.count()).select_from(Problem).where(*filters)) or 0
    problems = session.scalars(
        select(Problem).where(*filters).order_by(Problem.difficulty, Problem.title).offset(offset).limit(limit)
    ).all()
    return list(problems), total


def get_problem_by_slug(session: Session, slug: str) -> Problem | None:
    return session.scalar(select(Problem).where(Problem.slug == slug, Problem.is_published.is_(True)))


def get_published_problem_by_id(session: Session, problem_id: int) -> Problem | None:
    """Fetch a published problem by primary key.

    Progress mutations address problems by id, so the id path needs the same
    published-only visibility rule the slug path already has.
    """
    return session.scalar(
        select(Problem).where(Problem.id == problem_id, Problem.is_published.is_(True))
    )


def get_dashboard_summary(session: Session) -> DashboardSummary:
    difficulty_rows = session.execute(
        select(Problem.difficulty, func.count(Problem.id))
        .where(Problem.is_published.is_(True))
        .group_by(Problem.difficulty)
        .order_by(Problem.difficulty)
    ).all()
    by_difficulty = {difficulty: int(count) for difficulty, count in difficulty_rows}
    return DashboardSummary(total_problems=sum(by_difficulty.values()), by_difficulty=by_difficulty)
