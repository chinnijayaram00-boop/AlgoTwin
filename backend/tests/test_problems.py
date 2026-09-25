from fastapi.testclient import TestClient


def test_list_and_filter_problems(client: TestClient) -> None:
    response = client.get("/api/v1/problems", params={"difficulty": "Easy", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 2
    assert all(problem["difficulty"] == "Easy" for problem in payload["items"])


def test_get_problem_detail(client: TestClient) -> None:
    response = client.get("/api/v1/problems/two-sum")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "two-sum"
    assert payload["starter_code"]["javascript"]
    assert payload["examples"][0]["output"] == "[0, 1]"


def test_missing_problem_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/problems/not-a-real-problem")

    assert response.status_code == 404
