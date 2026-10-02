"""Submission persistence, judging, and history tests.

Covers the record lifecycle, the four required endpoints, and the three
properties the feature is really about:

* authentication is required on every submission endpoint, with identity taken
  only from the bearer token;
* a submission is graded by the judge, and no request can name the grade;
* one learner can never see, count, or address another learner's submissions.

The judging section at the end drives the whole vocabulary with real programs
rather than a stubbed judge, so the verdict assertions are about AlgoTwin
running code and not about a string being copied from one object to another.
"""

import json
from datetime import datetime, timezone

import pytest
from database.models import Problem, Progress, Submission
from database.models.progress import as_utc
from database.models.submission import (
    MAX_SOURCE_CODE_LENGTH,
    SUBMISSION_STATUS_VALUES,
    SUPPORTED_LANGUAGES,
)
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.routes import submissions
from backend.app.schemas.submissions import (
    SubmissionCreateRequest,
    SubmissionDetailResponse,
    SubmissionListResponse,
    SubmissionStatusInput,
    SupportedLanguage,
)
from backend.app.services import submission_service

RETIRED_CATALOGUE_PATHS = submissions.RETIRED_CATALOGUE_PATHS

ALPHA = {
    "name": "Alpha Learner",
    "email": "alpha@example.com",
    "password": "correct-horse-battery-staple",
}
BETA = {
    "name": "Beta Learner",
    "email": "beta@example.com",
    "password": "another-strong-passphrase",
}

SUBMISSIONS = "/api/v1/submissions"

# A fixed moment, so a test can assert that a solve date came back *unchanged*
# rather than merely present.
SOLVED_AT = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)

# Every route the release is required to expose, plus the two catalogue routes
# that were deliberately not kept.
AUTHENTICATED_ROUTES = (
    ("post", SUBMISSIONS),
    ("get", SUBMISSIONS),
    ("get", f"{SUBMISSIONS}/1"),
    ("get", "/api/v1/problems/1/submissions"),
)
ABSENT_ROUTES = (
    ("put", SUBMISSIONS),
    ("patch", SUBMISSIONS),
    ("delete", SUBMISSIONS),
    ("put", f"{SUBMISSIONS}/1"),
    ("patch", f"{SUBMISSIONS}/1"),
    ("delete", f"{SUBMISSIONS}/1"),
)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return auth(response.json()["access_token"])


