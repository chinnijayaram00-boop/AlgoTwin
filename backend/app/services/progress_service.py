from datetime import datetime, timezone

from database.models import Progress
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_user_progress(session: Session, user_id: int) -> list[Progress]:
    return list(session.scalars(select(Progress).where(Progress.user_id == user_id).order_by(Progress.updated_at.desc())))


def mark_problem_started(session: Session, user_id: int, problem_id: int) -> Progress:
    progress = session.scalar(
        select(Progress).where(Progress.user_id == user_id, Progress.problem_id == problem_id)
    )
    if progress is None:
        progress = Progress(user_id=user_id, problem_id=problem_id, status="in_progress")
        session.add(progress)
    elif progress.status == "not_started":
        progress.status = "in_progress"
    session.commit()
    session.refresh(progress)
    return progress


def mark_problem_completed(session: Session, user_id: int, problem_id: int, best_time_ms: int | None = None) -> Progress:
    progress = mark_problem_started(session, user_id, problem_id)
    progress.status = "completed"
    progress.completed_at = datetime.now(timezone.utc)
    if best_time_ms is not None and (progress.best_time_ms is None or best_time_ms < progress.best_time_ms):
        progress.best_time_ms = best_time_ms
    session.commit()
    session.refresh(progress)
    return progress
