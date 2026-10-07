"""Learner analytics tests.

Covers the summary arithmetic, the activity window, and -- most importantly --
that analytics belong to exactly one learner: no request can read another
learner's numbers, identity comes only from the bearer token, and no response
names whose record it is.

The deterministic parts of the computation (the activity window, the verdict
rates, the interview score statistics) are also driven directly through the
pure builders with pinned timestamps, so those assertions do not depend on the
day the suite happens to run.
"""

from datetime import date, datetime, timezone

import pytest
from database.models import InterviewQuestion, InterviewSession, Progress, Submission, User
from database.models.interview import InterviewQuestionStatus
from database.problem_catalog import CATALOG
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas.analytics import MAX_ACTIVITY_DAYS, MIN_ACTIVITY_DAYS
from backend.app.services import analytics_service
from backend.tests.conftest import CATALOG_BY_DIFFICULTY, CATALOG_SIZE, CATALOG_TOPIC_COUNTS

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

SUMMARY = "/api/v1/analytics/summary"
INTERVIEWS = "/api/v1/interviews"
LEARNING_PATH = "/api/v1/learning-path"
PROGRESS = "/api/v1/progress/problems"

PROTECTED_ENDPOINTS = (("get", SUMMARY),)

#: One catalog slug per difficulty, resolved from the catalog rather than
#: written out, so the suite keeps working when the problem bank changes.
EASY_SLUG = next(item["slug"] for item in CATALOG if item["difficulty"] == "Easy")
MEDIUM_SLUG = next(item["slug"] for item in CATALOG if item["difficulty"] == "Medium")
HARD_SLUG = next(item["slug"] for item in CATALOG if item["difficulty"] == "Hard")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, payload: dict[str, str] = ALPHA) -> dict:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    return auth(register(client, payload)["access_token"])


