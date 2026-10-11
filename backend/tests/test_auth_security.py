"""Regression tests for auth throttling and the security headers middleware.

Both features exist to answer findings from the security audit:

* `/auth/login` spent an Argon2id verify (or timing-equalizer hash) on every
  well-formed request and `/auth/register` spent an Argon2id hash, with no
  ceiling anywhere -- a scriptable brute-force surface for a known account and
  an unauthenticated compute-DoS vector.
* API responses carried no `Cache-Control`, so a browser could replay a signed
  JWT from back-history, and no hardening headers (`X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`).

These tests build their own app with a small budget so the behaviour is
deterministic without touching the counters other tests share.
"""

import pytest
from database.seed import DEMO_USER_EMAIL, seed_demo_data
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.tests.conftest import TEST_JWT_ALGORITHM, TEST_JWT_SECRET
from backend.tests.test_auth import REGISTRATION


@pytest.fixture
def throttled_app_client(db_engine) -> TestClient:
    """A client wired to the private DB with throttling enabled and a tiny budget.

    Replacing ``get_settings`` also gives this app its own limiter instance (the
    process-wide limiter is keyed by the effective limits), so these tests never
    interfere with the counters other tests share.
    """
    with Session(db_engine) as session:
        seed_demo_data(session)

    def override_get_db():
        with Session(db_engine) as session:
            yield session

    def override_settings() -> Settings:
        return Settings(
            jwt_secret_key=TEST_JWT_SECRET,
            jwt_algorithm=TEST_JWT_ALGORITHM,
            access_token_expire_minutes=60,
            auth_throttle_enabled=True,
            auth_max_login_failures=3,
            auth_login_window_seconds=60,
            auth_max_registrations=2,
            auth_register_window_seconds=60,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def _wrong_password(email: str = DEMO_USER_EMAIL) -> dict[str, str]:
    return {"email": email, "password": "wrong-password"}


def _exhaust_login_budget(client: TestClient, email: str = DEMO_USER_EMAIL) -> TestClient:
    """Fail logins until the next attempt would be refused with 429."""
    for _ in range(3):
        assert client.post("/api/v1/auth/login", json=_wrong_password(email)).status_code == 401
    return client


# ----------------------------------------------------------------- throttle


def test_login_blocks_after_repeated_failures(throttled_app_client: TestClient) -> None:
    """Three wrong passwords, then the attempt is refused with a wait window."""

    wrong = _wrong_password()
    # The first three failures are allowed through to the route's 401.
    assert throttled_app_client.post("/api/v1/auth/login", json=wrong).status_code == 401
    assert throttled_app_client.post("/api/v1/auth/login", json=wrong).status_code == 401
    assert throttled_app_client.post("/api/v1/auth/login", json=wrong).status_code == 401

    response = throttled_app_client.post("/api/v1/auth/login", json=wrong)
    assert response.status_code == 429
    assert "too many" in response.json()["detail"].lower()
    # Retry-After must be present and meaningfully bounded by the window.
    assert 1 <= int(response.headers["Retry-After"]) <= 60


def test_login_block_is_scoped_per_account(throttled_app_client: TestClient) -> None:
    """Exhausting one account's budget must not lock a different account out."""

    _exhaust_login_budget(throttled_app_client)
    assert (
        throttled_app_client.post(
            "/api/v1/auth/login", json=_wrong_password()
        ).status_code
        == 429
    )

    # A different address (even one that does not exist) still gets a normal
    # failure, not a 429.
    response = throttled_app_client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_register_blocks_after_repeated_attempts(throttled_app_client: TestClient) -> None:
    """Registration attempt volume from one client is capped per window."""

    assert (
        throttled_app_client.post("/api/v1/auth/register", json=REGISTRATION).status_code
        == 201
    )

    # A second attempt for the *same* address (case-variant) still costs a hash
    # and counts.
    duplicate = {**REGISTRATION, "email": REGISTRATION["email"].upper()}
    assert (
        throttled_app_client.post("/api/v1/auth/register", json=duplicate).status_code
        == 409
    )

    response = throttled_app_client.post("/api/v1/auth/register", json=REGISTRATION)
    assert response.status_code == 429
    assert "too many registration attempts" in response.json()["detail"].lower()


def test_login_counter_ignores_spoofable_headers(throttled_app_client: TestClient) -> None:
    """X-Forwarded-For must not reset a block.

    The limiter keys on the client IP as FastAPI reports it; trusting an
    unauthenticated header would let an attacker wipe its own counter after
    every failure, which is no counter at all.
    """
    _exhaust_login_budget(throttled_app_client)
    assert (
        throttled_app_client.post(
            "/api/v1/auth/login", json=_wrong_password()
        ).status_code
        == 429
    )
    # A spoofed forwarding address changes nothing: still blocked.
    response = throttled_app_client.post(
        "/api/v1/auth/login",
        json=_wrong_password(),
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert response.status_code == 429


def test_valid_credentials_pass_before_the_budget_is_exhausted(
    throttled_app_client: TestClient,
) -> None:
    """Failures must not consume the success path: the right password still works."""

    # Two wrong passwords, then the correct one -- all inside the window.
    throttled_app_client.post("/api/v1/auth/login", json=_wrong_password())
    throttled_app_client.post("/api/v1/auth/login", json=_wrong_password())
    from database.seed import DEMO_USER_PASSWORD

    response = throttled_app_client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_USER_EMAIL, "password": DEMO_USER_PASSWORD},
    )
    assert response.status_code == 200


# ----------------------------------------------------------------- security headers


def test_hardening_headers_are_present_on_public_responses(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_authenticated_responses_are_not_cached(client: TestClient) -> None:
    from backend.tests.test_auth import register

    token = register(client)["access_token"]
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"


def test_public_responses_remain_cacheable(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert "no-store" not in response.headers.get("Cache-Control", "")