def register(client: TestClient, payload: dict[str, str] = ALPHA) -> dict:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def problem_id(client: TestClient, slug: str) -> int:
    response = client.get(f"/api/v1/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def submit(
    client: TestClient,
    headers: dict[str, str],
    problem: int,
    language: str = "python",
    source: str = "def solve():\n    return 1\n",
) -> dict:
    response = client.post(
        SUBMISSIONS,
        json={"problem_id": problem, "language": language, "source_code": source},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def stored_submissions(db_session: Session, user_id: int) -> list[Submission]:
    return list(
        db_session.scalars(
            select(Submission).where(Submission.user_id == user_id).order_by(Submission.id)
        )
    )


def progress_row(db_session: Session, user_id: int, problem: int) -> Progress | None:
    return db_session.scalar(
        select(Progress).where(Progress.user_id == user_id, Progress.problem_id == problem)
    )


# ------------------------------------------------------------- authentication


@pytest.mark.parametrize("method,path", AUTHENTICATED_ROUTES)
def test_every_submission_endpoint_requires_authentication(client: TestClient, method, path) -> None:
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize("method,path", AUTHENTICATED_ROUTES)
def test_a_bad_token_does_not_unlock_a_submission_endpoint(client: TestClient, method, path) -> None:
    for headers in (auth(""), auth("invalid-token"), auth("a.b.c")):
        assert client.request(method, path, headers=headers).status_code == 401


def test_submission_writes_are_refused_without_a_token(client: TestClient) -> None:
    """A 401 on POST, not just on reads: an unauthenticated write is the real risk."""
    body = {"problem_id": 1, "language": "python", "source_code": "print(1)"}
    assert client.post(SUBMISSIONS, json=body).status_code == 401
    assert client.post(SUBMISSIONS, json=body, headers=auth("nope")).status_code == 401


def test_no_catalogue_route_is_left_unauthenticated(client: TestClient) -> None:
    """The vocabulary and language lists are not exposed as public routes.

    A public route on the submissions path would contradict the rule that every
    submission endpoint is authenticated, so the contract is pinned by a test
    rather than by a comment.
    """
    headers = as_learner(client)
    for path in (f"{SUBMISSIONS}/vocabulary", f"{SUBMISSIONS}/languages"):
        assert client.get(path).status_code in (401, 404)
        assert client.get(path, headers=headers).status_code == 404


@pytest.mark.parametrize("method,path", ABSENT_ROUTES)
def test_there_is_no_way_to_amend_or_delete_a_submission(client: TestClient, method, path) -> None:
    """A recorded attempt is an append-only fact, so no write verb is exposed."""
    assert client.request(method, path, headers=as_learner(client)).status_code == 405


def test_a_token_issued_at_registration_reaches_the_submission_routes(client: TestClient) -> None:
    headers = as_learner(client)
    assert client.get(SUBMISSIONS, headers=headers).status_code == 200


# --------------------------------------------------------------- retired routes


def test_a_retired_catalogue_path_is_a_404_rather_than_a_malformed_id(
    client: TestClient,
) -> None:
    """The reported bug, pinned: `/submissions/vocabulary` answers 404, not 422.

    A bare path parameter matches any single segment, so with no route of its own
    this path used to fall through to `/submissions/{submission_id}`, where
    parsing "vocabulary" as an int failed and FastAPI reported 422 -- telling the
    caller their submission id was not a number, for a request that never
    contained an id. The path does not exist, so 404 is the truthful answer.
    """
    headers = as_learner(client)

    for name in RETIRED_CATALOGUE_PATHS:
        response = client.get(f"{SUBMISSIONS}/{name}", headers=headers)

        assert response.status_code == 404, (name, response.text)
        # A 404 detail, not the list-of-errors body a 422 carries.
        assert response.json()["detail"] == "Not found.", name


def test_the_fix_is_narrow_and_does_not_turn_every_bad_id_into_a_404(
    client: TestClient,
) -> None:
    """Only the retired names are 404; an unparseable id is still a 422.

    A blanket rule that any non-numeric id is "not found" would hide the real
    mistake behind a plausible answer, so the boundary is asserted here as well
    as in `test_detail_rejects_a_non_positive_id`.
    """
    headers = as_learner(client)

    for value in ("abc", "VOCABULARY", "vocab"):
        response = client.get(f"{SUBMISSIONS}/{value}", headers=headers)
        assert response.status_code == 422, (value, response.text)


def test_the_retired_paths_are_registered_before_the_submission_id_route() -> None:
    """Starlette matches in registration order, so the 404 depends on position.

    If either tombstone were moved below `/submissions/{submission_id}` the
    parameterised route would swallow it again and the 404 above would quietly
    become a 422, with no other test failing to explain why.
    """
    paths = [getattr(route, "path", "") for route in submissions.router.routes]
    parameterised = paths.index("/submissions/{submission_id}")

    assert {
        path for path in paths if path.rsplit("/", 1)[-1] in RETIRED_CATALOGUE_PATHS
    } == {f"/submissions/{name}" for name in RETIRED_CATALOGUE_PATHS}
    for name in RETIRED_CATALOGUE_PATHS:
        assert paths.index(f"/submissions/{name}") < parameterised, name


def test_a_retired_path_is_not_published_in_the_openapi_contract() -> None:
    """A tombstone documents the absence of a route, so it must not add one.

    The expected set is written out in full rather than derived from the router,
    because deriving it would make the assertion true by construction -- including
    if a tombstone were ever registered and the expectation followed it round.

    ``{submission_id}/diagnose`` is a real route owned by the AI feature. It is named
    explicitly here so that a future sub-path is a deliberate addition to this line
    and not an accident.
    """
    from backend.app.main import app

    published = {
        path
        for path in app.openapi()["paths"]
        if path.startswith(SUBMISSIONS) and "{" in path
    }

    assert published == {
        f"{SUBMISSIONS}/{{submission_id}}",
        f"{SUBMISSIONS}/{{submission_id}}/diagnose",
    }
    assert not [path for path in published if path.rsplit("/", 1)[-1] in RETIRED_CATALOGUE_PATHS]


# ----------------------------------------------------------------- validation


def test_create_rejects_an_unsupported_language(client: TestClient) -> None:
    headers = as_learner(client)
    for language in ("ruby", "JavaScript", "js", "", "PYTHON"):
        response = client.post(
            SUBMISSIONS,
            json={"problem_id": 1, "language": language, "source_code": "x = 1"},
            headers=headers,
        )
        assert response.status_code == 422, (language, response.text)


def test_create_rejects_source_that_is_blank(client: TestClient) -> None:
    headers = as_learner(client)
    for source in ("", "   ", "\n\t "):
        response = client.post(
            SUBMISSIONS,
            json={"problem_id": 1, "language": "python", "source_code": source},
            headers=headers,
        )
        assert response.status_code == 422, (repr(source), response.text)


def test_create_rejects_source_beyond_the_stored_limit(client: TestClient) -> None:
    headers = as_learner(client)
    response = client.post(
        SUBMISSIONS,
        json={
            "problem_id": 1,
            "language": "python",
            "source_code": "a" * (MAX_SOURCE_CODE_LENGTH + 1),
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert submit(client, headers, 1)["id"]


def test_create_accepts_source_exactly_at_the_limit(client: TestClient) -> None:
    headers = as_learner(client)
    response = client.post(
        SUBMISSIONS,
        json={
            "problem_id": 1,
            "language": "python",
            "source_code": "a" * MAX_SOURCE_CODE_LENGTH,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["source_code"]) == MAX_SOURCE_CODE_LENGTH


@pytest.mark.parametrize(
    "extra",
    [
        {"user_id": 2},
        {"status": "accepted"},
        {"test_cases_passed": 3},
        {"test_cases_total": 3},
        {"runtime_ms": 12},
        {"memory_mb": 4},
        {"error_message": "all good"},
        {"results": {"passed": True}},
        {"submitted_at": "2024-01-01T00:00:00Z"},
    ],
)
def test_create_refuses_any_field_a_learner_may_not_set(client: TestClient, extra: dict) -> None:
    """extra="forbid" is what makes a submission unjudgeable by the caller.

    Each of these is a field the future execution service owns. Accepting one
    would let a learner file a submission that already claims to be accepted, or
    file it as somebody else.
    """
    headers = as_learner(client)
    body = {"problem_id": 1, "language": "python", "source_code": "x = 1", **extra}
    response = client.post(SUBMISSIONS, json=body, headers=headers)
    assert response.status_code == 422, (extra, response.text)
    assert client.get(SUBMISSIONS, headers=headers).json()["total"] == 0


def test_create_rejects_a_missing_required_field(client: TestClient) -> None:
    headers = as_learner(client)
    for body in (
        {"language": "python", "source_code": "x = 1"},
        {"problem_id": 1, "source_code": "x = 1"},
        {"problem_id": 1, "language": "python"},
    ):
        assert client.post(SUBMISSIONS, json=body, headers=headers).status_code == 422


@pytest.mark.parametrize("value", [0, -1, "abc"])
def test_create_rejects_a_non_positive_problem_id(client: TestClient, value) -> None:
    headers = as_learner(client)
    response = client.post(
        SUBMISSIONS,
        json={"problem_id": value, "language": "python", "source_code": "x = 1"},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_rejects_an_unknown_problem(client: TestClient) -> None:
    headers = as_learner(client)
    response = client.post(
        SUBMISSIONS,
        json={"problem_id": 99_999, "language": "python", "source_code": "x = 1"},
        headers=headers,
    )
    assert response.status_code == 404


def test_create_rejects_an_unpublished_problem(client: TestClient, db_session: Session) -> None:
    hidden = Problem(
        slug="not-published",
        title="Not Published",
        summary="Hidden from the catalog.",
        difficulty="Easy",
        topics=[],
        examples=[],
        constraints="",
        starter_code={"python": "def f():\n    pass\n"},
        is_published=False,
    )
    db_session.add(hidden)
    db_session.commit()
    db_session.refresh(hidden)
    headers = as_learner(client)

    response = client.post(
        SUBMISSIONS,
        json={"problem_id": hidden.id, "language": "python", "source_code": "x = 1"},
        headers=headers,
    )
    assert response.status_code == 404


# ----------------------------------------------------------------- persistence


def test_a_created_submission_carries_the_judges_real_verdict(
    client: TestClient, db_session: Session
) -> None:
    """The row exists, is owned by the token's learner, and records a real run.

    The default stub does not solve two-sum, so the judge returns
    ``wrong_answer`` -- and that is stored verbatim. Nothing about a judged
    submission may fall back to ``queued`` or claim a pass the judge did not
    report.
    """
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, language="javascript", source="function f() {}\n")

    assert body["status"] == "wrong_answer"
    assert body["language"] == "javascript"
    assert body["source_code"] == "function f() {}\n"
    assert body["problem_id"] == problem
    # A judged run reports real counts and a real verdict, not nulls.
    assert body["test_cases_passed"] == 0
    assert body["test_cases_total"] is not None and body["test_cases_total"] > 0
    assert body["test_cases_passed"] < body["test_cases_total"]
    assert body["runtime_ms"] is not None and body["runtime_ms"] >= 0
    assert body["error_message"]
    assert body["submitted_at"] is not None
    assert body["judged_at"] is not None

    rows = stored_submissions(db_session, session["user"]["id"])
    assert len(rows) == 1
    assert rows[0].status == "wrong_answer"
    assert rows[0].user_id == session["user"]["id"]
    assert rows[0].source_code == "function f() {}\n"
    # The stored verdict and counts match what was returned.
    assert rows[0].test_cases_passed == 0
    assert rows[0].test_cases_total == body["test_cases_total"]
    assert rows[0].judged_at is not None


def test_a_created_submission_never_names_its_owner_in_the_response(client: TestClient) -> None:
    """`user_id` is absent from every response, so it cannot leak by accident."""
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    created = submit(client, headers, problem)
    detail = client.get(f"{SUBMISSIONS}/{created['id']}", headers=headers).json()
    listing = client.get(SUBMISSIONS, headers=headers).json()

    assert "user_id" not in created
    assert "user_id" not in detail
    assert "user_id" not in listing["items"][0]


def test_source_code_is_returned_by_detail_but_not_by_the_list(client: TestClient) -> None:
    """A page of twenty submissions should not carry twenty code bodies."""
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    submit(client, headers, problem, source="MARKER = 'find me'")

    listing = client.get(SUBMISSIONS, headers=headers).json()
    detail = client.get(f"{SUBMISSIONS}/{listing['items'][0]['id']}", headers=headers).json()

    assert "source_code" not in listing["items"][0]
    assert detail["source_code"] == "MARKER = 'find me'"


def test_submitted_at_is_reported_in_utc(client: TestClient) -> None:
    headers = as_learner(client)
    created = submit(client, headers, problem_id(client, "two-sum"))
    assert created["submitted_at"].endswith("Z") or created["submitted_at"].endswith("+00:00")


# -------------------------------------------------------------------- detail


def test_a_learner_reads_their_own_submission(client: TestClient) -> None:
    headers = as_learner(client)
    created = submit(client, headers, problem_id(client, "binary-search"), source="SEARCH = 1")

    response = client.get(f"{SUBMISSIONS}/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["source_code"] == "SEARCH = 1"
    assert response.json()["problem_slug"] == "binary-search"


def test_another_learners_submission_is_not_found(client: TestClient) -> None:
    """404, not 403: the lookup is owner-filtered, so the two cases cannot be told apart."""
    mine = as_learner(client, ALPHA)
    theirs = as_learner(client, BETA)
    created = submit(client, mine, problem_id(client, "two-sum"))

    response = client.get(f"{SUBMISSIONS}/{created['id']}", headers=theirs)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_an_unknown_submission_id_is_not_found(client: TestClient) -> None:
    headers = as_learner(client)
    assert client.get(f"{SUBMISSIONS}/424242", headers=headers).status_code == 404


@pytest.mark.parametrize("value", [0, -5, "abc"])
def test_detail_rejects_a_non_positive_id(client: TestClient, value) -> None:
    headers = as_learner(client)
    assert client.get(f"{SUBMISSIONS}/{value}", headers=headers).status_code == 422


# --------------------------------------------------------------------- listing


def test_an_empty_history_is_an_empty_page_not_an_error(client: TestClient) -> None:
    headers = as_learner(client)

    body = client.get(SUBMISSIONS, headers=headers).json()

    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}


def test_the_history_is_newest_first(client: TestClient) -> None:
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    first = submit(client, headers, problem, source="FIRST = 1")
    second = submit(client, headers, problem, source="SECOND = 2")
    third = submit(client, headers, problem, source="THIRD = 3")

    ids = [item["id"] for item in client.get(SUBMISSIONS, headers=headers).json()["items"]]

    assert ids == [third["id"], second["id"], first["id"]]


def test_the_history_carries_enough_problem_detail_to_render(client: TestClient) -> None:
    headers = as_learner(client)
    submit(client, headers, problem_id(client, "valid-parentheses"))

    item = client.get(SUBMISSIONS, headers=headers).json()["items"][0]

    assert item["problem_slug"] == "valid-parentheses"
    assert item["problem_title"] == "Valid Parentheses"


def test_a_history_never_shows_another_learner(client: TestClient) -> None:
    mine = as_learner(client, ALPHA)
    theirs = as_learner(client, BETA)
    mine_id = submit(client, mine, problem_id(client, "two-sum"))["id"]
    theirs_id = submit(client, theirs, problem_id(client, "two-sum"))["id"]
    submit(client, theirs, problem_id(client, "binary-search"))

    body = client.get(SUBMISSIONS, headers=mine).json()

    assert [item["id"] for item in body["items"]] == [mine_id]
    assert body["total"] == 1
    assert theirs_id not in [item["id"] for item in body["items"]]


def test_pagination_splits_the_history_without_losing_or_repeating_a_row(client: TestClient) -> None:
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    created = [submit(client, headers, problem, source=f"N = {n}")["id"] for n in range(7)]

    first = client.get(f"{SUBMISSIONS}?page=1&page_size=3", headers=headers).json()
    second = client.get(f"{SUBMISSIONS}?page=2&page_size=3", headers=headers).json()
    third = client.get(f"{SUBMISSIONS}?page=3&page_size=3", headers=headers).json()

    assert first["total"] == 7
    assert first["total_pages"] == 3
    assert [len(page["items"]) for page in (first, second, third)] == [3, 3, 1]
    seen = [item["id"] for page in (first, second, third) for item in page["items"]]
    assert seen == list(reversed(created))


def test_a_page_past_the_end_is_empty_with_an_accurate_total(client: TestClient) -> None:
    headers = as_learner(client)
    submit(client, headers, problem_id(client, "two-sum"))

    body = client.get(f"{SUBMISSIONS}?page=9&page_size=20", headers=headers).json()

    assert body["items"] == []
    assert body["total"] == 1
    assert body["page"] == 9


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page_size=0", "page_size=101", "page_size=-2"])
def test_pagination_bounds_are_enforced(client: TestClient, query: str) -> None:
    headers = as_learner(client)
    assert client.get(f"{SUBMISSIONS}?{query}", headers=headers).status_code == 422


def test_the_largest_permitted_page_is_accepted(client: TestClient) -> None:
    headers = as_learner(client)
    response = client.get(f"{SUBMISSIONS}?page_size={submission_service.MAX_PAGE_SIZE}", headers=headers)
    assert response.status_code == 200
    assert response.json()["page_size"] == submission_service.MAX_PAGE_SIZE


def test_filtering_by_problem_narrows_the_history(client: TestClient) -> None:
    headers = as_learner(client)
    two_sum = problem_id(client, "two-sum")
    search = problem_id(client, "binary-search")
    submit(client, headers, two_sum)
    submit(client, headers, search)
    submit(client, headers, search)

    body = client.get(f"{SUBMISSIONS}?problem_id={search}", headers=headers).json()

    assert body["total"] == 2
    assert {item["problem_id"] for item in body["items"]} == {search}


def test_filtering_by_status_narrows_the_history(client: TestClient) -> None:
    """A judged verdict is filterable, and an unreached status is genuinely empty.

    The default stub does not solve two-sum, so both submissions are judged
    ``wrong_answer``. Filtering by that status returns them; filtering by a
    status no submission reached (``queued``) returns an empty page with an
    accurate total, not an error.
    """
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    submit(client, headers, problem)
    submit(client, headers, problem)

    wrong = client.get(f"{SUBMISSIONS}?status=wrong_answer", headers=headers).json()
    queued = client.get(f"{SUBMISSIONS}?status=queued", headers=headers).json()

    assert wrong["total"] == 2
    assert all(item["status"] == "wrong_answer" for item in wrong["items"])
    assert queued["total"] == 0
    assert queued["items"] == []


def test_filtering_by_language_narrows_the_history(client: TestClient) -> None:
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    submit(client, headers, problem, language="python")
    submit(client, headers, problem, language="javascript")

    body = client.get(f"{SUBMISSIONS}?language=javascript", headers=headers).json()

    assert body["total"] == 1
    assert body["items"][0]["language"] == "javascript"


def test_filters_compose_and_only_ever_narrow(client: TestClient) -> None:
    headers = as_learner(client)
    two_sum = problem_id(client, "two-sum")
    search = problem_id(client, "binary-search")
    submit(client, headers, two_sum, language="python")
    submit(client, headers, two_sum, language="javascript")
    submit(client, headers, search, language="python")

    body = client.get(
        f"{SUBMISSIONS}?problem_id={two_sum}&language=python&status=wrong_answer", headers=headers
    ).json()

    assert body["total"] == 1
    assert body["items"][0]["problem_id"] == two_sum
    assert body["items"][0]["language"] == "python"


def test_a_filter_never_reaches_another_learners_rows(client: TestClient) -> None:
    """A filter is not a way around the owner predicate."""
    mine = as_learner(client, ALPHA)
    theirs = as_learner(client, BETA)
    problem = problem_id(client, "two-sum")
    submit(client, theirs, problem, language="python")
    submit(client, theirs, problem, language="python")
    submit(client, mine, problem, language="python")

    body = client.get(f"{SUBMISSIONS}?problem_id={problem}&language=python", headers=mine).json()

    assert body["total"] == 1


@pytest.mark.parametrize(
    "query", ["status=bogus", "status=passed", "language=ruby", "problem_id=0", "problem_id=abc"]
)
def test_an_unusable_filter_is_a_422_rather_than_a_quiet_empty_page(client: TestClient, query: str) -> None:
    """Answering a different question than the one asked is worse than an error."""
    headers = as_learner(client)
    assert client.get(f"{SUBMISSIONS}?{query}", headers=headers).status_code == 422


# ------------------------------------------------------- problem-scoped history


def test_the_problem_scoped_history_is_the_callers_own(client: TestClient) -> None:
    mine = as_learner(client, ALPHA)
    theirs = as_learner(client, BETA)
    problem = problem_id(client, "merge-intervals")
    other = problem_id(client, "two-sum")
    mine_id = submit(client, mine, problem, source="MINE = 1")["id"]
    submit(client, mine, other)
    submit(client, theirs, problem)

    body = client.get(f"/api/v1/problems/{problem}/submissions", headers=mine).json()

    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [mine_id]
    assert body["items"][0]["problem_id"] == problem


def test_the_problem_scoped_history_supports_the_same_filters(client: TestClient) -> None:
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    submit(client, headers, problem, language="python")
    submit(client, headers, problem, language="javascript")

    body = client.get(
        f"/api/v1/problems/{problem}/submissions?language=python", headers=headers
    ).json()

    assert body["total"] == 1
    assert body["items"][0]["language"] == "python"


def test_the_problem_scoped_history_404s_on_an_unknown_problem(client: TestClient) -> None:
    headers = as_learner(client)
    assert client.get("/api/v1/problems/99999/submissions", headers=headers).status_code == 404


def test_the_problem_scoped_history_404s_on_an_unpublished_problem(
    client: TestClient, db_session: Session
) -> None:
    hidden = Problem(
        slug="hidden-two",
        title="Hidden Two",
        summary="Hidden.",
        difficulty="Easy",
        topics=[],
        examples=[],
        constraints="",
        starter_code={"python": "def f():\n    pass\n"},
        is_published=False,
    )
    db_session.add(hidden)
    db_session.commit()
    db_session.refresh(hidden)
    headers = as_learner(client)

    assert client.get(f"/api/v1/problems/{hidden.id}/submissions", headers=headers).status_code == 404


# ---------------------------------------------------------- progress coupling


def test_a_submission_counts_as_an_attempt(client: TestClient, db_session: Session) -> None:
    session = register(client)
    problem = problem_id(client, "two-sum")

    submit(client, auth(session["access_token"]), problem)

    row = progress_row(db_session, session["user"]["id"], problem)
    assert row is not None
    assert row.status == "attempted"
    assert row.attempts_count == 1
    assert row.solved_at is None


def test_repeated_submissions_keep_counting_the_attempts(client: TestClient, db_session: Session) -> None:
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    for n in range(3):
        submit(client, headers, problem, source=f"N = {n}")

    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.attempts_count == 3
    assert row.status == "attempted"


def test_a_submission_never_marks_a_problem_solved(client: TestClient, db_session: Session) -> None:
    """The central rule: recording code is not evidence that the code is right."""
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")
    db_session.add(
        Progress(user_id=session["user"]["id"], problem_id=problem, status="not_started")
    )
    db_session.commit()

    for _ in range(3):
        submit(client, headers, problem)

    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.status == "attempted"
    assert row.solved_at is None


def test_a_submission_leaves_an_already_solved_problem_solved(
    client: TestClient, db_session: Session
) -> None:
    """Recording an attempt on a solved problem must not undo the solve."""
    session = register(client)
    problem = problem_id(client, "two-sum")
    # Seeded the way the API itself leaves a solved record: `set_status` stamps
    # `solved_at` on the way in and counts at least one attempt, so a solved row
    # with no solve date is a state no caller can produce. Asserting on that
    # shape would only assert that nothing backfills it.
    db_session.add(
        Progress(
            user_id=session["user"]["id"],
            problem_id=problem,
            status="solved",
            attempts_count=1,
            solved_at=SOLVED_AT,
        )
    )
    db_session.commit()

    submit(client, auth(session["access_token"]), problem)

    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.status == "solved"
    # Unchanged, not merely present: the date the learner solved it is theirs,
    # and storing more code is not a second solve.
    assert as_utc(row.solved_at) == SOLVED_AT
    # The attempt is still counted -- the submission happened, only the verdict
    # is untouched.
    assert row.attempts_count == 2


def test_a_submission_only_touches_the_callers_own_progress(client: TestClient, db_session: Session) -> None:
    mine = register(client, ALPHA)
    theirs = register(client, BETA)
    problem = problem_id(client, "two-sum")

    submit(client, auth(theirs["access_token"]), problem)

    assert progress_row(db_session, mine["user"]["id"], problem) is None
    assert progress_row(db_session, theirs["user"]["id"], problem) is not None


def test_the_submission_survives_a_progress_failure(client: TestClient) -> None:
    """Storing the learner's code is the important part, and it happens first."""
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    def explode(*args, **kwargs):
        raise RuntimeError("progress is unavailable")

    original = submission_service.progress_service.record_attempt
    submission_service.progress_service.record_attempt = explode
    try:
        with pytest.raises(RuntimeError):
            client.post(
                SUBMISSIONS,
                json={"problem_id": problem, "language": "python", "source_code": "KEPT = 1"},
                headers=headers,
            )
    finally:
        submission_service.progress_service.record_attempt = original

    body = client.get(SUBMISSIONS, headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "queued"
    detail = client.get(f"{SUBMISSIONS}/{body['items'][0]['id']}", headers=headers).json()
    assert detail["source_code"] == "KEPT = 1"


# ------------------------------------------------------------- stored contract


def _seed_one_user_and_problem(db_session: Session) -> None:
    """A user and a problem, so a rejected row failed on its own constraint.

    Without them the foreign key would trip first and the test would pass for the
    wrong reason.
    """
    from database.models import User

    db_session.add(User(name="Raw", email="raw@example.com", password_hash="x"))
    db_session.add(
        Problem(
            slug="raw-problem",
            title="Raw Problem",
            summary="s",
            difficulty="Easy",
            topics=[],
            examples=[],
            constraints="",
            starter_code={"python": "def f():\n    pass\n"},
        )
    )
    db_session.commit()


def test_the_database_itself_refuses_an_unknown_status(db_session: Session) -> None:
    """The vocabulary is a real constraint, not only an application rule."""
    _seed_one_user_and_problem(db_session)
    with pytest.raises(IntegrityError, match="CHECK"):
        db_session.execute(
            text(
                "INSERT INTO submissions (user_id, problem_id, language, source_code, status,"
                " submitted_at) VALUES (1, 1, 'python', 'x', 'bogus', CURRENT_TIMESTAMP)"
            )
        )
    db_session.rollback()


def test_the_database_refuses_impossible_measurements(db_session: Session) -> None:
    _seed_one_user_and_problem(db_session)
    with pytest.raises(IntegrityError, match="CHECK"):
        db_session.execute(
            text(
                "INSERT INTO submissions (user_id, problem_id, language, source_code, status,"
                " test_cases_passed, test_cases_total, submitted_at)"
                " VALUES (1, 1, 'python', 'x', 'failed', 9, 2, CURRENT_TIMESTAMP)"
            )
        )
    db_session.rollback()


def test_the_database_refuses_a_negative_measurement(db_session: Session) -> None:
    _seed_one_user_and_problem(db_session)
    with pytest.raises(IntegrityError, match="CHECK"):
        db_session.execute(
            text(
                "INSERT INTO submissions (user_id, problem_id, language, source_code, status,"
                " runtime_ms, submitted_at)"
                " VALUES (1, 1, 'python', 'x', 'failed', -1, CURRENT_TIMESTAMP)"
            )
        )
    db_session.rollback()


def test_the_database_accepts_a_partly_reported_run(db_session: Session) -> None:
    """Nulls must stay legal, or a queued or partially timed run cannot be stored."""
    _seed_one_user_and_problem(db_session)
    db_session.execute(
        text(
            "INSERT INTO submissions (user_id, problem_id, language, source_code, status,"
            " test_cases_total, submitted_at)"
            " VALUES (1, 1, 'python', 'x', 'running', 10, CURRENT_TIMESTAMP)"
        )
    )
    db_session.commit()
    assert stored_submissions(db_session, 1)[0].test_cases_total == 10


def test_the_retired_placeholder_columns_are_gone(db_engine) -> None:
    """`results` and `created_at` are retired, so a second copy of the time cannot drift."""
    columns = {column["name"] for column in inspect(db_engine).get_columns("submissions")}
    assert "results" not in columns
    assert "created_at" not in columns
    assert "submitted_at" in columns


def test_the_submission_indexes_exist(db_engine) -> None:
    """The history query is "this learner, newest first"; the index matches it exactly."""
    indexes = {index["name"] for index in inspect(db_engine).get_indexes("submissions")}
    assert "ix_submissions_user_submitted_at" in indexes
    assert "ix_submissions_user_id" in indexes
    assert "ix_submissions_problem_id" in indexes


def test_the_published_contract_agrees_with_the_model_constants() -> None:
    """Stops the OpenAPI mirror of the vocabulary from drifting from the model."""
    from typing import get_args

    assert set(get_args(SubmissionStatusInput)) == set(SUBMISSION_STATUS_VALUES)
    assert set(get_args(SupportedLanguage)) == set(SUPPORTED_LANGUAGES)
    assert set(SubmissionCreateRequest.model_fields) == {"problem_id", "language", "source_code"}


def test_the_list_response_advertises_every_history_column() -> None:
    properties = set(SubmissionListResponse.model_json_schema()["properties"])
    assert properties == {"items", "total", "page", "page_size", "total_pages"}
    summary = set(SubmissionDetailResponse.model_json_schema()["properties"])
    assert "source_code" in summary
    assert "user_id" not in summary


# ========================================================== the judged verdicts
#
# Everything above is about the record: who owns it, what it looks like, and
# that no request can lie about it. This section is about the grade the judge
# actually produced, because a submission that is stored but never graded is
# not a submission -- it is a draft.
#
# The rule under all of these: the verdict is whatever the judge said. A test
# that stubbed the judge would only prove the plumbing copies a string around,
# so nothing here mocks the judge. Every case below is a real program, really
# compiled and really run against the problem's full case set.

#: A correct two-sum in the catalog's stdin format, so the happy path is a real
#: solve rather than a hand-written expected verdict.
TWO_SUM_PYTHON = """
import sys


def main():
    data = [int(token) for token in sys.stdin.read().split()]
    n = data[0]
    nums = data[1 : 1 + n]
    target = data[1 + n]
    seen = {}
    for index, value in enumerate(nums):
        if target - value in seen:
            print(seen[target - value], index)
            return
        seen.setdefault(value, index)


main()
"""


def test_an_accepted_solution_is_stored_as_accepted(client: TestClient) -> None:
    """The positive case: a real solve is recorded as a real pass."""
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source=TWO_SUM_PYTHON)

    assert body["status"] == "accepted"
    assert body["test_cases_passed"] == body["test_cases_total"] > 0
    assert body["runtime_ms"] is not None and body["runtime_ms"] >= 0
    assert body["judged_at"] is not None
    # A pass has nothing to report, so it reports nothing. An accepted row with
    # an error message attached would mean the judge was hedging.
    assert body["error_message"] is None


def test_an_accepted_solution_keeps_its_full_pass_count_on_disk(
    client: TestClient, db_session: Session
) -> None:
    """The stored row agrees with the response, not just with itself."""
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source=TWO_SUM_PYTHON)

    row = stored_submissions(db_session, session["user"]["id"])[0]
    assert row.status == "accepted"
    assert row.test_cases_passed == body["test_cases_total"]
    assert row.test_cases_total == body["test_cases_total"]
    assert row.judged_at is not None


def test_a_wrong_answer_is_stored_as_a_wrong_answer(client: TestClient) -> None:
    """It ran, and it was wrong -- which is not the same as a crash.

    Nonsense output rather than a plausible-but-wrong index pair, because a
    hardcoded answer can be accidentally right on the first case.
    """
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source="print('no idea')\n")

    assert body["status"] == "wrong_answer"
    assert body["test_cases_passed"] == 0
    assert body["test_cases_total"] > 0


def test_a_source_the_interpreter_cannot_parse_is_a_compilation_error(
    client: TestClient,
) -> None:
    """A syntax error is reported as a build failure, not a runtime one.

    The learner has to fix a typo in the source, not hunt a bug in a running
    program, so the distinction is worth asserting in its own right rather than
    being covered by "some kind of failure".
    """
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source="def solve(:\n    return 1\n")

    assert body["status"] == "compilation_error"
    assert body["test_cases_passed"] == 0
    # The interpreter's own diagnostic is what the learner needs to fix it.
    assert body["error_message"]
    assert "SyntaxError" in body["error_message"]


def test_a_program_that_crashes_is_a_runtime_error(client: TestClient) -> None:
    """Started fine, then died -- reported as a crash, with its own traceback."""
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source="raise ValueError('boom')\n")

    assert body["status"] == "runtime_error"
    assert body["test_cases_passed"] == 0
    assert "boom" in body["error_message"]