def summary_for(client: TestClient, headers: dict[str, str], **params) -> dict:
    response = client.get(SUMMARY, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def problem_id(client: TestClient, slug: str) -> int:
    response = client.get(f"/api/v1/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def mark(client: TestClient, headers: dict[str, str], slug: str, status: str) -> None:
    response = client.put(
        f"{PROGRESS}/{problem_id(client, slug)}", json={"status": status}, headers=headers
    )
    assert response.status_code == 200, response.text


def learner_row(db_session: Session, email: str) -> User:
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def add_submission(
    db_session: Session,
    user_id: int,
    slug: str,
    client: TestClient,
    status: str,
    *,
    runtime_ms: int | None = None,
    memory_mb: int | None = None,
    submitted_at: datetime | None = None,
) -> Submission:
    """Persist a submission row directly: the analytics read stored rows."""
    row = Submission(
        user_id=user_id,
        problem_id=problem_id(client, slug),
        language="python",
        source_code="def solve():\n    return 1\n",
        status=status,
        runtime_ms=runtime_ms,
        memory_mb=memory_mb,
        submitted_at=submitted_at or datetime.now(timezone.utc),
        judged_at=None if status in {"queued", "running"} else datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def difficulty_row(payload: dict, level: str) -> dict:
    matches = [row for row in payload["difficulty"] if row["difficulty"] == level]
    assert matches, f"no {level} row in {payload['difficulty']}"
    return matches[0]


def topic_row(payload: dict, topic: str) -> dict:
    matches = [row for row in payload["topics"] if row["topic"] == topic]
    assert matches, f"no {topic} row in {payload['topics']}"
    return matches[0]


def _keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _keys(value)


# ------------------------------------------------------------ authentication


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_every_analytics_endpoint_requires_authentication(
    client: TestClient, method, path
) -> None:
    assert client.request(method, path).status_code == 401


def test_a_bad_token_does_not_unlock_the_analytics(client: TestClient) -> None:
    for headers in ({}, auth(""), auth("invalid-token"), auth("a.b.c")):
        assert client.get(SUMMARY, headers=headers).status_code == 401


def test_analytics_reports_missing_jwt_configuration_as_unavailable(db_engine) -> None:
    """A present-but-unverifiable credential is a 503, never a bypass."""
    from database.seed import seed_demo_data

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


# --------------------------------------------------------------- fresh learner


def test_a_fresh_learner_summarizes_the_published_catalog(client: TestClient) -> None:
    headers = as_learner(client)
    payload = summary_for(client, headers)

    overview = payload["overview"]
    assert overview["total_problems"] == CATALOG_SIZE
    assert overview["solved"] == 0
    assert overview["attempted"] == 0
    assert overview["not_started"] == CATALOG_SIZE
    assert overview["completion_percentage"] == 0.0
    assert overview["current_streak_days"] == 0
    assert overview["total_submissions"] == 0
    assert overview["judged_submissions"] == 0
    assert overview["accepted_submissions"] == 0
    assert overview["acceptance_rate"] == 0.0
    assert overview["problems_submitted"] == 0
    # No evidence means no measurement, and no measurement means None --
    # not a fabricated zero pretending to be an average.
    assert overview["average_runtime_ms"] is None
    assert overview["average_memory_mb"] is None

    assert {row["difficulty"]: row["total"] for row in payload["difficulty"]} == (
        CATALOG_BY_DIFFICULTY
    )
    for row in payload["difficulty"]:
        assert row["solved"] == row["attempted"] == 0
        assert row["completion_percentage"] == 0.0
        assert row["submissions"] == row["judged"] == row["accepted"] == 0
    assert [row["difficulty"] for row in payload["difficulty"]][:3] == [
        "Easy",
        "Medium",
        "Hard",
    ]

    assert {row["topic"]: row["total"] for row in payload["topics"]} == CATALOG_TOPIC_COUNTS
    # An empty history has no verdicts to report, rather than nine zero slices.
    assert payload["verdicts"] == []

    assert payload["activity_days"] == 30
    assert len(payload["activity"]) == 30
    assert all(
        day["submissions"] == day["attempts"] == day["solves"] == 0
        for day in payload["activity"]
    )
    first = date.fromisoformat(payload["activity"][0]["date"])
    last = date.fromisoformat(payload["activity"][-1]["date"])
    assert (last - first).days == 29
    assert payload["as_of"] == payload["activity"][-1]["date"]

    path = payload["learning_path"]
    assert path["total_problems"] == CATALOG_SIZE
    assert path["solved_problems"] == 0
    assert path["stages_total"] > 0
    assert path["stages_complete"] == 0
    assert len(path["stages"]) == path["stages_total"]
    assert path["recommended_problem"] is not None

    interviews = payload["interviews"]
    assert interviews["total"] == interviews["completed"] == 0
    assert interviews["abandoned"] == interviews["active"] == 0
    assert interviews["average_score"] is None
    assert interviews["best_score"] is None
    assert interviews["scores"] == []


def test_the_summary_never_names_whose_record_it_is(client: TestClient) -> None:
    """No `user_id` key anywhere: the token already says whose this is."""
    headers = as_learner(client)
    payload = summary_for(client, headers)

    assert "user_id" not in list(_keys(payload))


# ---------------------------------------------------------------- breakdowns


def test_solved_and_attempted_rows_show_up_in_every_breakdown(
    client: TestClient, db_session: Session
) -> None:
    headers = as_learner(client)
    mark(client, headers, EASY_SLUG, "solved")
    mark(client, headers, MEDIUM_SLUG, "attempted")
    payload = summary_for(client, headers)

    overview = payload["overview"]
    assert overview["solved"] == 1
    assert overview["attempted"] == 1
    assert overview["not_started"] == CATALOG_SIZE - 2
    assert overview["completion_percentage"] == round(1 / CATALOG_SIZE * 100, 2)

    easy = difficulty_row(payload, "Easy")
    assert easy["solved"] == 1
    assert easy["not_started"] == easy["total"] - 1
    assert easy["completion_percentage"] == round(1 / easy["total"] * 100, 2)

    medium = difficulty_row(payload, "Medium")
    assert medium["attempted"] == 1
    assert medium["solved"] == 0

    easy_problem = next(item for item in CATALOG if item["slug"] == EASY_SLUG)
    easy_topics = topic_row(payload, easy_problem["topics"][0])
    assert easy_topics["solved"] >= 1

    # The activity series records the solve as today's work.
    assert payload["activity"][-1]["solves"] >= 1
    assert payload["activity"][-1]["attempts"] >= 1

    # The learning path sees the same rows the breakdowns do.
    assert payload["learning_path"]["solved_problems"] == 1
    assert payload["learning_path"]["attempted_problems"] == 1

    # Progress rows belong to this learner and are not shared with the catalog.
    user = learner_row(db_session, ALPHA["email"])
    rows = list(
        db_session.scalars(select(Progress).where(Progress.user_id == user.id))
    )
    assert len(rows) == 2


def test_verdicts_and_performance_come_from_stored_submissions(
    client: TestClient, db_session: Session
) -> None:
    headers = as_learner(client)
    user = learner_row(db_session, ALPHA["email"])
    add_submission(db_session, user.id, EASY_SLUG, client, "accepted", runtime_ms=120, memory_mb=64)
    add_submission(db_session, user.id, EASY_SLUG, client, "accepted", runtime_ms=80, memory_mb=48)
    add_submission(db_session, user.id, MEDIUM_SLUG, client, "wrong_answer", runtime_ms=200)
    add_submission(db_session, user.id, HARD_SLUG, client, "queued")

    payload = summary_for(client, headers)
    overview = payload["overview"]
    assert overview["total_submissions"] == 4
    assert overview["judged_submissions"] == 3
    assert overview["accepted_submissions"] == 2
    assert overview["acceptance_rate"] == round(2 / 3 * 100, 2)
    assert overview["problems_submitted"] == 3
    # Averages are taken only over rows that carry a measurement: the queued
    # row has no runtime, so it is not counted as a zero.
    assert overview["average_runtime_ms"] == round((120 + 80 + 200) / 3, 2)
    assert overview["average_memory_mb"] == round((64 + 48) / 2, 2)

    verdicts = {row["status"]: row for row in payload["verdicts"]}
    assert verdicts["accepted"]["count"] == 2
    assert verdicts["wrong_answer"]["count"] == 1
    assert verdicts["queued"]["count"] == 1
    assert verdicts["accepted"]["percentage"] == 50.0
    assert verdicts["queued"]["percentage"] == 25.0

    easy = difficulty_row(payload, "Easy")
    assert easy["submissions"] == 2
    assert easy["judged"] == 2
    assert easy["accepted"] == 2
    assert easy["acceptance_rate"] == 100.0

    hard = difficulty_row(payload, "Hard")
    assert hard["submissions"] == 1
    assert hard["judged"] == 0
    # Nothing was judged in this tier, so the rate is 0.0 rather than a guess.
    assert hard["acceptance_rate"] == 0.0


def test_a_legacy_status_is_counted_as_failed_like_every_other_reader() -> None:
    """A label outside the vocabulary cannot be stored through the API, but a
    pre-release row could hold one. Every reader in the platform maps it to
    ``failed`` -- never to ``queued`` (which would claim it awaits a run) and
    never to ``accepted`` -- and the analytics summary must agree."""
    legacy = Submission(
        user_id=1,
        problem_id=1,
        language="python",
        source_code="x",
        status="totally-bogus",
        submitted_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
    )

    verdicts = analytics_service.build_verdict_breakdown([legacy])
    assert [(row.status, row.count, row.percentage) for row in verdicts] == [
        ("failed", 1, 100.0)
    ]

    overview = analytics_service.build_overview([], [], [legacy], today=date(2026, 3, 15))
    assert overview.total_submissions == 1
    assert overview.judged_submissions == 1
    assert overview.accepted_submissions == 0
    assert overview.acceptance_rate == 0.0


# ------------------------------------------------------------------ activity


def test_the_activity_window_is_zero_filled_and_bounded_by_today() -> None:
    """The series is one entry per day, ending today, quiet days included."""
    today = date(2026, 3, 15)
    inside = Submission(
        user_id=1,
        problem_id=1,
        language="python",
        source_code="x",
        status="accepted",
        submitted_at=datetime(2026, 3, 13, 9, 30, tzinfo=timezone.utc),
    )
    outside = Submission(
        user_id=1,
        problem_id=1,
        language="python",
        source_code="x",
        status="accepted",
        submitted_at=datetime(2026, 2, 1, 9, 30, tzinfo=timezone.utc),
    )
    progress = Progress(
        user_id=1,
        problem_id=1,
        status="solved",
        attempts_count=1,
        last_attempted_at=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc),
        solved_at=datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc),
    )

    series = analytics_service.build_activity(
        [progress], [inside, outside], days=7, today=today
    )

    assert [day.date for day in series] == [
        date(2026, 3, 9),
        date(2026, 3, 10),
        date(2026, 3, 11),
        date(2026, 3, 12),
        date(2026, 3, 13),
        date(2026, 3, 14),
        date(2026, 3, 15),
    ]
    assert [day.submissions for day in series] == [0, 0, 0, 0, 1, 0, 0]
    assert [day.attempts for day in series] == [0, 0, 0, 0, 0, 0, 1]
    assert [day.solves for day in series] == [1, 0, 0, 0, 0, 0, 0]
    # A submission from February is real history, but outside this window.
    assert sum(day.submissions for day in series) == 1


def test_a_requested_window_is_clamped_to_the_promised_range() -> None:
    assert analytics_service.clamp_activity_days(1) == MIN_ACTIVITY_DAYS
    assert analytics_service.clamp_activity_days(10_000) == MAX_ACTIVITY_DAYS
    assert analytics_service.clamp_activity_days(45) == 45


def test_the_summary_carries_the_window_it_actually_used(
    client: TestClient,
) -> None:
    headers = as_learner(client)
    payload = summary_for(client, headers, days=7)
    assert payload["activity_days"] == 7
    assert len(payload["activity"]) == 7

    default = summary_for(client, headers)
    assert default["activity_days"] == 30
    assert len(default["activity"]) == 30


def test_an_out_of_range_window_is_rejected_not_silently_clamped(
    client: TestClient,
) -> None:
    headers = as_learner(client)
    assert client.get(SUMMARY, headers=headers, params={"days": 6}).status_code == 422
    assert client.get(SUMMARY, headers=headers, params={"days": 91}).status_code == 422
    assert client.get(SUMMARY, headers=headers, params={"days": "soon"}).status_code == 422


# ----------------------------------------------------------------- ownership


def test_one_learner_never_sees_another_learners_numbers(
    client: TestClient, db_session: Session
) -> None:
    alpha = as_learner(client, ALPHA)
    mark(client, alpha, EASY_SLUG, "solved")
    user = learner_row(db_session, ALPHA["email"])
    add_submission(db_session, user.id, EASY_SLUG, client, "accepted", runtime_ms=55, memory_mb=32)

    beta = as_learner(client, BETA)
    payload = summary_for(client, beta)

    overview = payload["overview"]
    assert overview["total_problems"] == CATALOG_SIZE
    assert overview["solved"] == 0
    assert overview["total_submissions"] == 0
    assert overview["acceptance_rate"] == 0.0
    assert overview["average_runtime_ms"] is None
    assert payload["verdicts"] == []
    assert all(
        day["submissions"] == day["attempts"] == day["solves"] == 0
        for day in payload["activity"]
    )
    assert payload["learning_path"]["solved_problems"] == 0

    # And the other direction: alpha's own numbers are still intact.
    alpha_payload = summary_for(client, alpha)
    assert alpha_payload["overview"]["solved"] == 1
    assert alpha_payload["overview"]["total_submissions"] == 1
    assert alpha_payload["overview"]["average_runtime_ms"] == 55.0


def test_the_summary_agrees_with_the_learning_path_endpoint(
    client: TestClient,
) -> None:
    """Both read the same rows, so the analytics page cannot drift from the path."""
    headers = as_learner(client)
    mark(client, headers, EASY_SLUG, "solved")
    mark(client, headers, MEDIUM_SLUG, "attempted")

    path = client.get(LEARNING_PATH, headers=headers)
    assert path.status_code == 200, path.text
    path = path.json()
    payload = summary_for(client, headers)
    analytics_path = payload["learning_path"]

    assert analytics_path["total_problems"] == path["total_problems"]
    assert analytics_path["solved_problems"] == path["solved_problems"]
    assert analytics_path["attempted_problems"] == path["attempted_problems"]
    assert analytics_path["completion_percentage"] == path["completion_percentage"]
    assert analytics_path["stages_total"] == path["stages_total"]
    assert analytics_path["stages_complete"] == path["stages_complete"]
    assert analytics_path["current_stage_title"] == path["current_stage_title"]
    assert analytics_path["weak_topics"] == path["weak_topics"]
    assert len(analytics_path["stages"]) == len(path["stages"])
    recommended = path["recommendation"]
    assert analytics_path["recommended_problem"] == (
        recommended["problem"]["title"] if recommended else None
    )
    assert analytics_path["recommended_reason"] == (
        recommended["reason"] if recommended else None
    )


# ---------------------------------------------------------------- interviews


def create_interview(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {"question_count": 2, "duration_minutes": 30}
    payload.update(overrides)
    response = client.post(INTERVIEWS, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_interview_analytics_counts_sessions_and_scores(
    client: TestClient, db_session: Session
) -> None:
    headers = as_learner(client)

    first = create_interview(client, headers, question_count=3)
    assert client.post(f"{INTERVIEWS}/{first['id']}/start", headers=headers).status_code == 200
    assert client.post(f"{INTERVIEWS}/{first['id']}/finish", headers=headers).status_code == 200

    second = create_interview(client, headers, question_count=1)
    assert (
        client.post(f"{INTERVIEWS}/{second['id']}/abandon", headers=headers).status_code == 200
    )

    third = create_interview(client, headers, question_count=1)

    payload = summary_for(client, headers)
    interviews = payload["interviews"]
    assert interviews["total"] == 3
    assert interviews["completed"] == 1
    assert interviews["abandoned"] == 1
    assert interviews["active"] == 1
    # The finished session answered nothing, so it scored 0 -- a real score
    # the platform computed, not a missing one.
    assert interviews["average_score"] == 0.0
    assert interviews["best_score"] == 0
    assert interviews["questions_total"] == 3 + 1 + 1
    assert interviews["questions_answered"] == 0
    assert interviews["questions_accepted"] == 0
    assert interviews["acceptance_rate"] == 0.0
    assert len(interviews["scores"]) == 1
    assert interviews["scores"][0]["interview_id"] == first["id"]
    assert interviews["scores"][0]["score"] == 0

    # An abandoned session carries no score, and the score list is completed
    # sessions only.
    assert third["id"] not in [point["interview_id"] for point in interviews["scores"]]


def test_question_acceptance_is_read_from_the_linked_submission(
    client: TestClient, db_session: Session
) -> None:
    headers = as_learner(client)
    create_interview(client, headers, question_count=1)
    user = learner_row(db_session, ALPHA["email"])

    question = db_session.scalar(
        select(InterviewQuestion)
        .join(InterviewSession, InterviewQuestion.session_id == InterviewSession.id)
        .where(InterviewSession.user_id == user.id)
    )
    assert question is not None
    submission = add_submission(db_session, user.id, EASY_SLUG, client, "accepted")
    question.submission_id = submission.id
    question.status = InterviewQuestionStatus.SUBMITTED.value
    db_session.commit()

    payload = summary_for(client, headers)
    interviews = payload["interviews"]
    assert interviews["questions_total"] == 1
    assert interviews["questions_answered"] == 1
    assert interviews["questions_accepted"] == 1
    assert interviews["acceptance_rate"] == 100.0


def test_an_abandoned_interview_is_never_averaged_as_a_zero_score(
    client: TestClient,
) -> None:
    headers = as_learner(client)
    created = create_interview(client, headers, question_count=1)
    assert (
        client.post(f"{INTERVIEWS}/{created['id']}/abandon", headers=headers).status_code == 200
    )

    payload = summary_for(client, headers)
    interviews = payload["interviews"]
    assert interviews["total"] == 1
    assert interviews["abandoned"] == 1
    assert interviews["average_score"] is None
    assert interviews["best_score"] is None
    assert interviews["scores"] == []


def test_interview_rows_are_owner_scoped_end_to_end(
    client: TestClient, db_session: Session
) -> None:
    alpha = as_learner(client, ALPHA)
    created = create_interview(client, alpha, question_count=1)

    beta = as_learner(client, BETA)
    payload = summary_for(client, beta)
    interviews = payload["interviews"]
    assert interviews["total"] == 0
    assert interviews["questions_total"] == 0
    assert created["id"] not in [point["interview_id"] for point in interviews["scores"]]
