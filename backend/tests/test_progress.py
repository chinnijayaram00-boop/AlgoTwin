"""Learner progress tracking tests.

Covers the record lifecycle, the summary aggregate, and -- most importantly --
that progress belongs to exactly one learner: no request can read or write
another learner's rows, and identity comes only from the bearer token.
"""

from datetime import date, datetime, timezone

import pytest
from database.models import Problem, Progress, User
from database.seed import seed_demo_data
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.schemas.progress import MAX_MEMORY_MB, MAX_RUNTIME_MS
from backend.app.services.progress_service import current_streak_days, set_status

ALPHA = {"name": "Alpha Learner", "email": "alpha@example.com", "password": "correct-horse-battery-staple"}
BETA = {"name": "Beta Learner", "email": "beta@example.com", "password": "another-strong-passphrase"}
GAMMA = {"name": "Gamma Learner", "email": "gamma@example.com", "password": "third-strong-passphrase"}

SUMMARY = "/api/v1/progress/me"
PROBLEMS = "/api/v1/progress/problems"
PROTECTED_ENDPOINTS = ("get", SUMMARY), ("get", PROBLEMS), ("get", f"{PROBLEMS}/1")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, payload: dict[str, str] = ALPHA) -> dict:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    session = register(client, payload)
    return auth(session["access_token"])


def register_session(client: TestClient, payload: dict[str, str] = ALPHA) -> dict:
    return register(client, payload)


