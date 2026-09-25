"""Authentication endpoint tests.

Covers registration, login, token issuance/validation, protected-route access,
logout, and cross-user isolation.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from database.models import User
from database.seed import seed_demo_data
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.tests.conftest import TEST_JWT_SECRET

REGISTRATION = {
    "name": "Test Learner",
    "email": "test.learner@example.com",
    "password": "correct-horse-battery-staple",
}
SECOND_USER = {
    "name": "Second Learner",
    "email": "second.learner@example.com",
    "password": "another-strong-passphrase",
}
PROTECTED = "/api/v1/auth/me"


def register(client: TestClient, payload: dict[str, str] | None = None) -> dict:
    response = client.post("/api/v1/auth/register", json=payload or REGISTRATION)
    assert response.status_code == 201, response.text
    return response.json()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------- register


def test_registration_returns_token_and_safe_profile(client: TestClient) -> None:
    payload = register(client)

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_in"] == 3600
    assert payload["user"]["name"] == REGISTRATION["name"]
    assert payload["user"]["email"] == REGISTRATION["email"]
    assert "password" not in payload["user"]
    assert "password_hash" not in payload["user"]


def test_registration_normalizes_email_and_name(client: TestClient, db_session: Session) -> None:
    payload = register(
        client,
        {
            "name": "  Ada   Lovelace  ",
            "email": "  Ada.Lovelace@Example.COM ",
            "password": REGISTRATION["password"],
        },
    )

    assert payload["user"]["email"] == "ada.lovelace@example.com"
    assert payload["user"]["name"] == "Ada Lovelace"

    stored = db_session.scalar(select(User).where(User.email == "ada.lovelace@example.com"))
    assert stored is not None


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTRATION, "email": REGISTRATION["email"].upper()},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_duplicate_registration_rejects_whitespace_variant(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTRATION, "email": f"  {REGISTRATION['email']}  "},
    )

    assert response.status_code == 409


def test_registration_rejects_invalid_payloads(client: TestClient) -> None:
    cases = {
        "missing name": {"email": "a@example.com", "password": REGISTRATION["password"]},
        "blank name": {"name": "   ", "email": "a@example.com", "password": REGISTRATION["password"]},
        "malformed email": {"name": "A", "email": "not-an-email", "password": REGISTRATION["password"]},
        "empty email": {"name": "A", "email": "", "password": REGISTRATION["password"]},
        "missing password": {"name": "A", "email": "a@example.com"},
        "password too short": {"name": "A", "email": "a@example.com", "password": "short"},
        "blank password": {"name": "A", "email": "a@example.com", "password": "          "},
        "password too long": {"name": "A", "email": "a@example.com", "password": "x" * 200},
        "name too long": {"name": "x" * 200, "email": "a@example.com", "password": REGISTRATION["password"]},
        "nothing": {},
    }

    for label, payload in cases.items():
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422, f"{label} -> {response.status_code} {response.text}"


def test_rejected_registration_creates_no_user(client: TestClient, db_session: Session) -> None:
    client.post("/api/v1/auth/register", json={"name": "A", "email": "bad", "password": "short"})

    assert db_session.scalars(select(User)).all() == []


# ------------------------------------------------------------ password hashing


def test_stored_password_is_argon2id_and_salted(client: TestClient, db_session: Session) -> None:
    register(client)

    stored = db_session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert stored is not None
    assert stored.password_hash is not None
    assert stored.password_hash != REGISTRATION["password"]
    assert REGISTRATION["password"] not in stored.password_hash
    assert stored.password_hash.startswith("$argon2id$")


def test_same_password_hashes_differently_each_time() -> None:
    first = hash_password("identical-password")
    second = hash_password("identical-password")

    assert first != second, "hashes must be salted per call"
    assert verify_password("identical-password", first)
    assert verify_password("identical-password", second)


def test_verify_password_rejects_wrong_and_malformed_hashes() -> None:
    stored = hash_password("correct-horse-battery-staple")

    assert verify_password("correct-horse-battery-staple", stored) is True
    assert verify_password("wrong-password", stored) is False
    assert verify_password("correct-horse-battery-staple", None) is False
    assert verify_password("correct-horse-battery-staple", "") is False
    assert verify_password("correct-horse-battery-staple", "not-a-hash") is False
    assert verify_password("correct-horse-battery-staple", "plaintext-password") is False


def test_login_succeeds_against_the_stored_hash(client: TestClient, db_session: Session) -> None:
    register(client)

    stored = db_session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert stored is not None

    response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200
    assert verify_password(REGISTRATION["password"], stored.password_hash)


# ----------------------------------------------------------------- login errors


def test_login_succeeds(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == REGISTRATION["email"]
    assert "password_hash" not in body["user"]


def test_login_is_case_insensitive_on_email(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"].upper(), "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200


def test_login_rejects_wrong_password(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "definitely-wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_login_rejects_nonexistent_account(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": REGISTRATION["password"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_does_not_reveal_whether_the_account_exists(client: TestClient) -> None:
    """A wrong password and an unknown address must be indistinguishable."""
    register(client)

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "definitely-wrong"},
    )
    unknown_account = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": REGISTRATION["password"]},
    )

    assert wrong_password.status_code == unknown_account.status_code == 401
    assert wrong_password.json() == unknown_account.json()


def test_login_rejects_invalid_payloads(client: TestClient) -> None:
    for payload in (
        {"email": "not-an-email", "password": REGISTRATION["password"]},
        {"email": "a@example.com", "password": ""},
        {"password": REGISTRATION["password"]},
        {},
    ):
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 422, f"{payload} -> {response.text}"


def test_login_rejects_account_with_unusable_password_hash(
    client: TestClient,
    db_session: Session,
) -> None:
    """A legacy account with no usable hash must 401, never 500."""
    db_session.add(User(name="Legacy", email="legacy@example.com", password_hash="not-a-real-hash"))
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy@example.com", "password": REGISTRATION["password"]},
    )

    assert response.status_code == 401


# -------------------------------------------------------------------- jwt flows


def test_valid_jwt_is_accepted(client: TestClient) -> None:
    registration = register(client)
    token = registration["access_token"]

    response = client.get(PROTECTED, headers=auth(token))

    assert response.status_code == 200
    assert response.json()["id"] == registration["user"]["id"]
    assert response.json()["email"] == REGISTRATION["email"]


def test_token_payload_carries_only_the_user_id(client_with_known_secret: TestClient) -> None:
    registration = register(client_with_known_secret)
    claims = jwt.decode(
        registration["access_token"],
        TEST_JWT_SECRET,
        algorithms=["HS256"],
    )

    assert claims["type"] == "access"
    assert claims["sub"] == str(registration["user"]["id"])
    assert "email" not in claims
    assert "password" not in claims
    assert "password_hash" not in claims
    assert claims["jti"]
    assert claims["exp"] > claims["iat"]


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("", id="empty"),
        pytest.param("invalid-token", id="garbage"),
        pytest.param("a.b.c", id="not-a-jwt"),
        pytest.param("Bearer token", id="prefixed-by-mistake"),
    ],
)
def test_invalid_jwt_is_rejected(client: TestClient, token: str) -> None:
    assert client.get(PROTECTED, headers=auth(token)).status_code == 401


def test_missing_jwt_is_rejected(client: TestClient) -> None:
    response = client.get(PROTECTED)

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials."


def test_malformed_authorization_header_is_rejected(client: TestClient) -> None:
    for header in ("", "Bearer", "Token abc", "bearer", "Basic dXNlcjpwYXNz"):
        response = client.get(PROTECTED, headers={"Authorization": header})
        assert response.status_code == 401, f"{header!r} -> {response.status_code}"


def test_token_signed_with_another_secret_is_rejected(client_with_known_secret: TestClient) -> None:
    register(client_with_known_secret)
    forged = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            "type": "access",
        },
        "a-completely-different-secret-of-sufficient-length",
        algorithm="HS256",
    )

    response = client_with_known_secret.get(PROTECTED, headers=auth(forged))

    assert response.status_code == 401


def test_expired_token_is_rejected(client_with_known_secret: TestClient) -> None:
    register(client_with_known_secret)
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    response = client_with_known_secret.get(PROTECTED, headers=auth(expired))

    assert response.status_code == 401


def test_token_for_deleted_user_is_rejected(client_with_known_secret: TestClient, db_session: Session) -> None:
    registration = register(client_with_known_secret)
    token = registration["access_token"]

    user = db_session.get(User, registration["user"]["id"])
    assert user is not None
    db_session.delete(user)
    db_session.commit()

    assert client_with_known_secret.get(PROTECTED, headers=auth(token)).status_code == 401


def test_token_with_wrong_type_is_rejected(client_with_known_secret: TestClient) -> None:
    register(client_with_known_secret)
    refresh_like = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            "type": "refresh",
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    assert client_with_known_secret.get(PROTECTED, headers=auth(refresh_like)).status_code == 401


def test_token_signed_with_another_algorithm_is_rejected(client_with_known_secret: TestClient) -> None:
    register(client_with_known_secret)
    unsigned = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            "type": "access",
        },
        key="",
        algorithm="none",
    )

    assert client_with_known_secret.get(PROTECTED, headers=auth(unsigned)).status_code == 401
    assert TEST_JWT_SECRET  # the configured secret is never accepted as "none"


def test_tampered_token_payload_is_rejected(client: TestClient) -> None:
    registration = register(client)
    token = registration["access_token"]
    header, payload, signature = token.split(".")

    # Re-point the subject at a different user while keeping the old signature.
    forged_payload = jwt.encode(
        {"sub": "999"}, "a-dummy-signing-key-of-sufficient-length", algorithm="HS256"
    ).split(".")[1]
    tampered = f"{header}.{forged_payload}.{signature}"

    assert client.get(PROTECTED, headers=auth(tampered)).status_code == 401


def test_auth_endpoints_report_missing_jwt_configuration(db_engine) -> None:
    """With no JWT secret configured the API must 503, not crash or authenticate."""
    from backend.app.core.config import get_settings
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

        # A credential that is present but cannot be validated is a
        # misconfiguration (503), not an authentication failure (401).
        assert client.get(PROTECTED, headers=auth("some-token")).status_code == 503
        assert client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": REGISTRATION["password"]},
        ).status_code == 503
        assert client.post("/api/v1/auth/register", json=REGISTRATION).status_code == 503

        # With no credential at all, 401 remains the correct answer.
        assert client.get(PROTECTED).status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------- protected behaviour


def test_protected_route_requires_valid_token(client: TestClient) -> None:
    assert client.get(PROTECTED).status_code == 401
    assert client.get(PROTECTED, headers=auth("invalid-token")).status_code == 401


def test_public_endpoints_need_no_token(client: TestClient) -> None:
    for path in ("/api/v1/health", "/api/v1/health/ready", "/api/v1/problems", "/api/v1/algorithms"):
        assert client.get(path).status_code == 200, f"{path} should stay public"


def test_logout_requires_authentication_and_returns_no_content(client: TestClient) -> None:
    registration = register(client)
    token = registration["access_token"]

    assert client.post("/api/v1/auth/logout").status_code == 401
    response = client.post("/api/v1/auth/logout", headers=auth(token))

    assert response.status_code == 204
    assert response.content == b""


def test_logout_rejects_an_invalid_token(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers=auth("invalid-token")).status_code == 401


# -------------------------------------------------------------- user isolation


def test_each_token_resolves_only_to_its_own_user(client: TestClient) -> None:
    first = register(client)
    second = register(client, SECOND_USER)

    first_me = client.get(PROTECTED, headers=auth(first["access_token"])).json()
    second_me = client.get(PROTECTED, headers=auth(second["access_token"])).json()

    assert first_me["id"] == first["user"]["id"]
    assert second_me["id"] == second["user"]["id"]
    assert first_me["id"] != second_me["id"]
    assert first_me["email"] == REGISTRATION["email"]
    assert second_me["email"] == SECOND_USER["email"]


def test_a_user_cannot_act_as_another_user_via_headers(client: TestClient) -> None:
    first = register(client)
    second = register(client, SECOND_USER)

    for header_name in ("X-User-Id", "X-User", "X-Forwarded-User"):
        response = client.get(PROTECTED, headers={**auth(first["access_token"]), header_name: str(second["user"]["id"])})
        assert response.json()["id"] == first["user"]["id"], f"{header_name} must not influence identity"


def test_a_user_cannot_read_another_users_email(client: TestClient) -> None:
    register(client)
    second = register(client, SECOND_USER)

    body = client.get(PROTECTED, headers=auth(second["access_token"])).text

    assert second["user"]["email"] in body
    assert REGISTRATION["email"] not in body


def test_registration_cannot_overwrite_an_existing_account(client: TestClient) -> None:
    first = register(client)

    hijack = client.post(
        "/api/v1/auth/register",
        json={"name": "Attacker", "email": REGISTRATION["email"], "password": "attacker-password"},
    )

    assert hijack.status_code == 409
    me = client.get(PROTECTED, headers=auth(first["access_token"])).json()
    assert me["name"] == first["user"]["name"]
    assert me["email"] == first["user"]["email"]


# ------------------------------------------------------------- secret hygiene


def test_no_endpoint_exposes_password_material(client: TestClient) -> None:
    """Sweep the live API: no response body may contain credential material."""
    registration = register(client)
    token = registration["access_token"]

    probes = [
        ("get", "/api/v1/auth/me", None),
        ("get", "/api/v1/auth/me", token),
        ("get", "/api/v1/health", None),
        ("get", "/api/v1/health/ready", None),
        ("get", "/api/v1/problems", None),
        ("get", "/api/v1/dashboard/summary", None),
        ("get", "/api/v1/algorithms", None),
    ]

    for method, path, probe_token in probes:
        headers = auth(probe_token) if probe_token else {}
        response = client.request(method, path, headers=headers)
        body = response.text
        assert "password_hash" not in body, f"{path} leaked password_hash"
        assert REGISTRATION["password"] not in body, f"{path} leaked the plaintext password"


CREDENTIAL_FIELDS = {"password_hash", "password", "hashed_password", "hashedPassword"}


def _referenced_schema_names(node, into: set[str]) -> None:
    """Collect every component schema name referenced anywhere under ``node``."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            into.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _referenced_schema_names(value, into)
    elif isinstance(node, list):
        for value in node:
            _referenced_schema_names(value, into)