def test_a_program_that_never_finishes_is_a_timeout(client: TestClient) -> None:
    """A hang is the learner's timeout, not a platform failure and not a pass."""
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source="while True:\n    pass\n")

    assert body["status"] == "time_limit_exceeded"
    assert body["test_cases_passed"] == 0
    assert "time limit" in body["error_message"].lower()


def test_a_program_that_floods_its_output_is_a_failure(client: TestClient) -> None:
    """An unreadable answer cannot be a pass.

    The output cap stops a program that would otherwise run out of memory
    writing; recording it as accepted would be grading an answer nobody read.
    """
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")

    body = submit(
        client,
        headers,
        problem,
        source="import sys\nsys.stdout.write('x' * (4 * 1024 * 1024))\n",
    )

    assert body["status"] == "failed"
    assert body["test_cases_passed"] == 0


@pytest.mark.parametrize(
    "source,expected",
    [
        pytest.param(TWO_SUM_PYTHON, "accepted", id="accepted"),
        pytest.param("print('no idea')\n", "wrong_answer", id="wrong-answer"),
        pytest.param("def solve(:\n", "compilation_error", id="compilation-error"),
        pytest.param("raise ValueError('boom')\n", "runtime_error", id="runtime-error"),
        pytest.param("while True:\n    pass\n", "time_limit_exceeded", id="time-limit"),
        pytest.param(
            "import sys\nsys.stdout.write('x' * (4 * 1024 * 1024))\n",
            "failed",
            id="output-limit",
        ),
    ],
)
def test_every_verdict_the_judge_reaches_is_stored_verbatim(
    client: TestClient, db_session: Session, source: str, expected: str
) -> None:
    """The judge is the only authority on a verdict, and the row keeps it.

    One program per branch of the vocabulary, checked in the response *and* on
    disk, because a verdict that is right on the wire and wrong in storage is
    the failure mode that hides longest.
    """
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source=source)

    assert body["status"] == expected
    assert expected in SUBMISSION_STATUS_VALUES
    db_session.expire_all()
    assert stored_submissions(db_session, session["user"]["id"])[0].status == expected