def problem_id(client: TestClient, slug: str) -> int:
    response = client.get(f"/api/v1/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def rows_for(user_id: int, db_session: Session) -> list[Progress]:
    return list(db_session.scalars(select(Progress).where(Progress.user_id == user_id)))


# ------------------------------------------------------------ authentication


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_every_progress_endpoint_requires_authentication(client: TestClient, method, path) -> None:
    assert client.request(method, path).status_code == 401


def test_progress_rejects_a_missing_or_invalid_token(client: TestClient) -> None:
    for headers in ({}, auth(""), auth("invalid-token"), auth("a.b.c")):
        assert client.get(SUMMARY, headers=headers).status_code == 401
        assert client.get(PROBLEMS, headers=headers).status_code == 401
        assert client.put(f"{PROBLEMS}/1", json={"status": "solved"}, headers=headers).status_code == 401
        assert client.post(f"{PROBLEMS}/1/attempt", headers=headers).status_code == 401


def test_authenticated_learner_reaches_progress_immediately_after_registration(client: TestClient) -> None:
    """A token issued by /auth/register is accepted by the progress guard."""
    session = register(client)

    response = client.get(SUMMARY, headers=auth(session["access_token"]))

    assert response.status_code == 200
    assert response.json()["total_problems"] == 4


def test_progress_reports_missing_jwt_configuration_as_unavailable(db_engine) -> None:
    """A present-but-unverifiable credential is a 503, never a bypass."""
    from backend.app.core.config import Settings, get_settings
    from backend.app.db.session import get_db
    from backend.app.main import app

    with Session(db_engine) as session:
        seed_demo_data(session)

    def override_get_db():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(jwt_secret_key=None)
    try:
        client = TestClient(app)
        assert client.get(SUMMARY, headers=auth("some-token")).status_code == 503
        assert client.get(SUMMARY).status_code == 401
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------ summary


def test_summary_of_a_fresh_learner_is_all_zero(client: TestClient) -> None:
    headers = as_learner(client)

    response = client.get(SUMMARY, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_problems"] == 4
    assert payload["attempted"] == 0
    assert payload["solved"] == 0
    assert payload["not_started"] == 4
    assert payload["completion_percentage"] == 0.0
    assert payload["current_streak_days"] == 0
    assert payload["total_by_difficulty"] == {"Easy": 3, "Medium": 1}
    assert payload["solved_by_difficulty"] == {}


def test_summary_counts_track_each_recorded_state(client: TestClient) -> None:
    headers = as_learner(client)
    two_sum = problem_id(client, "two-sum")
    brackets = problem_id(client, "valid-parentheses")
    intervals = problem_id(client, "merge-intervals")

    assert client.put(f"{PROBLEMS}/{two_sum}", json={"status": "solved"}, headers=headers).status_code == 200
    assert client.put(f"{PROBLEMS}/{brackets}", json={"status": "solved"}, headers=headers).status_code == 200
    assert client.put(f"{PROBLEMS}/{intervals}", json={"status": "attempted"}, headers=headers).status_code == 200

    payload = client.get(SUMMARY, headers=headers).json()

    assert payload["solved"] == 2
    assert payload["attempted"] == 1
    assert payload["not_started"] == 1
    assert payload["completion_percentage"] == 50.0
    assert payload["total_problems"] == 4
    assert payload["solved_by_difficulty"] == {"Easy": 2}
    assert payload["total_by_difficulty"] == {"Easy": 3, "Medium": 1}


def test_summary_breaks_progress_down_by_topic(client: TestClient) -> None:
    headers = as_learner(client)
    two_sum = problem_id(client, "two-sum")

    client.put(f"{PROBLEMS}/{two_sum}", json={"status": "solved"}, headers=headers)

    payload = client.get(SUMMARY, headers=headers).json()

    # "Arrays" is shared by three seeded problems, "Hash Maps" by one.
    assert payload["total_by_topic"]["Arrays"] == 3
    assert payload["total_by_topic"]["Hash Maps"] == 1
    assert payload["solved_by_topic"] == {"Arrays": 1, "Hash Maps": 1}


def test_summary_of_an_empty_catalog_is_all_zero(client: TestClient, db_session: Session) -> None:
    headers = as_learner(client)
    for problem in db_session.scalars(select(Problem)):
        problem.is_published = False
    db_session.commit()

    payload = client.get(SUMMARY, headers=headers).json()

    assert payload == {
        "total_problems": 0,
        "attempted": 0,
        "solved": 0,
        "not_started": 0,
        "completion_percentage": 0.0,
        "current_streak_days": 0,
        "solved_by_difficulty": {},
        "total_by_difficulty": {},
        "solved_by_topic": {},
        "total_by_topic": {},
    }


# ------------------------------------------------------------------ creation


def test_reading_progress_for_a_problem_starts_as_not_started(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.get(f"{PROBLEMS}/{target}", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["problem_id"] == target
    assert payload["slug"] == "two-sum"
    assert payload["status"] == "not_started"
    assert payload["attempts_count"] == 0
    assert payload["last_attempted_at"] is None
    assert payload["solved_at"] is None


def test_reading_progress_does_not_create_a_record(client: TestClient, db_session: Session) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    client.get(f"{PROBLEMS}/{target}", headers=headers)
    client.get(SUMMARY, headers=headers)

    user = db_session.scalar(select(User).where(User.email == ALPHA["email"]))
    assert rows_for(user.id, db_session) == []


def test_updating_status_creates_the_record(client: TestClient, db_session: Session) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.put(f"{PROBLEMS}/{target}", json={"status": "attempted"}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "attempted"
    assert payload["attempts_count"] == 1
    assert payload["last_attempted_at"] is not None
    assert payload["solved_at"] is None
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None

    user = db_session.scalar(select(User).where(User.email == ALPHA["email"]))
    stored = rows_for(user.id, db_session)
    assert len(stored) == 1
    assert stored[0].problem_id == target
    assert stored[0].status == "attempted"


def test_marking_solved_records_the_solve_time(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["solved_at"] is not None
    assert payload["last_attempted_at"] is not None
    assert payload["attempts_count"] == 1


def test_attempt_endpoint_counts_each_attempt(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    first = client.post(f"{PROBLEMS}/{target}/attempt", headers=headers)
    second = client.post(f"{PROBLEMS}/{target}/attempt", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "attempted"
    assert first.json()["attempts_count"] == 1
    assert second.json()["attempts_count"] == 2
    assert second.json()["solved_at"] is None


def test_attempting_a_solved_problem_does_not_regress_it(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    solved = client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=headers).json()

    response = client.post(f"{PROBLEMS}/{target}/attempt", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["solved_at"] == solved["solved_at"]
    assert payload["attempts_count"] == 2


def test_repeated_upsert_keeps_exactly_one_record(client: TestClient, db_session: Session) -> None:
    """Idempotency rests on the unique constraint, not on luck."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    for _ in range(4):
        assert client.put(f"{PROBLEMS}/{target}", json={"status": "attempted"}, headers=headers).status_code == 200

    user = db_session.scalar(select(User).where(User.email == ALPHA["email"]))
    assert db_session.scalar(
        select(func.count()).select_from(Progress).where(Progress.user_id == user.id, Progress.problem_id == target)
    ) == 1


def test_database_rejects_a_duplicate_user_problem_pair(client: TestClient, db_session: Session) -> None:
    user = User(name="Direct", email="direct@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    target = problem_id(client, "two-sum")

    db_session.add(Progress(user_id=user.id, problem_id=target, status="attempted"))
    db_session.commit()
    db_session.add(Progress(user_id=user.id, problem_id=target, status="solved"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_reset_to_not_started_clears_the_recorded_trail(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    client.put(
        f"{PROBLEMS}/{target}",
        json={"status": "solved", "best_runtime_ms": 120, "best_memory_mb": 8},
        headers=headers,
    )

    response = client.put(f"{PROBLEMS}/{target}", json={"status": "not_started"}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_started"
    assert payload["attempts_count"] == 0
    assert payload["last_attempted_at"] is None
    assert payload["solved_at"] is None
    assert payload["best_runtime_ms"] is None
    assert payload["best_memory_mb"] is None
    assert client.get(SUMMARY, headers=headers).json()["solved"] == 0


def test_downgrading_a_self_reported_solve_clears_the_solve_time(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=headers)

    response = client.put(f"{PROBLEMS}/{target}", json={"status": "attempted"}, headers=headers)

    assert response.json()["status"] == "attempted"
    assert response.json()["solved_at"] is None


# ----------------------------------------------------------------- metrics


def test_measurements_are_recorded_and_only_improve(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    first = client.put(
        f"{PROBLEMS}/{target}",
        json={"status": "solved", "best_runtime_ms": 240, "best_memory_mb": 32},
        headers=headers,
    )
    slower = client.put(
        f"{PROBLEMS}/{target}",
        json={"best_runtime_ms": 900, "best_memory_mb": 64},
        headers=headers,
    )
    faster = client.put(f"{PROBLEMS}/{target}", json={"best_runtime_ms": 120}, headers=headers)

    assert first.json()["best_runtime_ms"] == 240
    assert slower.json()["best_runtime_ms"] == 240, "a slower run must not replace the best"
    assert slower.json()["best_memory_mb"] == 32
    assert faster.json()["best_runtime_ms"] == 120
    assert faster.json()["status"] == "solved", "a measurement must not change the status"


# -------------------------------------------------------------------- list


def test_list_reports_every_problem_with_its_status(client: TestClient) -> None:
    headers = as_learner(client)
    solved_id = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{solved_id}", json={"status": "solved"}, headers=headers)

    response = client.get(PROBLEMS, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert {item["status"] for item in payload["items"]} == {"not_started", "solved"}


def test_list_filters_by_status_difficulty_and_topic(client: TestClient) -> None:
    headers = as_learner(client)
    solved_id = problem_id(client, "two-sum")
    intervals = problem_id(client, "merge-intervals")
    client.put(f"{PROBLEMS}/{solved_id}", json={"status": "solved"}, headers=headers)
    client.put(f"{PROBLEMS}/{intervals}", json={"status": "attempted"}, headers=headers)

    solved = client.get(PROBLEMS, params={"status": "solved"}, headers=headers).json()
    attempted = client.get(PROBLEMS, params={"status": "attempted"}, headers=headers).json()
    untouched = client.get(PROBLEMS, params={"status": "not_started"}, headers=headers).json()
    easy = client.get(PROBLEMS, params={"difficulty": "Easy"}, headers=headers).json()
    topic = client.get(PROBLEMS, params={"topic": "Intervals"}, headers=headers).json()

    assert [item["slug"] for item in solved["items"]] == ["two-sum"]
    assert [item["slug"] for item in attempted["items"]] == ["merge-intervals"]
    assert {item["slug"] for item in untouched["items"]} == {"valid-parentheses", "binary-search"}
    assert easy["total"] == 3
    assert [item["slug"] for item in topic["items"]] == ["merge-intervals"]


def test_list_paginates(client: TestClient) -> None:
    headers = as_learner(client)

    first = client.get(PROBLEMS, params={"limit": 2, "offset": 0}, headers=headers).json()
    second = client.get(PROBLEMS, params={"limit": 2, "offset": 2}, headers=headers).json()

    assert first["total"] == second["total"] == 4
    assert len(first["items"]) == len(second["items"]) == 2
    assert {item["problem_id"] for item in first["items"]}.isdisjoint(
        {item["problem_id"] for item in second["items"]}
    )


def test_list_omits_unpublished_problems(client: TestClient, db_session: Session) -> None:
    headers = as_learner(client)
    hidden = db_session.scalar(select(Problem).where(Problem.slug == "binary-search"))
    hidden.is_published = False
    db_session.commit()

    payload = client.get(PROBLEMS, headers=headers).json()

    assert "binary-search" not in {item["slug"] for item in payload["items"]}
    assert client.get(f"{PROBLEMS}/{hidden.id}", headers=headers).status_code == 404


# ------------------------------------------------------------- user isolation


def test_a_learner_never_sees_another_learners_records(client: TestClient) -> None:
    alpha = as_learner(client, ALPHA)
    beta = as_learner(client, BETA)
    target = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=alpha)

    beta_view = client.get(f"{PROBLEMS}/{target}", headers=beta).json()
    beta_list = client.get(PROBLEMS, headers=beta).json()
    beta_summary = client.get(SUMMARY, headers=beta).json()

    assert beta_view["status"] == "not_started"
    assert beta_view["solved_at"] is None
    assert {item["status"] for item in beta_list["items"]} == {"not_started"}
    assert beta_summary["solved"] == 0
    assert beta_summary["not_started"] == 4


def test_a_learner_cannot_change_another_learners_progress(client: TestClient) -> None:
    alpha = as_learner(client, ALPHA)
    beta = as_learner(client, BETA)
    target = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=alpha)

    client.put(f"{PROBLEMS}/{target}", json={"status": "not_started"}, headers=beta)
    client.post(f"{PROBLEMS}/{target}/attempt", headers=beta)

    assert client.get(f"{PROBLEMS}/{target}", headers=alpha).json()["status"] == "solved"
    assert client.get(f"{PROBLEMS}/{target}", headers=beta).json()["status"] == "attempted"


def test_each_learner_keeps_their_own_record_for_the_same_problem(client: TestClient, db_session: Session) -> None:
    alpha = as_learner(client, ALPHA)
    beta = as_learner(client, BETA)
    gamma = as_learner(client, GAMMA)
    target = problem_id(client, "two-sum")

    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=alpha)
    client.put(f"{PROBLEMS}/{target}", json={"status": "attempted"}, headers=beta)
    client.post(f"{PROBLEMS}/{target}/attempt", headers=gamma)

    assert client.get(f"{PROBLEMS}/{target}", headers=alpha).json()["status"] == "solved"
    assert client.get(f"{PROBLEMS}/{target}", headers=beta).json()["status"] == "attempted"
    assert client.get(f"{PROBLEMS}/{target}", headers=gamma).json()["status"] == "attempted"

    users = {
        user.email: user.id
        for user in db_session.scalars(select(User).where(User.email.in_([ALPHA["email"], BETA["email"], GAMMA["email"]])))
    }
    assert len(rows_for(users[ALPHA["email"]], db_session)) == 1
    assert len(rows_for(users[BETA["email"]], db_session)) == 1
    assert len(rows_for(users[GAMMA["email"]], db_session)) == 1


def test_a_frontend_supplied_user_id_cannot_redirect_a_request(client: TestClient) -> None:
    """Identity is taken from the token; a body or header claim is ignored."""
    alpha_session = register_session(client, ALPHA)
    beta_session = register_session(client, BETA)
    beta = auth(beta_session["access_token"])
    target = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=beta)

    alpha = auth(alpha_session["access_token"])
    for body in (
        {"status": "solved", "user_id": beta_session["user"]["id"]},
        {"status": "solved", "userId": 999},
    ):
        response = client.put(f"{PROBLEMS}/{target}", json=body, headers=alpha)
        assert response.status_code == 422, "an unexpected field must be rejected outright"

    # Header-based impersonation has to be ignored as well.
    impersonation = client.get(
        SUMMARY, headers={**alpha, "X-User-Id": str(beta_session["user"]["id"])}
    )
    assert impersonation.status_code == 200
    assert impersonation.json()["solved"] == 0

    assert client.get(f"{PROBLEMS}/{target}", headers=beta).json()["status"] == "solved"
    assert client.get(SUMMARY, headers=alpha).json()["solved"] == 0


def test_no_progress_response_names_the_owning_user(client: TestClient) -> None:
    """Responses never echo a user id, so there is nothing to tamper with."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=headers)

    bodies = [
        client.get(SUMMARY, headers=headers).text,
        client.get(PROBLEMS, headers=headers).text,
        client.get(f"{PROBLEMS}/{target}", headers=headers).text,
    ]
    document = client.get("/openapi.json").json()
    progress_schemas = {
        name: schema
        for name, schema in document["components"]["schemas"].items()
        if "Progress" in name and schema.get("properties")
    }

    for body in bodies:
        assert '"user_id"' not in body
    assert progress_schemas
    for name, schema in progress_schemas.items():
        assert "user_id" not in schema["properties"], name


# ----------------------------------------------------------------- validation


def test_unknown_problem_id_returns_not_found(client: TestClient) -> None:
    headers = as_learner(client)

    for path in (f"{PROBLEMS}/999999",):
        assert client.get(path, headers=headers).status_code == 404
        assert client.put(path, json={"status": "solved"}, headers=headers).status_code == 404
        assert client.post(f"{path}/attempt", headers=headers).status_code == 404


@pytest.mark.parametrize("problem_id_value", ["abc", "0", "-1", "1.5"])
def test_malformed_problem_id_is_rejected(client: TestClient, problem_id_value: str) -> None:
    headers = as_learner(client)

    response = client.get(f"{PROBLEMS}/{problem_id_value}", headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"status": "done"},
        {"status": "IN_PROGRESS"},
        {"status": ""},
        {"status": 1},
        {"best_runtime_ms": -1},
        {"best_runtime_ms": MAX_RUNTIME_MS + 1},
        {"best_memory_mb": -5},
        {"best_memory_mb": MAX_MEMORY_MB + 1},
        {"attempts_count": 99},
        {"status": "solved", "unexpected": True},
    ],
)
def test_invalid_update_bodies_are_rejected(client: TestClient, body: dict) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.put(f"{PROBLEMS}/{target}", json=body, headers=headers)

    assert response.status_code == 422, response.text


def test_a_rejected_update_writes_nothing(client: TestClient, db_session: Session) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    client.put(f"{PROBLEMS}/{target}", json={"status": "in_progress"}, headers=headers)

    user = db_session.scalar(select(User).where(User.email == ALPHA["email"]))
    assert rows_for(user.id, db_session) == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_rejects_out_of_range_pagination(client: TestClient, params: dict) -> None:
    headers = as_learner(client)

    assert client.get(PROBLEMS, params=params, headers=headers).status_code == 422


@pytest.mark.parametrize("value", ["not_started", "attempted", "solved"])
def test_list_accepts_every_canonical_status(client: TestClient, value: str) -> None:
    headers = as_learner(client)

    assert client.get(PROBLEMS, params={"status": value}, headers=headers).status_code == 200


@pytest.mark.parametrize("value", ["archived", "done", "", "SOLVED", "in_progress", "completed", "solved "])
def test_list_rejects_an_unknown_or_legacy_status_filter(client: TestClient, value: str) -> None:
    """The query is a strict filter, not a legacy-tolerant reader.

    Legacy labels are normalised when a stored row is read, but a caller asking
    for one is a client bug worth reporting: guessing a status would return a
    confidently wrong list.
    """
    headers = as_learner(client)

    assert client.get(PROBLEMS, params={"status": value}, headers=headers).status_code == 422


@pytest.mark.parametrize("value", ["archived", "", "SOLVED", "in_progress", "completed"])
def test_the_service_refuses_an_unknown_status_value(
    client: TestClient, db_session: Session, value: str
) -> None:
    """Only the three canonical values are accepted as a target status.

    ``completed`` reaches the reader as a legacy alias but must not be accepted
    as a new verdict, or the two vocabularies would keep mixing.
    """
    as_learner(client)  # the learner must exist before the service is called
    problem = db_session.get(Problem, problem_id(client, "two-sum"))
    user = db_session.scalar(select(User).where(User.email == ALPHA["email"]))

    with pytest.raises(ValueError):
        set_status(db_session, user.id, problem, status=value)

    assert rows_for(user.id, db_session) == []


# -------------------------------------------------------------------- streak


def test_streak_counts_consecutive_days_of_recorded_activity() -> None:
    today = date(2026, 3, 10)
    rows = [
        _row_at(2026, 3, 10, 9),
        _row_at(2026, 3, 9, 9),
        _row_at(2026, 3, 8, 9),
        _row_at(2026, 3, 5, 9),
    ]

    assert current_streak_days(rows, today=today) == 3


def test_streak_survives_a_day_that_has_not_ended_yet() -> None:
    today = date(2026, 3, 10)

    assert current_streak_days([_row_at(2026, 3, 9, 22), _row_at(2026, 3, 8, 22)], today=today) == 2


def test_streak_breaks_after_a_missed_day() -> None:
    today = date(2026, 3, 10)

    assert current_streak_days([_row_at(2026, 3, 7, 9), _row_at(2026, 3, 8, 9)], today=today) == 0


def test_streak_is_zero_without_activity() -> None:
    assert current_streak_days([], today=date(2026, 3, 10)) == 0


def test_streak_ignores_legacy_rows_with_no_timestamps() -> None:
    today = date(2026, 3, 10)
    legacy = Progress(
        user_id=1,
        problem_id=1,
        status="solved",
        attempts_count=0,
        last_attempted_at=None,
        solved_at=None,
    )

    assert current_streak_days([legacy], today=today) == 0


def test_api_reports_a_streak_after_activity(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.post(f"{PROBLEMS}/{target}/attempt", headers=headers)

    assert response.status_code == 200
    assert client.get(SUMMARY, headers=headers).json()["current_streak_days"] == 1


def _row_at(year: int, month: int, day: int, hour: int) -> Progress:
    return Progress(
        user_id=1,
        problem_id=1,
        status="attempted",
        attempts_count=1,
        last_attempted_at=datetime(year, month, day, hour, tzinfo=timezone.utc),
        solved_at=None,
    )


# ------------------------------------------------------------------ catalog


def test_the_public_catalog_never_leaks_progress(client: TestClient) -> None:
    """Anonymous readers of /problems see the catalog and nothing about progress."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    client.put(f"{PROBLEMS}/{target}", json={"status": "solved"}, headers=headers)

    for path in ("/api/v1/problems", "/api/v1/dashboard/summary", "/api/v1/problems/two-sum"):
        body = client.get(path).text
        assert "not_started" not in body
        assert "attempts_count" not in body
        assert "solved_at" not in body
