"""Endpoints for running a learner's code.

Two routes, and the difference between them is the whole point of having a
"Run" and a "Submit":

* ``POST /problems/{problem_id}/run`` with no ``stdin`` runs the program against
  the problem's **visible** test cases and returns a verdict. It stores nothing --
  no submission row, no progress change, no attempt count. Pressing Run thirty
  times is not thirty attempts, and Run that silently counted them would make the
  progress numbers mean something other than what the progress panel says.
* the same route with a ``stdin`` runs the program once on the learner's own input
  and returns only what it printed. There is nothing to compare against, so there
  is no verdict and no pass count.

The hidden cases are never run here. They exist for the judged-submission path
(``POST /submissions``), which is where the graded verdict comes from; running
them for a debug endpoint would hand a learner the pass/fail vector for the
graded set.

Both routes are synchronous, which is a deliberate limit rather than an oversight.
The total work is bounded by ``MAX_JUDGE_WALL_CLOCK_MS`` and by the per-case wall
clock, and the route is declared with ``def`` rather than ``async def`` so FastAPI
runs it in the threadpool where it does not block the event loop. A deployment
that needs longer runs should move judging to a background worker, not raise the
budget.
"""

from database.models import Problem
from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import AppSettings, CurrentUser, DbSession
from backend.app.schemas.judge import (
    CodeRunRequest,
    ProblemRunResponse,
    RunLanguagesResponse,
)
from backend.app.services import judge_service
from backend.app.services.problem_service import get_published_problem_by_id

router = APIRouter(tags=["judge"])


def _resolve_problem(db: Session, problem_id: int) -> Problem:
    """A published problem, or the same 404 every other learner-scoped route gives."""
    problem = get_published_problem_by_id(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return problem


def _resolve_language(problem: Problem, payload: CodeRunRequest, settings):
    try:
        return judge_service.resolve_language(problem, payload.language, settings)
    except judge_service.UnsupportedLanguageError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@router.get("/judge/languages", response_model=RunLanguagesResponse)
def list_runnable_languages(settings: AppSettings) -> RunLanguagesResponse:
    """The languages this deployment can run, and whether execution is on at all.

    The editor reads this to decide which tabs to draw. Reporting a language the
    runner will refuse is what produced the Java tab that ended in a 422, so the
    list comes from the same registry the judge uses.
    """
    return RunLanguagesResponse(
        items=judge_service.describe_languages(settings),
        execution_enabled=settings.execution_enabled,
    )


@router.post("/problems/{problem_id}/run", response_model=ProblemRunResponse)
def run_against_problem(
    payload: CodeRunRequest,
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
    problem_id: int = Path(ge=1),
) -> ProblemRunResponse:
    """Run the authenticated learner's code against one problem.

    Nothing is stored. The learner's identity is taken from the token and used
    only to require a session: a run is a local debugging aid, and it must not
    create a submission, count an attempt, or touch another learner's state.

    The source is executed in a separate worker process with a wall-clock limit, a
    memory ceiling, and an output cap. It is never executed in the API process.
    """
    _ = current_user
    problem = _resolve_problem(db, problem_id)
    language = _resolve_language(problem, payload, settings)

    try:
        if payload.stdin is not None:
            return judge_service.run_adhoc_input(
                problem, language, payload.source_code, payload.stdin, settings
            )
        return judge_service.run_visible_cases(problem, language, payload.source_code, settings)
    except judge_service.ExecutionDisabledError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except judge_service.NoTestCasesError as error:
        # A problem with nothing to run is a catalog fault, not a learner fault,
        # and it must never be reported as a pass or a failure of their code.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
