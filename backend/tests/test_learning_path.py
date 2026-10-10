"""Learning path tests.

Three properties matter more than the rest and each has its own section:
the path is *ordered* (curriculum stages, Easy to Hard inside a stage), the
path is *explainable* (the recommendation names a reason a client can switch
on), and the path belongs to *exactly one learner* (identity comes only from
the bearer token, and no response names whose it is).
"""

import pytest
from database.models import Problem, Progress, User
from database.problem_catalog import CATALOG
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas.learning_path import REASON_CODES
from backend.app.services.learning_path_service import (
    CURRICULUM_ORDER,
    build_learning_path,
    stage_key,
)
from backend.tests.conftest import CATALOG_SIZE, CATALOG_SLUGS, CATALOG_TOPICS

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

PATH = "/api/v1/learning-path"
PROGRESS = "/api/v1/progress/problems"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, payload: dict[str, str] = ALPHA) -> dict:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    return auth(register(client, payload)["access_token"])


def path_for(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get(PATH, headers=headers)
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


def recommendation(payload: dict) -> dict:
    assert payload["recommendation"] is not None, "expected a recommendation"
    return payload["recommendation"]


def _keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _keys(value)


# ------------------------------------------------------------ authentication


@pytest.mark.parametrize("headers", [{}, auth(""), auth("invalid-token"), auth("a.b.c")])
def test_the_learning_path_requires_a_valid_token(client: TestClient, headers) -> None:
    assert client.get(PATH, headers=headers).status_code == 401


def test_a_token_issued_by_registration_is_accepted(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    assert payload["total_problems"] == CATALOG_SIZE


# -------------------------------------------------------------- stage layout


def test_the_stage_order_follows_the_curriculum(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    assert [stage["title"] for stage in payload["stages"]] == list(CURRICULUM_ORDER)


def test_every_published_problem_appears_exactly_once(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    seen = [problem["problem_id"] for stage in payload["stages"] for problem in stage["problems"]]
    assert len(seen) == len(set(seen)) == CATALOG_SIZE
    assert sum(stage["problem_count"] for stage in payload["stages"]) == CATALOG_SIZE
    assert {problem["slug"] for stage in payload["stages"] for problem in stage["problems"]} == set(
        CATALOG_SLUGS
    )


def test_the_primary_topic_decides_which_stage_holds_a_problem(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    for stage in payload["stages"]:
        for problem in stage["problems"]:
            assert problem["primary_topic"] == stage["title"]
            assert stage["title"] == CATALOG_TOPICS[problem["slug"]][0]


def test_problems_inside_a_stage_run_easy_to_hard(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    order = {"Easy": 0, "Medium": 1, "Hard": 2}
    for stage in payload["stages"]:
        ranks = [order[problem["difficulty"]] for problem in stage["problems"]]
        assert ranks == sorted(ranks), stage["title"]
        assert [problem["position"] for problem in stage["problems"]] == list(
            range(len(stage["problems"]))
        )


def test_stage_keys_are_url_safe(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    for stage in payload["stages"]:
        assert stage["key"] == stage_key(stage["title"])
        assert stage["key"] and " " not in stage["key"] and stage["key"].islower()


def test_a_fresh_learner_lands_on_the_first_stage(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    assert payload["current_stage_index"] == 0
    assert payload["current_stage_title"] == "Arrays"
    assert payload["stages_complete"] == 0
    assert payload["solved_problems"] == 0
    assert payload["completion_percentage"] == 0.0
    assert payload["stages"][0]["state"] == "current"
    assert all(stage["state"] == "upcoming" for stage in payload["stages"][1:])
    assert payload["stages"][0]["prerequisite_ready"] is True
    assert all(stage["prerequisite_ready"] is False for stage in payload["stages"][1:])


def test_stage_states_fill_in_in_curriculum_order(client: TestClient) -> None:
    headers = as_learner(client)
    arrays = path_for(client, headers)["stages"][0]
    for problem in arrays["problems"]:
        mark(client, headers, problem["slug"], "solved")

    payload = path_for(client, headers)

    assert payload["stages"][0]["state"] == "complete"
    assert payload["stages"][0]["completion_percentage"] == 100.0
    assert payload["stages"][1]["state"] == "current"
    assert all(stage["state"] == "upcoming" for stage in payload["stages"][2:])
    assert payload["current_stage_index"] == 1
    assert payload["stages"][0]["prerequisite_ready"] is True


# --------------------------------------------------------- recommendation


def test_a_fresh_learner_is_offered_an_easy_problem_in_the_first_stage(
    client: TestClient,
) -> None:
    rec = recommendation(path_for(client, as_learner(client)))

    assert rec["stage_index"] == 0
    assert rec["stage_title"] == "Arrays"
    assert rec["problem"]["difficulty"] == "Easy"
    assert rec["reason_code"] == "first_step"
    assert rec["reason"] == "Start with the Arrays fundamentals."


def test_a_fresh_learners_recommendation_score_matches_the_documented_formula(
    client: TestClient,
) -> None:
    """The exposed ``score`` is the documented sum, not an opaque ranking key.

    Fresh learner, first stage: prerequisite-ready +50, stage-started +0 (no
    solve yet), problem is unstarted +0, Easy +60, stage progress +0, and the
    problem's whole topic still outstanding +10 = 120.
    """
    rec = recommendation(path_for(client, as_learner(client)))

    assert rec["score"] == 120


def test_the_recommendation_lands_in_the_current_stage(client: TestClient) -> None:
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")

    payload = path_for(client, headers)
    rec = recommendation(payload)

    assert rec["stage_index"] == payload["current_stage_index"]
    assert rec["problem"]["status"] != "solved"


def test_the_path_advances_and_says_so_after_a_solve(client: TestClient) -> None:
    headers = as_learner(client)
    first = recommendation(path_for(client, headers))
    mark(client, headers, first["problem"]["slug"], "solved")

    second = recommendation(path_for(client, headers))

    assert second["problem"]["problem_id"] != first["problem"]["problem_id"]
    assert second["problem"]["slug"] == "single-number"
    assert second["reason_code"] == "continue_stage"
    assert second["reason"] == "Continue your Arrays progression."


def test_a_solved_problem_is_never_recommended_again(client: TestClient) -> None:
    headers = as_learner(client)
    solved: set[int] = set()

    for _ in range(12):
        rec = recommendation(path_for(client, headers))
        assert rec["problem"]["problem_id"] not in solved
        assert rec["problem"]["status"] != "solved"
        mark(client, headers, rec["problem"]["slug"], "solved")
        solved.add(rec["problem"]["problem_id"])

    assert len(solved) == 12


def test_difficulty_moves_from_easy_to_medium_inside_a_stage(client: TestClient) -> None:
    headers = as_learner(client)
    easy = [
        problem["slug"]
        for problem in path_for(client, headers)["stages"][0]["problems"]
        if problem["difficulty"] == "Easy"
    ]
    for slug in easy:
        mark(client, headers, slug, "solved")

    rec = recommendation(path_for(client, headers))

    assert rec["problem"]["difficulty"] == "Medium"
    assert rec["reason_code"] == "next_difficulty"
    assert rec["reason"] == "This is the next Medium problem in your current topic."


def test_a_problem_the_learner_started_is_named_first(client: TestClient) -> None:
    headers = as_learner(client)
    mark(client, headers, "single-number", "attempted")

    rec = recommendation(path_for(client, headers))

    assert rec["problem"]["slug"] == "single-number"
    assert rec["reason_code"] == "attempted_pending"
    assert rec["reason"] == "You started Single Number but have not solved it yet."


def test_finishing_a_stage_reports_the_prerequisite_as_met(client: TestClient) -> None:
    headers = as_learner(client)
    for problem in path_for(client, headers)["stages"][0]["problems"]:
        mark(client, headers, problem["slug"], "solved")

    rec = recommendation(path_for(client, headers))

    assert rec["stage_title"] == "Strings"
    assert rec["reason_code"] == "prerequisite_met"
    assert rec["reason"] == "You completed the prerequisite fundamentals."


def test_every_reason_stays_inside_the_documented_vocabulary(client: TestClient) -> None:
    headers = as_learner(client)
    seen: set[str] = set()

    for _ in range(14):
        rec = recommendation(path_for(client, headers))
        assert rec["reason_code"] in REASON_CODES
        assert rec["reason"].strip()
        seen.add(rec["reason_code"])
        mark(client, headers, rec["problem"]["slug"], "solved")

    assert seen <= set(REASON_CODES)
    assert len(seen) >= 3


def test_the_path_is_deterministic_across_repeated_reads(client: TestClient) -> None:
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")
    mark(client, headers, "single-number", "attempted")

    first = path_for(client, headers)
    second = path_for(client, headers)

    assert first == second


def test_a_completed_catalog_has_no_recommendation(client: TestClient, db_session: Session) -> None:
    headers = as_learner(client)
    user = db_session.scalar(select(User).where(User.email == ALPHA["email"]))
    for problem in db_session.scalars(select(Problem).where(Problem.is_published.is_(True))):
        db_session.add(
            Progress(user_id=user.id, problem_id=problem.id, status="solved", attempts_count=1)
        )
    db_session.commit()

    payload = path_for(client, headers)

    assert payload["recommendation"] is None
    assert payload["current_stage_index"] is None
    assert payload["current_stage_title"] is None
    assert payload["stages_complete"] == payload["stages_total"]
    assert payload["completion_percentage"] == 100.0
    assert payload["weak_topics"] == []
    assert all(stage["state"] == "complete" for stage in payload["stages"])


# ------------------------------------------------------------- weak topics


def test_weak_topics_start_empty_and_fill_in_as_work_is_finished(client: TestClient) -> None:
    headers = as_learner(client)
    assert path_for(client, headers)["weak_topics"] == []

    mark(client, headers, "two-sum", "solved")

    payload = path_for(client, headers)

    assert "Arrays" in payload["weak_topics"]
    assert "Hash Maps" in payload["weak_topics"]
    # A topic with nothing solved is untouched, not weak.
    assert "Dynamic Programming" not in payload["weak_topics"]


def test_a_topic_that_was_only_attempted_is_reported_as_weak(client: TestClient) -> None:
    """Starting a problem without solving it still starts its topic.

    ``weak_topics`` is documented as "started but not finished". A learner who
    tried a Dynamic Programming problem and got stuck has started that topic, so
    it belongs in the worklist before the first solve lands.
    """
    headers = as_learner(client)
    assert "Dynamic Programming" not in path_for(client, headers)["weak_topics"]

    mark(client, headers, "longest-increasing-subsequence", "attempted")

    payload = path_for(client, headers)
    assert "Dynamic Programming" in payload["weak_topics"]


def test_weak_topics_never_include_a_finished_or_untouched_topic(
    client: TestClient,
) -> None:
    headers = as_learner(client)

    # An untouched catalog has no weak topics at all: nothing has been started.
    assert path_for(client, headers)["weak_topics"] == []

    # Finish the whole Stack stage (stage 3 of the curriculum) and leave Dynamic
    # Programming untouched: neither is weak, because neither has unfinished
    # *started* work.
    for problem in path_for(client, headers)["stages"][2]["problems"]:
        mark(client, headers, problem["slug"], "solved")

    payload = path_for(client, headers)
    assert "Stack" not in payload["weak_topics"]
    assert "Dynamic Programming" not in payload["weak_topics"]


# ---------------------------------------------------------- user isolation


def test_one_learner_never_sees_another_learners_path(client: TestClient) -> None:
    alpha = as_learner(client, ALPHA)
    beta = as_learner(client, BETA)
    mark(client, alpha, "two-sum", "solved")

    alpha_payload = path_for(client, alpha)
    beta_payload = path_for(client, beta)

    assert alpha_payload["solved_problems"] == 1
    assert alpha_payload["stages"][0]["solved_count"] == 1
    assert beta_payload["solved_problems"] == 0
    assert beta_payload["stages"][0]["solved_count"] == 0
    assert beta_payload["stages"][0]["problems"][0]["status"] == "not_started"
    assert alpha_payload["recommendation"]["problem"]["slug"] == "single-number"
    # Beta has done nothing, so Beta's path has not moved on at all.
    assert beta_payload["recommendation"]["problem"]["slug"] == "two-sum"
    assert beta_payload["current_stage_index"] == alpha_payload["current_stage_index"]


def test_a_path_response_never_names_the_learner(client: TestClient) -> None:
    payload = path_for(client, as_learner(client))

    assert "user_id" not in set(_keys(payload))
    assert "user" not in set(_keys(payload))


def test_the_endpoint_takes_no_identity_from_the_request(client: TestClient) -> None:
    """There is nothing to tamper with: no id in the path, the query, or a body."""
    headers = as_learner(client)

    for response in (
        client.get(PATH, params={"user_id": 999}, headers=headers),
        client.get(f"{PATH}/999", headers=headers),
        client.post(PATH, json={"user_id": 999}, headers=headers),
    ):
        assert response.status_code in (200, 404, 405), response.text
        assert response.status_code != 200 or "user_id" not in set(_keys(response.json()))


# --------------------------------------------------------------- containment


def test_the_path_never_carries_a_test_case_or_a_solution(client: TestClient) -> None:
    text = client.get(PATH, headers=as_learner(client)).text

    # Matched as JSON keys rather than as words, so a problem summary that
    # happens to read "the hints below" cannot make this fail.
    for key in (
        '"test_cases"',
        '"expected_output"',
        '"is_hidden"',
        '"reference_solutions"',
        '"starter_code"',
        '"explanation"',
        '"hints"',
    ):
        assert key not in text, key

    hidden_outputs = [
        str(case.get("expected_output", ""))
        for definition in CATALOG
        for case in definition["test_cases"]
        if case.get("is_hidden") and len(str(case.get("expected_output", ""))) >= 16
    ]
    assert hidden_outputs
    for output in hidden_outputs:
        assert output not in text


def test_an_unpublished_problem_leaves_the_path(
    client: TestClient, db_session: Session
) -> None:
    headers = as_learner(client)
    hidden = db_session.scalar(select(Problem).where(Problem.slug == "binary-search"))
    hidden.is_published = False
    db_session.commit()

    payload = path_for(client, headers)

    assert payload["total_problems"] == CATALOG_SIZE - 1
    assert "binary-search" not in {
        problem["slug"] for stage in payload["stages"] for problem in stage["problems"]
    }


def test_progress_for_an_unpublished_problem_stops_counting(
    client: TestClient, db_session: Session
) -> None:
    """A solve is only progress when the problem is part of the published path."""
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")
    before = path_for(client, headers)
    assert before["solved_problems"] == 1

    hidden = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    hidden.is_published = False
    db_session.commit()

    after = path_for(client, headers)

    assert after["total_problems"] == before["total_problems"] - 1
    assert after["solved_problems"] == 0


def test_the_endpoint_is_registered_in_the_public_api(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert PATH in schema["paths"]
    assert "get" in schema["paths"][PATH]


# ------------------------------------------------------------- pure builder


def _problem(problem_id: int, slug: str, difficulty: str, topics: list[str]) -> Problem:
    return Problem(
        id=problem_id,
        slug=slug,
        title=slug.replace("-", " ").title(),
        summary=f"Summary of {slug}.",
        difficulty=difficulty,
        topics=topics,
    )


def test_an_empty_catalog_yields_an_empty_path() -> None:
    payload = build_learning_path([], {})

    assert payload.total_problems == 0
    assert payload.stages == []
    assert payload.current_stage_index is None
    assert payload.recommendation is None
    assert payload.completion_percentage == 0.0
    assert payload.weak_topics == []


def test_a_problem_without_topics_is_filed_under_uncategorised() -> None:
    payload = build_learning_path([_problem(1, "no-topics", "Easy", [])], {})

    assert [stage.title for stage in payload.stages] == ["Uncategorised"]
    assert payload.stages[0].problems[0].primary_topic == "Uncategorised"
    assert payload.recommendation.stage_title == "Uncategorised"


def test_an_unknown_primary_topic_is_appended_after_the_known_ones() -> None:
    problems = [
        _problem(1, "arrays-one", "Easy", ["Arrays"]),
        _problem(2, "quantum-one", "Easy", ["Quantum Computing"]),
        _problem(3, "arrays-two", "Easy", ["Arrays"]),
    ]

    payload = build_learning_path(problems, {})

    assert [stage.title for stage in payload.stages] == ["Arrays", "Quantum Computing"]


def test_an_unknown_difficulty_is_ranked_last_inside_its_stage() -> None:
    problems = [
        _problem(1, "mystery", "Mystery", ["Arrays"]),
        _problem(2, "hard-one", "Hard", ["Arrays"]),
        _problem(3, "easy-one", "Easy", ["Arrays"]),
    ]

    payload = build_learning_path(problems, {})

    assert [problem.slug for problem in payload.stages[0].problems] == [
        "easy-one",
        "hard-one",
        "mystery",
    ]


def test_the_builder_ignores_the_order_of_the_rows_it_is_given() -> None:
    problems = [
        _problem(1, "one", "Easy", ["Arrays"]),
        _problem(2, "two", "Easy", ["Arrays"]),
        _problem(3, "three", "Medium", ["Arrays"]),
    ]
    progress = {2: Progress(user_id=7, problem_id=2, status="solved")}

    forward = build_learning_path(list(problems), progress)
    backward = build_learning_path(list(reversed(problems)), progress)

    assert forward == backward
    assert forward.recommendation.problem.slug == "one"


def test_weak_topics_are_capped_and_ordered_by_outstanding_then_name() -> None:
    problems: list[Problem] = []
    progress: dict[int, Progress] = {}
    problem_id = 1
    for letter in "ABCDEFGH":
        for offset in range(2):
            problems.append(_problem(problem_id, f"p{problem_id}", "Easy", [f"Topic {letter}"]))
            if offset == 1:
                progress[problem_id] = Progress(
                    user_id=1, problem_id=problem_id, status="solved", attempts_count=1
                )
            problem_id += 1

    payload = build_learning_path(problems, progress)

    # Every topic has exactly one solve and one gap, so "outstanding" ties at
    # one and the cap keeps the alphabetically-first six topics.
    assert payload.weak_topics == [f"Topic {letter}" for letter in "ABCDEF"]


def test_completion_percentage_is_rounded_to_two_decimals() -> None:
    problems = [_problem(i, f"p{i}", "Easy", ["Arrays"]) for i in range(1, 4)]
    progress = {1: Progress(user_id=1, problem_id=1, status="solved", attempts_count=1)}

    payload = build_learning_path(problems, progress)

    assert payload.completion_percentage == 33.33
    assert payload.stages[0].completion_percentage == 33.33


def test_a_non_list_topics_column_is_filed_under_uncategorised() -> None:
    problem = Problem(
        id=1,
        slug="odd",
        title="Odd Storage",
        summary="Summary.",
        difficulty="Easy",
        topics="Arrays",
    )

    payload = build_learning_path([problem], {})

    assert [stage.title for stage in payload.stages] == ["Uncategorised"]
    assert payload.stages[0].problems[0].topics == []


def test_non_string_topic_entries_are_filtered_out() -> None:
    problem = _problem(1, "mixed", "Easy", ["Arrays", {"bad": 1}, None, 3, True])

    payload = build_learning_path([problem], {})

    # Dicts, Nones, and booleans drop out; ints are coerced to their labels so
    # the path can still make a decision from a dirty row.
    assert payload.stages[0].problems[0].topics == ["Arrays", "3"]


def test_a_dirty_attempts_count_is_clamped_to_zero() -> None:
    problems = [_problem(1, "one", "Easy", ["Arrays"])]

    for raw in (-5, None):
        progress = {1: Progress(user_id=1, problem_id=1, status="attempted", attempts_count=raw)}
        payload = build_learning_path(problems, progress)

        assert payload.stages[0].problems[0].attempts_count == 0
        assert payload.stages[0].attempted_count == 1


def test_a_legacy_status_is_read_as_solved_in_the_path() -> None:
    """A row written before the status vocabulary was enforced still counts."""
    problems = [
        _problem(1, "one", "Easy", ["Arrays"]),
        _problem(2, "two", "Easy", ["Arrays"]),
    ]
    progress = {1: Progress(user_id=1, problem_id=1, status="completed", attempts_count=1)}

    payload = build_learning_path(problems, progress)

    assert payload.stages[0].solved_count == 1
    assert payload.solved_problems == 1
    assert payload.recommendation.problem.problem_id == 2
