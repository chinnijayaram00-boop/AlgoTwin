from fastapi.testclient import TestClient

from backend.tests.conftest import CATALOG_BY_DIFFICULTY, CATALOG_SIZE


def test_list_and_filter_problems(client: TestClient) -> None:
    response = client.get("/api/v1/problems", params={"difficulty": "Easy", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == CATALOG_BY_DIFFICULTY["Easy"]
    assert len(payload["items"]) == 2
    assert all(problem["difficulty"] == "Easy" for problem in payload["items"])


def test_list_paginates_the_whole_catalog(client: TestClient) -> None:
    first = client.get("/api/v1/problems", params={"limit": 5, "offset": 0}).json()
    second = client.get("/api/v1/problems", params={"limit": 5, "offset": 5}).json()

    assert first["total"] == second["total"] == CATALOG_SIZE
    assert len(first["items"]) == len(second["items"]) == 5
    assert {item["id"] for item in first["items"]}.isdisjoint(
        {item["id"] for item in second["items"]}
    )


def test_get_problem_detail(client: TestClient) -> None:
    response = client.get("/api/v1/problems/two-sum")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "two-sum"
    assert payload["starter_code"]["javascript"]
    assert payload["examples"][0]["output"] == "0 1"


def test_problem_detail_reports_the_judge_limits(client: TestClient) -> None:
    """The limits on screen are the limits the run is held to.

    Reported rather than defaulted, because a learner who is told 2000 ms and then
    fails at 2000 ms has been told something true, while a placeholder has not.
    """
    payload = client.get("/api/v1/problems/two-sum").json()

    assert payload["time_limit_ms"] > 0
    assert payload["memory_limit_mb"] > 0
    assert payload["supported_languages"]


def test_problem_detail_never_exposes_judge_data(client: TestClient) -> None:
    """No test case, hidden or visible, and no reference solution, in a public read.

    The strongest form of this guarantee is that the response shape has nowhere to
    put them. This asserts it anyway, because a future field added to
    `ProblemDetail` is exactly the change that would break it, and a test is what
    makes that change deliberate.
    """
    payload = client.get("/api/v1/problems/two-sum").json()

    for field in ("test_cases", "reference_solutions", "hints", "explanation"):
        assert field not in payload, f"{field} must not be readable from a public problem endpoint"
    assert "hidden" not in client.get("/api/v1/problems").text.lower()


def test_missing_problem_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/problems/not-a-real-problem")

    assert response.status_code == 404
