"""Mock interview endpoints: lifecycle, timer, selection, scoring, ownership.

Covers the surface (authenticated, owner-scoped routes), the deterministic
selection, the server-side timer, the judge-powered submission flow, the
deterministic score, and the report/history read paths. The two rules the
feature is really about are asserted throughout:

* a verdict, a score, a remaining time, and a selection are **never sent by a
  client** -- requests name calibration, language, and source only, and
  ``extra="forbid"`` proves it;
* one learner can never see, count, or address another learner's interviews.

Submissions are driven through the real judge (no mocking), matching the
submission suite, so the verdict assertions are about AlgoTwin running code.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from database.models import InterviewQuestion, InterviewSession, Submission
from database.models.interview import InterviewQuestion as _Question
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.services import interview_service

INTERVIEWS = "/api/v1/interviews"

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

#: A genuine two-sum solve in the catalog's stdin format, so the accepted path
#: is a real pass rather than a value a test wrote into a fake judge.
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

#: Something that runs cleanly and always prints a wrong answer, for the
#: verdicts that are not a pass.
WRONG_ANSWER = "import sys\nprint('nope')\n"

SECRET_KEYS = ("test_cases", "reference_solutions", "expected_output", "case_input")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return auth(response.json()["access_token"])


def create(
    client: TestClient,
    headers: dict[str, str],
    **overrides,
) -> dict:
    payload = {
        "role": "Software Engineer",
        "level": "mid",
        "question_count": 3,
        "duration_minutes": 30,
    }
    payload.update(overrides)
    response = client.post(INTERVIEWS, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def start(client: TestClient, headers: dict[str, str], interview_id: int) -> dict:
    response = client.post(f"{INTERVIEWS}/{interview_id}/start", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def stored_session(db, interview_id: int, user_id: int) -> InterviewSession:
    session = db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == interview_id,
            InterviewSession.user_id == user_id,
        )
    )
    assert session is not None
    return session


def stored_question(db, interview_id: int, position: int) -> _Question:
    question = db.scalar(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == interview_id,
            InterviewQuestion.position == position,
        )
    )
    assert question is not None
    return question


def response_leaks_no_test_material(payload: dict) -> list[str]:
    """Secret keys that leaked into an interview response, if any."""
    leaked: list[str] = []
    for question in payload.get("questions", []):
        for key in SECRET_KEYS:
            if key in question:
                leaked.append(f"question.{key}")
    for key in SECRET_KEYS:
        if key in payload:
            leaked.append(key)
    return leaked


# ------------------------------------------------------------------ pure unit


def _problem(slug: str, difficulty: str, topics: list[str] | None = None, id: int = 0):
    return SimpleNamespace(
        id=id, slug=slug, difficulty=difficulty, topics=topics or [], is_published=True
    )


def test_the_selection_is_deterministic_and_spreads_difficulties() -> None:
    """Two identical inputs pick the same problems in the same order.

    The round-robin is the point of the ordering rule: an unfiltered three-
    question interview draws Easy, Medium, then Hard rather than three Easy
    problems, and a repeat draw is byte-for-byte the same list.
    """
    problems = [
        _problem("a", "Easy", id=0),
        _problem("b", "Easy", id=1),
        _problem("c", "Medium", id=2),
        _problem("d", "Hard", id=3),
        _problem("e", "Easy", id=4),
        _problem("f", "Medium", id=5),
    ]

    def pick(difficulty=None, topic=None) -> list[str]:
        return [
            p.slug
            for p in interview_service.select_interview_questions(problems, 3, difficulty, topic)
        ]

    assert pick() == pick()
    assert pick(difficulty="Easy") == ["a", "b", "e"]
    assert pick(difficulty="Medium") == ["c", "f"]
    # Round-robining across tiers: Easy, Medium, Hard, then the rest again.
    assert pick() == ["a", "c", "d"]


def test_the_selection_stops_when_the_catalog_runs_out() -> None:
    problems = [_problem("p0", "Easy", id=0), _problem("p1", "Easy", id=1)]
    assert len(interview_service.select_interview_questions(problems, 5)) == 2


def test_compute_score_is_deterministic() -> None:
    def question(accepted: bool):
        class _P:
            pass

        q = _P()
        q.is_submitted = True
        if accepted:
            q.submission = _P()
            q.submission.status = "accepted"
        else:
            q.submission = _P()
            q.submission.status = "wrong_answer"
        return q

    assert interview_service.compute_score([question(True), question(True)]) == 100
    assert interview_service.compute_score([question(True), question(False)]) == 50
    assert interview_service.compute_score([question(False), question(False)]) == 0
    assert interview_service.compute_score([]) == 0


# ------------------------------------------------------------ surface & auth


def test_interview_routes_require_a_token(client: TestClient) -> None:
    calls = [
        ("post", INTERVIEWS, {}),
        ("get", INTERVIEWS, None),
        ("get", f"{INTERVIEWS}/active", None),
        ("get", f"{INTERVIEWS}/1", None),
        ("post", f"{INTERVIEWS}/1/start", None),
        ("post", f"{INTERVIEWS}/1/finish", None),
        ("post", f"{INTERVIEWS}/1/abandon", None),
        ("get", f"{INTERVIEWS}/1/report", None),
        ("post", f"{INTERVIEWS}/1/questions/0/submit", {"language": "python", "source_code": "x"}),
    ]
    for method, path, payload in calls:
        response = client.request(method, path, json=payload)
        assert response.status_code == 401, (method, path, response.status_code)


def test_create_rejects_payload_fields_the_client_does_not_own(client: TestClient) -> None:
    headers = as_learner(client)
    assert client.post(
        INTERVIEWS, json={"score": 90}, headers=headers
    ).status_code == 422
    assert client.post(
        INTERVIEWS, json={"verdict": "accepted"}, headers=headers
    ).status_code == 422
    assert client.post(
        INTERVIEWS, json={"remaining_seconds": 5}, headers=headers
    ).status_code == 422
    assert client.post(
        INTERVIEWS, json={"user_id": 1}, headers=headers
    ).status_code == 422
    assert client.post(
        INTERVIEWS, json={"problem_ids": [1]}, headers=headers
    ).status_code == 422


def test_the_answer_payload_carries_only_language_and_source(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1)
    session = start(client, headers, interview["id"])
    path = f"{INTERVIEWS}/{session['id']}/questions/0/submit"
    assert client.post(
        path, json={"language": "python", "source_code": "x", "verdict": "accepted"}, headers=headers
    ).status_code == 422
    assert client.post(
        path, json={"language": "python", "source_code": "x", "problem_id": 1}, headers=headers
    ).status_code == 422


def test_a_default_interview_records_its_selection(client: TestClient, db_session) -> None:
    headers = as_learner(client)
    response = client.post(INTERVIEWS, json={}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "created"
    assert body["role"] == "Software Engineer"
    assert body["level"] is None and body["difficulty"] is None and body["topic"] is None
    assert body["question_count"] == 3
    assert body["duration_seconds"] == 1800
    assert body["current_index"] == 0
    assert body["score"] is None
    assert body["started_at"] is None and body["expires_at"] is None
    assert body["remaining_seconds"] is None
    assert body["timed_out"] is False
    assert body["questions"][0]["position"] == 0
    assert body["questions"][2]["position"] == 2

    rows = list(
        db_session.execute(
            select(InterviewQuestion).where(InterviewQuestion.session_id == body["id"])
        ).scalars()
    )
    assert [row.position for row in rows] == [0, 1, 2]
    assert all(row.status == "pending" for row in rows)
    assert all(row.attempts == 0 for row in rows)
    assert all(row.submission_id is None for row in rows)
    assert not response_leaks_no_test_material(body)


def test_default_selection_round_robins_across_difficulties(client: TestClient) -> None:
    body = create(client, as_learner(client))
    assert [q["difficulty"] for q in body["questions"]] == ["Easy", "Medium", "Hard"]
    assert body["questions"][0]["slug"] == "two-sum"


def test_the_selection_is_deterministic_across_two_creations(client: TestClient) -> None:
    headers = as_learner(client)
    first = create(client, headers, question_count=3)
    client.post(f"{INTERVIEWS}/{first['id']}/abandon", headers=headers)
    second = create(client, headers, question_count=3)
    assert first["id"] != second["id"]
    assert [q["slug"] for q in first["questions"]] == [q["slug"] for q in second["questions"]]


def test_difficulty_and_topic_filters_both_narrow_the_pick(client: TestClient) -> None:
    headers = as_learner(client)
    body = create(client, headers, question_count=3, difficulty="Easy")
    assert [q["difficulty"] for q in body["questions"]] == ["Easy", "Easy", "Easy"]

    headers = as_learner(client, BETA)
    easy = create(client, headers, question_count=3, difficulty="Easy", topic="arrays")
    assert all("Arrays" in q["topics"] for q in easy["questions"])


def test_topic_matching_is_case_insensitive(client: TestClient) -> None:
    lower = create(client, as_learner(client), question_count=2, difficulty="Easy", topic="arrays")
    upper = create(
        client, as_learner(client, BETA), question_count=2, difficulty="Easy", topic="ARRAYS"
    )
    assert [q["slug"] for q in lower["questions"]] == [q["slug"] for q in upper["questions"]]


def test_calibration_is_stored_and_echoed(client: TestClient) -> None:
    headers = as_learner(client)
    body = create(
        client,
        headers,
        role="Senior Backend Engineer",
        level="senior",
        difficulty="Hard",
        topic="graphs",
        question_count=4,
        duration_minutes=45,
    )
    assert body["role"] == "Senior Backend Engineer"
    assert body["level"] == "senior"
    assert body["difficulty"] == "Hard"
    assert body["topic"] == "graphs"
    assert body["question_count"] == 4
    assert body["duration_seconds"] == 45 * 60


def test_whitespace_only_calibration_fields_are_rejected(client: TestClient) -> None:
    headers = as_learner(client)
    assert client.post(
        INTERVIEWS, json={"role": "   "}, headers=headers
    ).status_code == 422
    assert client.post(
        INTERVIEWS, json={"topic": "  "}, headers=headers
    ).status_code == 422
    assert client.post(
        INTERVIEWS, json={"level": " "}, headers=headers
    ).status_code == 422


@pytest.mark.parametrize("question_count", [0, 11])
def test_question_count_is_bounded(client: TestClient, question_count: int) -> None:
    assert client.post(
        INTERVIEWS, json={"question_count": question_count}, headers=as_learner(client)
    ).status_code == 422


@pytest.mark.parametrize("minutes", [1, 121])
def test_duration_minutes_is_bounded(client: TestClient, minutes: int) -> None:
    assert client.post(
        INTERVIEWS, json={"duration_minutes": minutes}, headers=as_learner(client)
    ).status_code == 422


def test_an_unfillable_selection_is_a_conflict(client: TestClient) -> None:
    response = client.post(
        INTERVIEWS,
        json={"topic": "no-such-topic-anywhere"},
        headers=as_learner(client),
    )
    assert response.status_code == 409
    assert "supply 0 problems" in response.json()["detail"]


def test_one_active_session_per_learner(client: TestClient) -> None:
    headers = as_learner(client)
    first = create(client, headers)

    response = client.post(INTERVIEWS, json={}, headers=headers)
    assert response.status_code == 409
    assert str(first["id"]) in response.json()["detail"]

    # Starting does not change the rule: it is still one active session.
    session = start(client, headers, first["id"])
    assert client.post(INTERVIEWS, json={}, headers=headers).status_code == 409

    # Abandoning frees the slot.
    assert client.post(f"{INTERVIEWS}/{session['id']}/abandon", headers=headers).status_code == 200
    assert client.post(INTERVIEWS, json={}, headers=headers).status_code == 201


def test_another_learners_interview_is_a_404(client: TestClient) -> None:
    alpha = as_learner(client)
    beta = as_learner(client, BETA)
    interview = create(client, alpha)

    assert client.get(f"{INTERVIEWS}/{interview['id']}", headers=beta).status_code == 404
    assert client.post(f"{INTERVIEWS}/{interview['id']}/start", headers=beta).status_code == 404
    assert client.post(f"{INTERVIEWS}/{interview['id']}/finish", headers=beta).status_code == 404
    assert client.post(f"{INTERVIEWS}/{interview['id']}/abandon", headers=beta).status_code == 404
    assert client.get(f"{INTERVIEWS}/{interview['id']}/report", headers=beta).status_code == 404
    assert client.post(
        f"{INTERVIEWS}/{interview['id']}/questions/0/submit",
        json={"language": "python", "source_code": "x"},
        headers=beta,
    ).status_code == 404
    assert client.get(f"{INTERVIEWS}/active", headers=beta).status_code == 404
    assert client.get(INTERVIEWS, headers=beta).json()["items"] == []


def test_an_unknown_interview_is_a_404(client: TestClient) -> None:
    headers = as_learner(client)
    assert client.get(f"{INTERVIEWS}/999", headers=headers).status_code == 404
    assert client.post(f"{INTERVIEWS}/999/start", headers=headers).status_code == 404
    assert client.get(f"{INTERVIEWS}/999/report", headers=headers).status_code == 404


# -------------------------------------------------------------------- lifecycle


def test_start_sets_the_timer_from_the_server_clock(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)

    created = client.get(f"{INTERVIEWS}/{interview['id']}", headers=headers).json()
    assert created["remaining_seconds"] is None
    assert created["started_at"] is None and created["expires_at"] is None

    session = start(client, headers, interview["id"])
    assert session["status"] == "in_progress"
    assert session["started_at"] is not None
    assert session["expires_at"] is not None
    assert session["remaining_seconds"] is not None
    assert 0 < session["remaining_seconds"] <= session["duration_seconds"]


def test_starting_twice_is_a_conflict(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    start(client, headers, interview["id"])
    response = client.post(f"{INTERVIEWS}/{interview['id']}/start", headers=headers)
    assert response.status_code == 409


def test_finish_is_only_valid_on_a_running_session(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    assert client.post(f"{INTERVIEWS}/{interview['id']}/finish", headers=headers).status_code == 409


def test_abandon_a_created_session_leaves_no_score(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    response = client.post(f"{INTERVIEWS}/{interview['id']}/abandon", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "abandoned"
    assert body["score"] is None
    assert body["completed_at"] is not None
    assert client.get(f"{INTERVIEWS}/active", headers=headers).status_code == 404


def test_abandon_a_running_session_leaves_no_score(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    body = client.post(f"{INTERVIEWS}/{session['id']}/abandon", headers=headers).json()
    assert body["status"] == "abandoned"
    assert body["score"] is None
    assert client.get(f"{INTERVIEWS}/{session['id']}/report", headers=headers).status_code == 409


def test_abandon_a_finished_session_is_a_conflict(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    finish = client.post(f"{INTERVIEWS}/{session['id']}/finish", headers=headers)
    assert finish.status_code == 200
    assert client.post(f"{INTERVIEWS}/{session['id']}/abandon", headers=headers).status_code == 409


def test_finishing_an_unanswered_session_scores_zero(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    body = client.post(f"{INTERVIEWS}/{session['id']}/finish", headers=headers).json()

    assert body["status"] == "completed"
    assert body["score"] == 0
    assert body["timed_out"] is False
    assert body["remaining_seconds"] is None
    assert body["completed_at"] is not None
    assert not response_leaks_no_test_material(body)


def test_the_active_endpoint_tracks_the_lifecycle(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    active = client.get(f"{INTERVIEWS}/active", headers=headers).json()
    assert active["id"] == interview["id"] and active["status"] == "created"

    session = start(client, headers, interview["id"])
    assert client.get(f"{INTERVIEWS}/active", headers=headers).json()["status"] == "in_progress"

    client.post(f"{INTERVIEWS}/{session['id']}/finish", headers=headers)
    assert client.get(f"{INTERVIEWS}/active", headers=headers).status_code == 404


# ----------------------------------------------------------------------- timer


def _force_expiry(db, interview_id: int) -> None:
    """Move a running session's expiry into the past on the stored row."""
    row = db.scalar(select(InterviewSession).where(InterviewSession.id == interview_id))
    row.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db.commit()


