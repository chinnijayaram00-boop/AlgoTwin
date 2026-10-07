"""Mock interview endpoints.

Every route on this router is authenticated with ``CurrentUser``, like the
submission routes, and the identity comes only from the bearer token: there is
no ``user_id`` parameter, query field, or body field anywhere in this module.

Three rules carry through every route:

* **Ownership is part of the lookup.** ``user_id`` is a WHERE clause in the
  service, not a check afterwards, so another learner's interview is reported as
  a 404 exactly like one that does not exist.
* **Nothing here is client-scored.** A create request names calibration and a
  question count; an answer names a language and source. Accepting, timing,
  scoring, selecting, and expiring all happen in the service against the server
  clock and the real judge. There is no endpoint that accepts a verdict, a
  remaining time, or a score.
* **The lifecycle and its errors are explicit.** The timer running out is a
  state a learner can observe; ``SessionExpiredError`` says so. A transition out
  of order is a 409 conflict, not a silent no-op.
"""

from fastapi import APIRouter, HTTPException, Path, Query, status

from backend.app.api.dependencies import AppSettings, CurrentUser, DbSession
from backend.app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewCreateRequest,
    InterviewListResponse,
    InterviewReportResponse,
    InterviewSessionResponse,
    InterviewStatusInput,
)
from backend.app.services import interview_service
from backend.app.services.judge_service import (
    ExecutionDisabledError,
    NoTestCasesError,
    UnsupportedLanguageError,
)

router = APIRouter(tags=["interviews"])

