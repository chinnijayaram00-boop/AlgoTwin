from fastapi.testclient import TestClient


def test_dashboard_summary(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_problems"] == 4
    assert payload["by_difficulty"]["Easy"] == 3
    assert payload["by_difficulty"]["Medium"] == 1


def test_ai_status_does_not_expose_secrets(client: TestClient) -> None:
    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert "api_key" not in {key.lower() for key in payload}