def test_an_expired_session_is_finalised_on_read(client: TestClient, db_session) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    _force_expiry(db_session, session["id"])

    body = client.get(f"{INTERVIEWS}/{session['id']}", headers=headers).json()
    assert body["status"] == "completed"
    assert body["timed_out"] is True
    assert body["remaining_seconds"] is None
    assert body["score"] == 0
    assert body["completed_at"] == body["expires_at"]
    assert client.get(f"{INTERVIEWS}/active", headers=headers).status_code == 404


def test_submitting_after_expiry_is_a_refused_conflict(client: TestClient, db_session) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    problem_id = interview["questions"][0]["problem_id"]
    _force_expiry(db_session, session["id"])

    response = client.post(
        f"{INTERVIEWS}/{session['id']}/questions/0/submit",
        json={"language": "python", "source_code": TWO_SUM_PYTHON},
        headers=headers,
    )
    assert response.status_code == 409
    assert "time has run out" in response.json()["detail"]

    question = stored_question(db_session, session["id"], 0)
    assert question.status == "pending"
    assert question.submission_id is None
    # The refusal happens before the judge, so nothing was stored unjudged either.
    assert (
        db_session.scalar(select(func.count()).select_from(Submission).where(Submission.problem_id == problem_id))
        == 0
    )