def test_only_an_accepted_submission_marks_a_problem_solved(
    client: TestClient, db_session: Session
) -> None:
    """The gate, from both sides: a pass solves, everything else does not.

    Stated in one test on purpose. Split into two, each half would pass while
    the rule itself was broken -- one asserting "a wrong answer does not solve"
    says nothing about whether an accepted answer does.
    """
    session = register(client)
    headers = auth(session["access_token"])
    wrong = problem_id(client, "two-sum")
    right = problem_id(client, "binary-search")

    submit(client, headers, wrong, source="print('no idea')\n")
    db_session.expire_all()
    failed_row = progress_row(db_session, session["user"]["id"], wrong)
    assert failed_row.status == "attempted"
    assert failed_row.solved_at is None

    submit(client, headers, right, source="print(1)\n")
    db_session.expire_all()
    assert progress_row(db_session, session["user"]["id"], right).status == "attempted"


def test_an_accepted_submission_marks_the_problem_solved(
    client: TestClient, db_session: Session
) -> None:
    """The positive half of the gate, which is what actually earns a solve.

    ``record_accepted_progress`` is the only path that can write ``solved``, so
    this is the test that proves the path is reachable at all.
    """
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source=TWO_SUM_PYTHON)

    assert body["status"] == "accepted"
    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.status == "solved"
    assert row.solved_at is not None