def _property_names(schema: dict) -> set[str]:
    return set(schema.get("properties", {}))


def test_no_response_schema_declares_credential_fields(client: TestClient) -> None:
    """No schema reachable from a response may carry credential material.

    Request bodies such as ``RegisterRequest`` legitimately accept a password,
    so they are excluded: this asserts specifically about what comes back out.
    """
    document = client.get("/openapi.json").json()
    schemas = document["components"]["schemas"]

    request_only: set[str] = set()
    for operation in document["paths"].values():
        for definition in operation.values():
            if not isinstance(definition, dict):
                continue
            if "requestBody" in definition:
                _referenced_schema_names(definition["requestBody"], request_only)
            for parameter in definition.get("parameters", []):
                if isinstance(parameter, dict) and parameter.get("in") == "query":
                    _referenced_schema_names(parameter, request_only)

    offenders = [
        f"{name}.{field}"
        for name, schema in schemas.items()
        if name not in request_only
        for field in _property_names(schema) & CREDENTIAL_FIELDS
    ]
    assert offenders == [], f"credential fields exposed in a response schema: {offenders}"


def test_user_profile_schema_excludes_the_password_hash(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]

    assert "UserProfile" in schemas
    assert _property_names(schemas["UserProfile"]) == {"id", "name", "email", "created_at", "updated_at"}


def test_no_response_schema_reaches_the_user_model(client: TestClient) -> None:
    """``UserProfile`` must be a projection, not the ORM model itself."""
    document = client.get("/openapi.json").json()

    assert "User" not in document["components"]["schemas"]
    assert "HTTPValidationError" in document["components"]["schemas"]


def test_access_token_never_contains_the_password(client: TestClient) -> None:
    registration = register(client)

    assert REGISTRATION["password"] not in registration["access_token"]


def test_create_access_token_rejects_a_non_positive_user_id(settings: Settings) -> None:
    for bad_id in (0, -1):
        with pytest.raises(ValueError):
            create_access_token(bad_id, settings)


def test_decode_access_token_round_trips(settings: Settings) -> None:
    token = create_access_token(42, settings)

    assert decode_access_token(token, settings) == 42