def test_finish_and_abandon_after_expiry_report_the_run_out(client: TestClient, db_session) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    _force_expiry(db_session, session["id"])

    finish = client.post(f"{INTERVIEWS}/{session['id']}/finish", headers=headers)
    assert finish.status_code == 409
    assert "time has run out" in finish.json()["detail"]

    abandon = client.post(f"{INTERVIEWS}/{session['id']}/abandon", headers=headers)
    assert abandon.status_code == 409


# ------------------------------------------------------------------ submissions


def _submit(
    client: TestClient,
    headers: dict[str, str],
    interview_id: int,
    position: int,
    source: str = WRONG_ANSWER,
) -> dict:
    response = client.post(
        f"{INTERVIEWS}/{interview_id}/questions/{position}/submit",
        json={"language": "python", "source_code": source},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_an_interview_answer_is_judged_by_the_same_judge_as_a_submission(
    client: TestClient,
) -> None:
    """The interview outcome equals the platform's own verdict for the problem.

    The interview question is a real catalog problem with a real judge, so the
    guarantee here is that the interview's answer went through the same grader
    a normal submission goes through -- not that some interview-specific result
    was invented for it.
    """
    headers = as_learner(client)
    interview = create(client, headers, question_count=1, difficulty="Easy", topic="arrays")
    assert interview["questions"][0]["slug"] == "two-sum"
    session = start(client, headers, interview["id"])

    body = _submit(client, headers, session["id"], 0, source=TWO_SUM_PYTHON)
    question = body["questions"][0]
    assert question["status"] == "submitted"
    assert question["accepted"] is True
    assert question["verdict"] == "accepted"
    assert question["submission_id"] is not None
    assert question["attempts"] == 1

    synchronous = client.post(
        "/api/v1/submissions",
        json={
            "problem_id": interview["questions"][0]["problem_id"],
            "language": "python",
            "source_code": TWO_SUM_PYTHON,
        },
        headers=headers,
    ).json()
    assert synchronous["status"] == "accepted"
    assert not response_leaks_no_test_material(body)


def test_a_wrong_answer_is_recorded_as_the_judge_said(client: TestClient, db_session) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1)
    session = start(client, headers, interview["id"])

    body = _submit(client, headers, session["id"], 0, source=WRONG_ANSWER)
    question = body["questions"][0]
    assert question["status"] == "submitted"
    assert question["verdict"] != "pending"
    assert question["accepted"] is False
    assert not question["accepted"]

    row = stored_question(db_session, session["id"], 0)
    assert row.status == "submitted"
    assert row.attempts == 1
    assert row.submission_id == question["submission_id"]
    assert row.answered_at is not None