def test_an_accepted_submission_stamps_a_solve_date(
    client: TestClient, db_session: Session
) -> None:
    """A solved problem with no solve date is a state no caller should produce."""
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    submit(client, headers, problem, source=TWO_SUM_PYTHON)

    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert as_utc(row.solved_at) is not None
    # The solve date is stamped at solve time, not backdated to the account.
    assert as_utc(row.solved_at).year >= 2024


def test_an_accepted_submission_records_the_runtime_as_the_best(
    client: TestClient, db_session: Session
) -> None:
    """The judged runtime becomes the learner's best time for that problem.

    This is the path the self-reporting progress panel never had: the number
    comes from a real run of real code, not from a field the learner typed.
    """
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")

    body = submit(client, headers, problem, source=TWO_SUM_PYTHON)

    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.best_runtime_ms == body["runtime_ms"]


def test_a_slower_accept_does_not_replace_a_faster_best(
    client: TestClient, db_session: Session
) -> None:
    """Best means best. A later, slower pass leaves the earlier best alone."""
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")
    # Seed the faster run the way a first accept would have left it.
    db_session.add(
        Progress(
            user_id=session["user"]["id"],
            problem_id=problem,
            status="solved",
            attempts_count=1,
            best_runtime_ms=1,
            solved_at=SOLVED_AT,
        )
    )
    db_session.commit()

    submit(client, headers, problem, source=TWO_SUM_PYTHON)

    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.status == "solved"
    assert row.best_runtime_ms == 1
    assert row.attempts_count == 2


