from fastapi.testclient import TestClient

from backend.app.algorithms.frames import CELL_TONES, STATE_KINDS
from backend.app.algorithms.registry import ALGORITHM_REGISTRY, REFERENCE_LANGUAGES
from backend.app.judge.languages import LANGUAGE_IDS
from backend.tests.conftest import CATALOG_BY_DIFFICULTY, CATALOG_SIZE


def test_dashboard_summary(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_problems"] == CATALOG_SIZE
    assert payload["by_difficulty"] == CATALOG_BY_DIFFICULTY


def test_ai_status_does_not_expose_secrets(client: TestClient) -> None:
    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert "api_key" not in {key.lower() for key in payload}


def test_algorithms_endpoint_publishes_only_real_algorithms(client: TestClient) -> None:
    """The catalog cannot advertise something the platform cannot run.

    The registry's own tests check each descriptor in isolation; this one checks what
    a client actually receives. A card in the response that names no implementation
    would be the most visible possible lie -- the picker would offer it, and the
    click would fail.
    """
    response = client.get("/api/v1/algorithms")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [descriptor.id for descriptor in ALGORITHM_REGISTRY]
    for item in items:
        assert item["summary"], item["id"]
        assert item["input_hint"], item["id"]
        assert item["sample_input"], item["id"]
        assert item["state_kind"] in STATE_KINDS, item["id"]


def test_algorithms_endpoint_only_speaks_the_published_vocabularies(client: TestClient) -> None:
    """The response stays inside the closed vocabularies the renderer knows.

    A tone or layout the frontend does not recognise would fall back to its idle
    appearance, and the failure would look like "the animation is not showing the
    step" rather than "the backend sent something new".
    """
    response = client.get("/api/v1/algorithms")

    for item in response.json()["items"]:
        assert item["state_kind"] in STATE_KINDS, item["id"]
        assert item["supported_languages"] == list(REFERENCE_LANGUAGES), item["id"]


def test_supported_languages_are_languages_the_judge_actually_has(client: TestClient) -> None:
    """A language the platform cannot read must not be advertised on an algorithm card."""
    response = client.get("/api/v1/algorithms")

    for item in response.json()["items"]:
        assert set(item["supported_languages"]) <= set(LANGUAGE_IDS), item["id"]


def test_cell_tones_are_closed(client: TestClient) -> None:
    """Guard the vocabulary itself, so a new tone cannot be added by accident."""
    assert set(CELL_TONES) == {
        "idle",
        "active",
        "compare",
        "pivot",
        "swap",
        "sorted",
        "match",
        "visited",
        "frontier",
        "path",
        "blocked",
    }