def test_the_last_answer_completes_and_scores_the_interview(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=2, difficulty="Easy", topic="arrays")
    session = start(client, headers, interview["id"])
    first = interview["questions"][0]["slug"]

    # Two-sum is first; give it a real solve, and a wrong answer to the second.
    if first == "two-sum":
        _submit(client, headers, session["id"], 0, source=TWO_SUM_PYTHON)
    else:
        _submit(client, headers, session["id"], 0, source=WRONG_ANSWER)
    body = _submit(client, headers, session["id"], 1, source=WRONG_ANSWER)

    assert body["status"] == "completed"
    assert body["score"] == 50
    assert body["timed_out"] is False
    assert body["current_index"] == 1
    assert all(q["status"] == "submitted" for q in body["questions"])
    assert client.get(f"{INTERVIEWS}/active", headers=headers).status_code == 404


def test_submitting_to_a_question_that_was_not_drawn_is_a_404(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1)
    session = start(client, headers, interview["id"])
    response = client.post(
        f"{INTERVIEWS}/{session['id']}/questions/5/submit",
        json={"language": "python", "source_code": WRONG_ANSWER},
        headers=headers,
    )
    assert response.status_code == 404


def test_submitting_before_start_is_a_conflict(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    response = client.post(
        f"{INTERVIEWS}/{interview['id']}/questions/0/submit",
        json={"language": "python", "source_code": WRONG_ANSWER},
        headers=headers,
    )
    assert response.status_code == 409


def test_an_unsupported_language_is_a_422_before_anything_is_stored(
    client: TestClient, db_session
) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1)
    session = start(client, headers, interview["id"])

    response = client.post(
        f"{INTERVIEWS}/{session['id']}/questions/0/submit",
        json={"language": "cobol", "source_code": WRONG_ANSWER},
        headers=headers,
    )
    assert response.status_code == 422

    row = stored_question(db_session, session["id"], 0)
    assert row.status == "pending"
    assert row.attempts == 0
    assert (
        db_session.scalar(
            select(Submission).where(Submission.problem_id == interview["questions"][0]["problem_id"])
        )
        is None
    )