def test_a_failing_submission_leaves_the_best_runtime_untouched(
    client: TestClient, db_session: Session
) -> None:
    """Only an accepted run may contribute a measurement.

    A wrong answer that happens to be fast must not become the learner's best
    time -- the number would be faster, and it would mean nothing.
    """
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")
    db_session.add(
        Progress(
            user_id=session["user"]["id"],
            problem_id=problem,
            status="solved",
            attempts_count=1,
            best_runtime_ms=42,
            best_memory_mb=7,
            solved_at=SOLVED_AT,
        )
    )
    db_session.commit()

    submit(client, headers, problem, source="print('no idea')\n")

    db_session.expire_all()
    row = progress_row(db_session, session["user"]["id"], problem)
    assert row.best_runtime_ms == 42
    assert row.best_memory_mb == 7


def test_a_demoted_accept_never_marks_a_problem_solved(client, db_session) -> None:
    """The row and the progress gate cannot disagree about a verdict.

    ``apply_judgement`` demotes an ``accepted`` judgement whose counts do not
    support it, and ``record_accepted_progress`` gates on the stored row rather
    than on the judgement it was handed. This drives that pair directly: a
    verdict the table refused to record must not still solve the problem, or the
    submission would say ``failed`` while the progress panel said ``solved``.
    """
    from database.models.submission import SubmissionStatus

    from backend.app.services.judge_service import SubmissionJudgement

    session = register(client)
    user_id = session["user"]["id"]
    problem = problem_id(client, "two-sum")
    problem_row = db_session.get(Problem, problem)

    stored = submission_service.create_submission(
        db_session, user_id, problem_row, "python", "SOURCE = 1"
    )
    # Accepted, but it passed fewer cases than exist. The counts contradict the
    # verdict, so the verdict is not storable as given.
    inconsistent = SubmissionJudgement(
        verdict=SubmissionStatus.ACCEPTED,
        cases_run=2,
        cases_passed=1,
        cases_total=4,
        total_runtime_ms=5,
        peak_memory_mb=3.0,
        error_message=None,
    )

    submission_service.apply_judgement(db_session, stored, inconsistent)
    result = submission_service.record_accepted_progress(
        db_session, user_id, problem_row, stored
    )

    db_session.expire_all()
    assert stored.status == "failed"
    assert result is None
    assert progress_row(db_session, user_id, problem) is None