#: Route ordering is load-bearing on this router: ``/interviews/active`` must be
#: declared before ``/interviews/{interview_id}`` so "active" is matched as the
#: dedicated path and never parsed as a session id.
_ACTIVE = "active"


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.post("/interviews", response_model=InterviewSessionResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> InterviewSessionResponse:
    """Create a session with its questions selected deterministically.

    The body is optional beyond the defaults: ``{}`` creates a three-question,
    thirty-minute interview for a software engineering role. ``question_count``
    and ``duration_minutes`` are bounded by the model's limits, the filters only
    narrow the pick, and everything the service does not own is rejected by the
    request schema's ``extra="forbid"``.
    """
    try:
        interview = interview_service.create_interview(
            db,
            current_user.id,
            question_count=payload.question_count,
            duration_seconds=payload.duration_minutes * 60,
            role=payload.role,
            level=payload.level,
            difficulty=payload.difficulty,
            topic=payload.topic,
        )
    except interview_service.ActiveSessionError as error:
        raise _conflict(str(error)) from error
    except interview_service.NotEnoughProblemsError as error:
        raise _conflict(str(error)) from error
    return interview_service.to_session_response(interview)


@router.get("/interviews", response_model=InterviewListResponse)
def list_my_interviews(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: InterviewStatusInput | None = Query(
        default=None, alias="status", description="Filter to one lifecycle state."
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=interview_service.DEFAULT_PAGE_SIZE,
        ge=1,
        le=interview_service.MAX_PAGE_SIZE,
    ),
) -> InterviewListResponse:
    """The authenticated learner's interview history, newest first.

    An unrecognised ``status`` is a 422 from the ``Literal`` type rather than a
    silent empty page, because answering a different question than the one asked
    is worse than an error.
    """
    return interview_service.list_interviews(
        db,
        current_user.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get("/interviews/active", response_model=InterviewSessionResponse)
def read_my_active_interview(
    db: DbSession,
    current_user: CurrentUser,
) -> InterviewSessionResponse:
    """The learner's active interview, finalised if its clock ran out.

    404 means "no active session right now": either none was ever created, or
    the one that ran has moved to a terminal state (possibly, on this very
    read, because the timer ran out and this read finalised it).
    """
    interview = interview_service.get_active_interview(db, current_user.id)
    if interview is None:
        raise _not_found("No active interview.")
    return interview_service.to_session_response(interview)


@router.get("/interviews/{interview_id}", response_model=InterviewSessionResponse)
def read_my_interview(
    db: DbSession,
    current_user: CurrentUser,
    interview_id: int = Path(ge=1),
) -> InterviewSessionResponse:
    """One of the learner's interviews, finalising it if the clock ran out.

    A read after ``expires_at`` is the read that completes the session: the timer
    is a server-side timestamp, so seeing a finished session is a side effect of
    observing it, and the response honestly shows the completed state.
    """
    interview = interview_service.load_session(db, current_user.id, interview_id)
    if interview is None:
        raise _not_found("Interview not found.")
    return interview_service.to_session_response(interview)


@router.post("/interviews/{interview_id}/start", response_model=InterviewSessionResponse)
def start_my_interview(
    db: DbSession,
    current_user: CurrentUser,
    interview_id: int = Path(ge=1),
) -> InterviewSessionResponse:
    """Start the clock on a created interview.

    The response carries ``started_at``, ``expires_at``, and a server-computed
    ``remaining_seconds``. Starting an interview that is not ``created`` -- or
    is in a terminal state -- is a 409. Both the service and the timer decide
    against the server clock, never against a client's idea of the time.
    """
    try:
        interview = interview_service.start_interview(db, current_user.id, interview_id)
    except interview_service.SessionExpiredError as error:
        raise _conflict(str(error)) from error
    except interview_service.SessionStateError as error:
        raise _conflict(str(error)) from error
    if interview is None:
        raise _not_found("Interview not found.")
    return interview_service.to_session_response(interview)


@router.post(
    "/interviews/{interview_id}/questions/{position}/submit",
    response_model=InterviewSessionResponse,
)
def submit_my_answer(
    payload: InterviewAnswerRequest,
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
    interview_id: int = Path(ge=1),
    position: int = Path(ge=0),
) -> InterviewSessionResponse:
    """Judge the learner's answer to one recorded question.

    The payload names only ``language`` and ``source_code``; the problem is the
    one recorded for ``position``. The judge's verdict, pass counts, and
    runtime are written by the judge and appear read-only in the returned
    session. The code is stored before judging, exactly like a normal
    submission, so an answer survives even if the judge never runs.

    Errors are explicit: an unsupported language is a 422 before anything is
    stored; a submission after the clock ran out is a 409 saying so; a session
    that is not running rejects answers with a 409; execution switched off is a
    503.
    """
    try:
        interview, _ = interview_service.submit_answer(
            db,
            current_user.id,
            interview_id,
            position,
            payload.language,
            payload.source_code,
            settings,
        )
    except UnsupportedLanguageError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except interview_service.SessionExpiredError as error:
        raise _conflict(str(error)) from error
    except interview_service.SessionStateError as error:
        raise _conflict(str(error)) from error
    except ExecutionDisabledError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except NoTestCasesError as error:
        raise _conflict(str(error)) from error
    if interview is None:
        raise _not_found("Interview or question not found.")
    return interview_service.to_session_response(interview)


@router.post("/interviews/{interview_id}/finish", response_model=InterviewSessionResponse)
def finish_my_interview(
    db: DbSession,
    current_user: CurrentUser,
    interview_id: int = Path(ge=1),
) -> InterviewSessionResponse:
    """Finish a running interview and score what was answered.

    Finishing stamps the completion with the server time and computes the
    deterministic score from the stored question rows. A session whose timer
    already ran out raises the expired conflict, because the timer -- not this
    request -- ended it.
    """
    try:
        interview = interview_service.finish_interview(db, current_user.id, interview_id)
    except interview_service.SessionExpiredError as error:
        raise _conflict(str(error)) from error
    except interview_service.SessionStateError as error:
        raise _conflict(str(error)) from error
    if interview is None:
        raise _not_found("Interview not found.")
    return interview_service.to_session_response(interview)


@router.post("/interviews/{interview_id}/abandon", response_model=InterviewSessionResponse)
def abandon_my_interview(
    db: DbSession,
    current_user: CurrentUser,
    interview_id: int = Path(ge=1),
) -> InterviewSessionResponse:
    """Discard a created or running interview, leaving it unscored.

    An abandoned interview is ``abandoned`` with ``score=None``. A session the
    timer already ended raises the expired conflict: it was not abandoned, it
    finished.
    """
    try:
        interview = interview_service.abandon_interview(db, current_user.id, interview_id)
    except interview_service.SessionExpiredError as error:
        raise _conflict(str(error)) from error
    except interview_service.SessionStateError as error:
        raise _conflict(str(error)) from error
    if interview is None:
        raise _not_found("Interview not found.")
    return interview_service.to_session_response(interview)


@router.get("/interviews/{interview_id}/report", response_model=InterviewReportResponse)
def read_my_interview_report(
    db: DbSession,
    current_user: CurrentUser,
    interview_id: int = Path(ge=1),
) -> InterviewReportResponse:
    """The post-session report for a completed interview.

    The report is only available once the interview completed -- the timer ran
    out, the learner finished, or the last answer was submitted. A session that
    is still active (created or running) is a 409, and an abandoned session is
    a 409 too: there is nothing to report about a run the learner walked away
    from.
    """
    interview = interview_service.load_session(db, current_user.id, interview_id)
    if interview is None:
        raise _not_found("Interview not found.")
    if not interview.is_completed:
        raise _conflict(
            "This interview is not completed yet; finish it or wait for the timer "
            "before requesting a report."
        )
    return interview_service.to_report_response(interview)