def test_a_blank_source_is_rejected(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1)
    session = start(client, headers, interview["id"])
    response = client.post(
        f"{INTERVIEWS}/{session['id']}/questions/0/submit",
        json={"language": "python", "source_code": "   \n"},
        headers=headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------- report


def test_a_report_is_only_available_for_completed_interviews(client: TestClient) -> None:
    headers = as_learner(client)
    created = create(client, headers)
    assert (
        client.get(f"{INTERVIEWS}/{created['id']}/report", headers=headers).status_code == 409
    )
    running = start(client, headers, created["id"])
    assert client.get(f"{INTERVIEWS}/{running['id']}/report", headers=headers).status_code == 409


def test_the_report_reads_back_what_actually_happened(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1, difficulty="Easy", topic="arrays")
    session = start(client, headers, interview["id"])
    body = _submit(client, headers, session["id"], 0, source=TWO_SUM_PYTHON)
    completed = body

    report = client.get(f"{INTERVIEWS}/{completed['id']}/report", headers=headers).json()
    assert report["status"] == "completed"
    assert report["question_count"] == 1
    assert report["score"] == 100
    assert report["questions_answered"] == 1
    assert report["questions_accepted"] == 1
    assert report["timed_out"] is False
    assert report["duration_used_seconds"] >= 0
    question = report["questions"][0]
    assert question["accepted"] is True
    assert question["test_cases_total"] is not None
    assert question["test_cases_passed"] == question["test_cases_total"]
    assert not response_leaks_no_test_material(report)


def test_an_abandoned_interview_has_no_report(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers)
    session = start(client, headers, interview["id"])
    client.post(f"{INTERVIEWS}/{session['id']}/abandon", headers=headers)
    assert client.get(f"{INTERVIEWS}/{session['id']}/report", headers=headers).status_code == 409


# ---------------------------------------------------------------------- history


def test_history_lists_only_my_own_interviews_newest_first(client: TestClient) -> None:
    alpha = as_learner(client)
    beta = as_learner(client, BETA)
    first = create(client, alpha)
    client.post(f"{INTERVIEWS}/{first['id']}/abandon", headers=alpha)
    create(client, alpha)
    create(client, beta)

    items = client.get(INTERVIEWS, headers=alpha).json()["items"]
    assert [item["id"] for item in items] == sorted((item["id"] for item in items), reverse=True)
    assert items[0]["role"] == "Software Engineer"
    assert all(item["score"] is None for item in items)


def test_history_filters_by_status_and_paginates(client: TestClient) -> None:
    headers = as_learner(client)
    a = create(client, headers)
    client.post(f"{INTERVIEWS}/{a['id']}/abandon", headers=headers)
    b = create(client, headers)
    client.post(f"{INTERVIEWS}/{b['id']}/abandon", headers=headers)
    c = create(client, headers)

    abandoned = client.get(f"{INTERVIEWS}?status=abandoned", headers=headers).json()
    assert {item["id"] for item in abandoned["items"]} == {a["id"], b["id"]}
    created = client.get(f"{INTERVIEWS}?status=created", headers=headers).json()
    assert [item["id"] for item in created["items"]] == [c["id"]]

    page = client.get(f"{INTERVIEWS}?page=1&page_size=2", headers=headers).json()
    assert len(page["items"]) == 2
    assert page["total"] == 3
    assert page["total_pages"] == 2

    assert client.get(f"{INTERVIEWS}?status=nonsense", headers=headers).status_code == 422


def test_completed_sessions_appear_in_history_with_a_score(client: TestClient) -> None:
    headers = as_learner(client)
    interview = create(client, headers, question_count=1, difficulty="Easy", topic="arrays")
    session = start(client, headers, interview["id"])
    _submit(client, headers, session["id"], 0, source=TWO_SUM_PYTHON)

    item = client.get(INTERVIEWS, headers=headers).json()["items"][0]
    assert item["status"] == "completed"
    assert item["score"] == 100
    assert item["timed_out"] is False
    assert item["completed_at"] is not None