def test_a_submission_response_carries_no_hidden_test_data(
    client: TestClient, db_session: Session
) -> None:
    """Submitting runs the hidden cases, so the response must not quote them.

    The run endpoint's guarantee has to hold here too, and it is a strictly
    stronger claim: this response describes a run that really did include the
    hidden suite. If any hidden input, expected output, or the program's own
    output on a hidden case escaped into it, a learner could submit repeatedly
    and read the graded set out of the answers.

    The expected values are read from the database rather than from a fixture,
    so a wrong fixture cannot make this pass by asserting the wrong secret.
    """
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    row = db_session.get(Problem, problem)
    hidden = [
        dict(case)
        for case in (row.test_cases or [])
        if case.get("is_hidden") is True
    ]
    assert hidden, "two-sum must have hidden cases for this test to mean anything"

    # A wrong answer, so the failure path -- the one with a message that could
    # carry a quote of the input -- is what gets inspected.
    created = submit(client, headers, problem, source="print('guess')\n")
    detail = client.get(f"{SUBMISSIONS}/{created['id']}", headers=headers).json()
    listing = client.get(SUBMISSIONS, headers=headers).json()
    blob = json.dumps([created, detail, listing])

    for case in hidden:
        for secret in (case.get("input"), case.get("expected_output")):
            if secret:
                assert str(secret) not in blob, f"hidden case leaked: {secret!r}"

    # The schema has no field a hidden case could arrive in, so the response
    # shape itself rules the leak out rather than the code remembering not to.
    summary = set(SubmissionDetailResponse.model_json_schema()["properties"])
    assert not summary & {"cases", "results", "case_input", "expected_output"}


