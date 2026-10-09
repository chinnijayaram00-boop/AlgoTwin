"""Personalized coach: profile derivation, grounded mentor guidance, fallbacks.

The profile tests defend that the coach is *derived*, not invented: every signal
traces to a stored row, and the counts match the analytics endpoint that reads the
same rows. The mentor tests defend the promise that asking for advice always
returns advice -- a learner with a working provider gets the model's text, and a
learner on a deployment with no provider, or over their budget, or hitting a
broken or slow provider, gets deterministic text that says so.

Two design choices get their own assertions because they are the reason this
feature was built the way it was:

* mentor guidance is *ephemeral* -- a mentor call stores no ``ai_insights`` row,
  so advice always reflects the profile the request just read;
* the request body cannot carry facts -- ``extra="forbid"`` plus a closed
  ``focus`` vocabulary means a caller can select an emphasis and nothing else.
"""

from typing import Any, Iterator

import pytest
from database.models import AIInsight
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.ai import errors as ai_errors
from backend.app.ai.providers import fake as fake_provider
from backend.app.core.config import Settings
from backend.app.services import ai_service
from backend.tests.conftest import CATALOG_SIZE

API = "/api/v1"
PROFILE = f"{API}/personalization/profile"
MENTOR = f"{API}/personalization/mentor"
ANALYTICS = f"{API}/analytics/summary"

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

TEST_SECRET = "test-only-jwt-secret-0123456789abcdef"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, payload: dict[str, str] = ALPHA) -> dict:
    response = client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    return auth(register(client, payload)["access_token"])


