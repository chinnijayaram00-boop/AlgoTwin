"""Learner submission endpoints.

Every route on this router is authenticated with ``CurrentUser``, the same
``get_current_user`` guard the auth and progress routes use. The learner's
identity comes only from the bearer token: there is no ``user_id`` parameter,
query field, or body field anywhere in this module, and
``SubmissionCreateRequest`` forbids extra fields outright, so a caller cannot
address another learner's submissions even by guessing an id or by sending one.

Submitting runs the learner's program through the judge and stores the real
verdict. The create request still accepts only ``problem_id``, ``language``, and
``source_code`` -- a caller can never name a status, a pass count, or a runtime;
those are written only by the judge. A submission that the judge could not run
records that fact as its verdict (a timeout, a crash, a failure); it is never
given a status the learner or the client chose.
"""

from database.models import Problem
from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import AppSettings, CurrentUser, DbSession
from backend.app.schemas.submissions import (
    SubmissionCreateRequest,
    SubmissionDetailResponse,
    SubmissionListResponse,
    SubmissionStatusInput,
    SupportedLanguage,
)
from backend.app.services import submission_service
from backend.app.services.judge_service import (
    ExecutionDisabledError,
    NoTestCasesError,
    UnsupportedLanguageError,
    judge_submission,
    resolve_language,
)
from backend.app.services.problem_service import get_published_problem_by_id

router = APIRouter(tags=["submissions"])

#: Path segments that used to be routes on this prefix and no longer are. They
#: are named here because the response they get depends on being matched before
#: ``/submissions/{submission_id}`` -- see :func:`retired_catalogue_route`.
RETIRED_CATALOGUE_PATHS = ("vocabulary", "languages")


def _resolve_problem(db: Session, problem_id: int) -> Problem:
    """Resolve a published problem or fail with 404.

    A submission has to point at something a learner could actually have been
    shown, so an unknown or unpublished id is reported the same way progress
    reports it: not found.
    """
    problem = get_published_problem_by_id(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return problem


@router.post(
    "/submissions",
    response_model=SubmissionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    payload: SubmissionCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
) -> SubmissionDetailResponse:
    """Judge the authenticated learner's program and store the real verdict.

    The order matters and is deliberate:

    1. resolve the language, so a language the deployment or the problem cannot
       run is rejected with a 422 *before* anything is stored -- the learner is
       not left with a row for code that was never judged;
    2. store the row ``queued`` and commit, so the code is durable even if the
       process dies mid-run;
    3. count one attempt (every submission is an attempt);
    4. run the judge over the problem's full case set, hidden included;
    5. store the verdict and its measurements;
    6. mark the problem solved only if the judge returned ``accepted``.

    The response carries the stored verdict, its pass count, runtime, peak
    memory, and a safe error message. It never carries a hidden case's input,
    expected output, or the program's output on a hidden case.
    """
    problem = _resolve_problem(db, payload.problem_id)
    try:
        language = resolve_language(problem, payload.language, settings)
    except UnsupportedLanguageError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    submission = submission_service.create_submission(
        db,
        current_user.id,
        problem,
        payload.language,
        payload.source_code,
    )
    submission_service.record_submission_attempt(db, current_user.id, problem)

    try:
        judgement = judge_submission(problem, language, payload.source_code, settings)
    except ExecutionDisabledError as error:
        # Execution was switched off between the language check and here, or the
        # judge raised it. This is not the learner's fault and not a 4xx: the
        # server simply cannot run the code. The stored row stays ``queued``,
        # which honestly means "stored, not judged".
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except NoTestCasesError as error:
        # A problem with nothing to judge against is a catalog fault, not a
        # learner fault. It is reported as a conflict rather than recorded as a
        # verdict, because recording "failed" here would blame the learner's
        # code for the platform's missing test data.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    submission = submission_service.apply_judgement(db, submission, judgement)
    submission_service.record_accepted_progress(db, current_user.id, problem, submission)
    return submission_service.to_detail_response(submission)


@router.get("/submissions", response_model=SubmissionListResponse)
def list_my_submissions(
    db: DbSession,
    current_user: CurrentUser,
    problem_id: int | None = Query(default=None, ge=1, description="Filter to one problem."),
    status_filter: SubmissionStatusInput | None = Query(
        default=None,
        alias="status",
        description="Filter to one status from the submission vocabulary.",
    ),
    language: SupportedLanguage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=submission_service.DEFAULT_PAGE_SIZE, ge=1, le=submission_service.MAX_PAGE_SIZE),
) -> SubmissionListResponse:
    """The authenticated learner's submission history, newest first.

    The filters are optional and only ever narrow the result. An unrecognised
    ``status`` or ``language`` is a 422 rather than a silent empty page,
    because quietly answering a different question than the one asked is worse
    than an error.
    """
    return submission_service.list_submissions(
        db,
        current_user.id,
        problem_id=problem_id,
        status=status_filter if status_filter else None,
        language=language,
        page=page,
        page_size=page_size,
    )


# Registered above `/submissions/{submission_id}` on purpose, and that ordering
# is the whole point of the two routes. The vocabulary and language catalogue
# were retired: the status and language vocabularies are published in the
# OpenAPI schema, and a learner cannot submit anything the schema does not
# already allow. But a bare path parameter matches any single segment, so with
# no route here `/submissions/vocabulary` would fall straight through to
# `{submission_id}`, where parsing "vocabulary" as an int fails and the caller
# gets a 422 telling them their id is not a number. That advice is wrong: the
# request never carried an id. The path simply does not exist, so the honest
# answer is 404, and answering it here -- before the parameterised route -- is
# the only way to say so. `include_in_schema=False` keeps the tombstones out of
# the published contract, since they are not part of it.
@router.get("/submissions/vocabulary", include_in_schema=False, response_model=None)
@router.get("/submissions/languages", include_in_schema=False, response_model=None)
def retired_catalogue_route(current_user: CurrentUser) -> None:
    """Answer a retired catalogue path with the 404 it is, never a 422.

    Still authenticated, like every other route on this router: an
    unauthenticated caller gets 401 and so learns nothing about which paths
    exist, which keeps the rule that nothing under this prefix answers without
    a token.
    """
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.get("/submissions/{submission_id}", response_model=SubmissionDetailResponse)
def read_my_submission(
    db: DbSession,
    current_user: CurrentUser,
    submission_id: int = Path(ge=1),
) -> SubmissionDetailResponse:
    """One of the authenticated learner's submissions, with its source.

    A submission belonging to another learner is reported as 404, not 403: the
    lookup is filtered by the owner, so the service cannot tell the difference
    between "not yours" and "does not exist", and the response must not either.
    """
    submission = submission_service.get_submission(db, current_user.id, submission_id)
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found."
        )
    return submission_service.to_detail_response(submission)


@router.get("/problems/{problem_id}/submissions", response_model=SubmissionListResponse)
def list_my_problem_submissions(
    db: DbSession,
    current_user: CurrentUser,
    problem_id: int = Path(ge=1),
    status_filter: SubmissionStatusInput | None = Query(default=None, alias="status"),
    language: SupportedLanguage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=submission_service.DEFAULT_PAGE_SIZE, ge=1, le=submission_service.MAX_PAGE_SIZE),
) -> SubmissionListResponse:
    """The authenticated learner's submissions for one problem.

    The problem must be in the published catalog, matching the progress routes,
    and the answer is always the caller's own rows for it.
    """
    _resolve_problem(db, problem_id)
    return submission_service.list_submissions(
        db,
        current_user.id,
        problem_id=problem_id,
        status=status_filter if status_filter else None,
        language=language,
        page=page,
        page_size=page_size,
    )