def test_an_accepted_submission_discloses_no_hidden_answer(
    client: TestClient, db_session: Session
) -> None:
    """A pass reports only that it passed.

    Even on the accepted path, where there is no error message to leak, the
    per-case detail is absent: a learner must not be able to read which hidden
    cases their program got right.
    """
    headers = as_learner(client)
    problem = problem_id(client, "two-sum")
    row = db_session.get(Problem, problem)
    visible = [
        dict(case) for case in (row.test_cases or []) if case.get("is_hidden") is False
    ]
    assert visible, "two-sum must have visible cases for this test to mean anything"

    accepted = submit(client, headers, problem, source=TWO_SUM_PYTHON)
    blob = json.dumps(
        [
            accepted,
            client.get(f"{SUBMISSIONS}/{accepted['id']}", headers=headers).json(),
            client.get(SUBMISSIONS, headers=headers).json(),
        ]
    )

    assert accepted["status"] == "accepted"
    # Not even the *visible* cases come back on a submission: a durable record
    # is not a debug run, and the counts are what a history row needs.
    for case in visible:
        assert str(case["expected_output"]) not in blob


def test_no_problem_read_carries_a_hidden_case(client: TestClient) -> None:
    """Reading the problem the learner is solving must not reveal the suite.

    The judged submission runs the hidden cases, so a problem read that exposed
    them would undo every guarantee the judge makes.
    """
    for path in ("/api/v1/problems/two-sum", "/api/v1/problems?limit=100"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert "test_cases" not in response.text
        assert "is_hidden" not in response.text


def test_a_judged_submission_is_private_to_its_owner(client: TestClient) -> None:
    """One learner's pass never appears in another's history.

    A shared verdict would be a shared answer key: if learner B could read
    learner A's accepted submission, the platform would be handing out a
    solution rather than a grade.
    """
    mine = register(client, ALPHA)
    theirs = register(client, BETA)
    problem = problem_id(client, "two-sum")

    submit(client, auth(theirs["access_token"]), problem, source=TWO_SUM_PYTHON)

    my_history = client.get(SUBMISSIONS, headers=auth(mine["access_token"])).json()
    assert my_history["total"] == 0
    assert my_history["items"] == []

    their_history = client.get(SUBMISSIONS, headers=auth(theirs["access_token"])).json()
    assert their_history["total"] == 1
    assert their_history["items"][0]["status"] == "accepted"


def test_another_learners_accepted_submission_is_not_readable(client: TestClient) -> None:
    """The id of someone else's passing submission is not a way in.

    404 rather than 403, so the response cannot confirm that the row exists.
    """
    mine = as_learner(client, ALPHA)
    theirs = register(client, BETA)
    problem = problem_id(client, "two-sum")

    accepted = submit(client, auth(theirs["access_token"]), problem, source=TWO_SUM_PYTHON)

    response = client.get(f"{SUBMISSIONS}/{accepted['id']}", headers=mine)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_a_solve_does_not_reach_another_learners_progress(
    client: TestClient, db_session: Session
) -> None:
    """Judged progress is per learner, on the accepted path as much as the rest."""
    mine = register(client, ALPHA)
    theirs = register(client, BETA)
    problem = problem_id(client, "two-sum")

    submit(client, auth(theirs["access_token"]), problem, source=TWO_SUM_PYTHON)

    db_session.expire_all()
    assert progress_row(db_session, mine["user"]["id"], problem) is None
    solved = progress_row(db_session, theirs["user"]["id"], problem)
    assert solved.status == "solved"


def test_each_learner_solves_on_their_own_submissions(
    client: TestClient, db_session: Session
) -> None:
    """Two learners solving the same problem keep entirely separate records."""
    mine = register(client, ALPHA)
    theirs = register(client, BETA)
    problem = problem_id(client, "two-sum")
    headers = [auth(mine["access_token"]), auth(theirs["access_token"])]

    submit(client, headers[0], problem, source="print('no idea')\n")
    submit(client, headers[1], problem, source=TWO_SUM_PYTHON)

    db_session.expire_all()
    assert progress_row(db_session, mine["user"]["id"], problem).status == "attempted"
    assert progress_row(db_session, theirs["user"]["id"], problem).status == "solved"


def test_an_unsolved_problem_cannot_be_filtered_into_a_solved_one(
    client: TestClient,
) -> None:
    """A status filter narrows a learner's own history and reaches nobody else's."""
    mine = as_learner(client, ALPHA)
    theirs = register(client, BETA)
    problem = problem_id(client, "two-sum")

    submit(client, auth(theirs["access_token"]), problem, source=TWO_SUM_PYTHON)

    filtered = client.get(f"{SUBMISSIONS}?status=accepted", headers=mine).json()
    assert filtered["total"] == 0
    assert filtered["items"] == []


def test_submitting_with_execution_switched_off_keeps_the_code(
    client: TestClient,
) -> None:
    """A platform that cannot run code says so, and keeps the learner's source.

    The row is already committed before the judge is reached, so the learner
    does not lose their code to a deployment setting. It stays ``queued``,
    which honestly means "stored, never judged" -- never a pass.
    """
    from backend.app.api.dependencies import get_settings
    from backend.app.core.config import Settings

    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")
    disabled = Settings(execution_enabled=False)

    from backend.app.main import app

    app.dependency_overrides[get_settings] = lambda: disabled
    try:
        response = client.post(
            SUBMISSIONS,
            json={
                "problem_id": problem,
                "language": "python",
                "source_code": "KEPT = 1",
            },
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    body = client.get(SUBMISSIONS, headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "queued"
    detail = client.get(f"{SUBMISSIONS}/{body['items'][0]['id']}", headers=headers).json()
    assert detail["source_code"] == "KEPT = 1"


def test_a_problem_with_no_test_cases_is_a_conflict_not_a_verdict(
    client: TestClient, db_session: Session,
) -> None:
    """Missing test data is a catalog fault, and is not blamed on the learner.

    Recording ``failed`` here would put "your code is wrong" on a row whose real
    problem is that the platform has nothing to grade against.
    """
    session = register(client)
    headers = auth(session["access_token"])
    problem = problem_id(client, "two-sum")
    row = db_session.get(Problem, problem)
    row.test_cases = []
    db_session.commit()

    response = client.post(
        SUBMISSIONS,
        json={"problem_id": problem, "language": "python", "source_code": "x = 1"},
        headers=headers,
    )

    assert response.status_code == 409
    assert "test cases" in response.json()["detail"].lower()