def problem_id(client: TestClient, slug: str) -> int:
    response = client.get(f"{API}/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def mark(client: TestClient, headers: dict[str, str], slug: str, status: str) -> None:
    response = client.put(
        f"{API}/progress/problems/{problem_id(client, slug)}",
        json={"status": status},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def profile(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get(PROFILE, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _keys(value)


def ai_settings(**overrides: Any) -> Settings:
    return Settings(
        jwt_secret_key=TEST_SECRET,
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        **overrides,
    )


def build_client(db_engine, provider=None, **setting_overrides: Any) -> TestClient:
    """A TestClient whose settings and AI provider are pinned by the caller.

    Configuration is injected through the same dependencies a deployment uses, so
    the routes resolve the provider and the limits exactly as the registry would.
    Overriding ``get_ai_provider`` directly rather than patching a constructor keeps
    the production wiring under test.
    """
    from database.seed import seed_demo_data
    from fastapi.testclient import TestClient as _TestClient

    from backend.app.api.dependencies import get_ai_provider
    from backend.app.core.config import get_settings
    from backend.app.db.session import get_db
    from backend.app.main import app

    with Session(db_engine) as session:
        seed_demo_data(session)

    def override_get_db() -> Iterator[Session]:
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: ai_settings(**setting_overrides)
    if provider is not None:
        app.dependency_overrides[get_ai_provider] = lambda: provider
    return _TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_limiters() -> Iterator[None]:
    """Clear the process-wide rate limiter around every test.

    The limiter is deliberately shared across requests; without this reset one
    test's provider calls would count against the next test's budget.
    """
    ai_service.reset_limiters()
    yield
    ai_service.reset_limiters()


@pytest.fixture(autouse=True)
def _clean_dependency_overrides() -> Iterator[None]:
    """Leave no overrides or cached providers behind for the next test."""
    from backend.app.main import app

    app.dependency_overrides.clear()
    app.state.ai_services = {}
    yield
    app.dependency_overrides.clear()
    app.state.ai_services = {}


# ----------------------------------------------------------------- profile


def test_the_profile_requires_a_valid_token(client: TestClient) -> None:
    for headers in ({}, auth(""), auth("invalid-token"), auth("a.b.c")):
        assert client.get(PROFILE, headers=headers).status_code == 401


def test_the_mentor_endpoint_requires_a_valid_token(client: TestClient) -> None:
    assert client.post(MENTOR, json={}).status_code == 401
    assert client.post(MENTOR, json={}, headers=auth("nope")).status_code == 401


def test_a_fresh_profile_names_where_to_start(client: TestClient) -> None:
    payload = profile(client, as_learner(client))

    assert payload["overview"]["solved"] == 0
    assert payload["overview"]["total_problems"] == CATALOG_SIZE
    assert payload["overview"]["not_started"] == CATALOG_SIZE
    assert [signal["code"] for signal in payload["weaknesses"]] == ["not_started"]
    assert payload["recommendations"], "a fresh learner should still be pointed at a problem"
    assert payload["recommendations"][0]["reason_code"] == "first_step"
    assert payload["recommendations"][0]["status"] == "not_started"


def test_the_profile_reflects_real_stored_progress(client: TestClient) -> None:
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")

    payload = profile(client, headers)

    assert payload["overview"]["solved"] == 1
    assert "solved_volume" in {signal["code"] for signal in payload["strengths"]}
    slugs = [item["slug"] for item in payload["recommendations"]]
    assert slugs
    assert "two-sum" not in slugs
    # The first recommendation is the learning path's own choice, reason and all.
    assert payload["recommendations"][0]["slug"] == "single-number"
    assert payload["recommendations"][0]["reason_code"] == "continue_stage"


def test_the_profile_and_the_analytics_endpoint_agree(client: TestClient) -> None:
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")

    summary = client.get(ANALYTICS, headers=headers).json()
    payload = profile(client, headers)

    assert payload["overview"]["solved"] == summary["overview"]["solved"]
    assert payload["overview"]["total_problems"] == summary["overview"]["total_problems"]
    assert payload["overview"]["acceptance_rate"] == summary["overview"]["acceptance_rate"]
    assert payload["as_of"] == summary["as_of"]


def test_the_profile_is_deterministic_across_reads(client: TestClient) -> None:
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")
    mark(client, headers, "single-number", "attempted")

    assert profile(client, headers) == profile(client, headers)


def test_the_profile_never_names_the_learner(client: TestClient) -> None:
    payload = profile(client, as_learner(client))

    keys = set(_keys(payload))
    assert "user_id" not in keys
    assert "user" not in keys


# ------------------------------------------------------------------ mentor


def test_mentor_uses_the_provider_when_one_is_configured(db_engine) -> None:
    client = build_client(db_engine, ai_provider="fake")
    headers = as_learner(client)

    response = client.post(MENTOR, json={}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fallback"] is False
    assert body["degraded_reason"] is None
    assert body["provider"] == "fake"
    assert body["is_demo_output"] is True
    # The deterministic fake's text, and the profile that grounded it.
    assert "fake" in body["content"]
    assert body["grounding"]["focus"] == "overview"
    assert body["grounding"]["total_problems"] == CATALOG_SIZE


def test_mentor_stores_nothing_because_guidance_is_ephemeral(
    db_engine, db_session: Session
) -> None:
    """Advice is recomputed per request, so no ``ai_insights`` row is written."""
    client = build_client(db_engine, ai_provider="fake")
    headers = as_learner(client)

    assert client.post(MENTOR, json={}, headers=headers).status_code == 200

    count = db_session.scalar(select(func.count()).select_from(AIInsight))
    assert count == 0


def test_mentor_always_answers_without_a_provider(db_engine) -> None:
    """A deployment with AI switched off still gives the learner advice."""
    client = build_client(db_engine, ai_provider="disabled")
    headers = as_learner(client)
    mark(client, headers, "two-sum", "solved")

    response = client.post(MENTOR, json={}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fallback"] is True
    assert body["degraded_reason"] == "provider_not_configured"
    assert body["provider"] == "deterministic"
    assert body["model"] == "profile-rules"
    assert body["is_demo_output"] is False
    # The fallback is real coaching derived from the profile, not an empty string.
    assert body["content"].strip()
    assert "## Next step" in body["content"]
    # And it reflects this learner's state: one problem solved.
    assert "**1 of" in body["content"]


@pytest.mark.parametrize(
    "raised,expected_reason",
    [
        (ai_errors.AIProviderError("unwell"), "provider_error"),
        (ai_errors.AIProviderTimeoutError("slow"), "provider_timeout"),
    ],
)
def test_mentor_falls_back_when_the_provider_fails(
    db_engine, raised: Exception, expected_reason: str
) -> None:
    failing = fake_provider.FakeAIProvider(ai_settings(ai_provider="fake"), error=raised)
    client = build_client(db_engine, provider=failing, ai_provider="fake")
    headers = as_learner(client)

    response = client.post(MENTOR, json={}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fallback"] is True
    assert body["degraded_reason"] == expected_reason
    assert body["provider"] == "deterministic"
    # The provider really was asked before the fallback was chosen.
    assert failing.calls


def test_mentor_falls_back_when_the_learner_is_rate_limited(db_engine) -> None:
    client = build_client(db_engine, ai_provider="fake", ai_rate_limit_per_minute=1)
    headers = as_learner(client)

    first = client.post(MENTOR, json={}, headers=headers)
    second = client.post(MENTOR, json={}, headers=headers)

    assert first.status_code == 200, first.text
    assert first.json()["fallback"] is False
    assert second.status_code == 200, second.text
    assert second.json()["fallback"] is True
    assert second.json()["degraded_reason"] == "rate_limited"


def test_mentor_echoes_the_requested_focus(db_engine) -> None:
    client = build_client(db_engine, ai_provider="fake")
    headers = as_learner(client)

    response = client.post(MENTOR, json={"focus": "strengths"}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["focus"] == "strengths"
    assert response.json()["grounding"]["focus"] == "strengths"


def test_the_mentor_body_is_optional(db_engine) -> None:
    """No body means the default focus, not a 422."""
    client = build_client(db_engine, ai_provider="fake")
    headers = as_learner(client)

    response = client.post(MENTOR, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["focus"] == "overview"


@pytest.mark.parametrize(
    "payload",
    [
        {"focus": "nonsense"},
        {"user_id": 999},
        {"code": "print('inject')"},
        {"strengths": ["made up"]},
    ],
)
def test_the_mentor_request_cannot_carry_facts_or_unknown_fields(
    db_engine, payload: dict
) -> None:
    """Only a closed ``focus`` is accepted; nothing else can enter the prompt."""
    client = build_client(db_engine, ai_provider="fake")
    headers = as_learner(client)

    assert client.post(MENTOR, json=payload, headers=headers).status_code == 422


def test_the_profile_never_carries_hidden_test_data(client: TestClient) -> None:
    """The profile is counts and catalog labels, never case data."""
    text = client.get(PROFILE, headers=as_learner(client)).text

    for key in ('"test_cases"', '"expected_output"', '"is_hidden"', '"reference_solutions"'):
        assert key not in text, key


def test_the_mentor_grounding_is_bounded_scalars_and_short_lists(db_engine) -> None:
    client = build_client(db_engine, ai_provider="fake")
    headers = as_learner(client)

    grounding = client.post(MENTOR, json={}, headers=headers).json()["grounding"]

    for field in ("solved", "total_problems", "acceptance_rate", "focus"):
        assert field in grounding
    assert isinstance(grounding["strengths"], list)
    assert isinstance(grounding["weaknesses"], list)
    assert len(grounding["strengths"]) <= 6
    assert len(grounding["weaknesses"]) <= 6


def test_one_learner_never_sees_another_learners_profile(client: TestClient) -> None:
    alpha = as_learner(client, ALPHA)
    beta = as_learner(client, BETA)
    mark(client, alpha, "two-sum", "solved")

    assert profile(client, alpha)["overview"]["solved"] == 1
    assert profile(client, beta)["overview"]["solved"] == 0


def test_the_endpoints_are_registered_in_the_public_api(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert PROFILE in schema["paths"]
    assert "get" in schema["paths"][PROFILE]
    assert MENTOR in schema["paths"]
    assert "post" in schema["paths"][MENTOR]
