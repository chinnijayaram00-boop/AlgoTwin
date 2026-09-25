from fastapi.testclient import TestClient

REGISTRATION = {
    "name": "Test Learner",
    "email": "test.learner@example.com",
    "password": "correct-horse-battery-staple",
}


def register(client: TestClient, payload: dict[str, str] | None = None) -> dict:
    response = client.post("/api/v1/auth/register", json=payload or REGISTRATION)
    assert response.status_code == 201
    return response.json()


def test_registration_returns_token_and_safe_profile(client: TestClient) -> None:
    payload = register(client)

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["name"] == REGISTRATION["name"]
    assert payload["user"]["email"] == REGISTRATION["email"]
    assert "password" not in payload["user"]
    assert "password_hash" not in payload["user"]


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTRATION, "email": REGISTRATION["email"].upper()},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_and_current_user(client: TestClient) -> None:
    registration = register(client)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["id"] == registration["user"]["id"]
    assert me_response.json()["email"] == REGISTRATION["email"]


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_protected_route_requires_valid_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}).status_code == 401


def test_logout_requires_authentication_and_returns_no_content(client: TestClient) -> None:
    registration = register(client)
    token = registration["access_token"]

    assert client.post("/api/v1/auth/logout").status_code == 401
    response = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert response.content == b""


def test_registration_validates_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "", "email": "not-an-email", "password": "short"},
    )

    assert response.status_code == 422
