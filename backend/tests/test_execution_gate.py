"""Phase 1 hardening: the safe defaults behind demo seeding and code execution.

These tests pin down the defaults a deployment inherits and the refusal the
execution gate produces when isolation is not configured:

* :data:`Settings.seed_demo_data` is OFF by default, so no fresh install ships
  the published demo login (``learner@algotwin.dev``).
* :data:`Settings.execution_enabled` is OFF by default, AND switching it on is
  not enough: without a verified isolation backend -- or an explicit
  ``execution_allow_insecure_native`` acknowledgment -- the run and submission
  routes refuse with 503 rather than run a learner's code un-isolated. There is
  deliberately no silent fallback.

The behavioural part of the suite (``test_judge.py`` and friends) runs with
``EXECUTION_ENABLED=true`` and ``EXECUTION_ALLOW_INSECURE_NATIVE=true`` set by
``conftest.py`` before the application imports -- the explicit, recorded opt-in
of a trusted test host. The default tests here delete those variables so they
assert the production shape, not the harness.
"""

from database.models import User
from database.seed import DEMO_USER_EMAIL
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.judge.isolation import execution_available

_GATE_VARIABLES = (
    "EXECUTION_ENABLED",
    "EXECUTION_ALLOW_INSECURE_NATIVE",
    "EXECUTION_ISOLATION",
    "SEED_DEMO_DATA",
)


def _learner_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Gate Learner",
            "email": "gate@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _problem_id(client, slug: str) -> int:
    response = client.get(f"/api/v1/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _fresh_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_default_settings_are_safe(monkeypatch) -> None:
    """The production defaults ship no demo login and no execution.

    Both variables are deleted so the conftest harness opt-in cannot mask the
    default; ``_env_file=None`` so a developer's local ``.env`` cannot either.
    """
    from backend.app.core.config import Settings

    for variable in _GATE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)

    assert settings.seed_demo_data is False
    assert settings.execution_enabled is False
    assert settings.execution_isolation == "none"
    assert settings.execution_allow_insecure_native is False


def test_execution_requires_intent_a_backend_and_an_acknowledgment(monkeypatch) -> None:
    """The gate is three independent decisions; every refusal names the gap."""
    from backend.app.core.config import Settings

    for variable in _GATE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    disabled = Settings(_env_file=None, execution_enabled=False)
    ok, reason = execution_available(disabled)
    assert ok is False
    assert "disabled" in reason.lower()

    unknown_backend = Settings(
        _env_file=None,
        execution_enabled=True,
        execution_isolation="names-a-future-backend",
    )
    ok, reason = execution_available(unknown_backend)
    assert ok is False
    assert "not a registered" in reason

    unisolated = Settings(
        _env_file=None,
        execution_enabled=True,
        execution_isolation="none",
        execution_allow_insecure_native=False,
    )
    ok, reason = execution_available(unisolated)
    assert ok is False
    assert "isolation" in reason.lower()

    acknowledged = Settings(
        _env_file=None,
        execution_enabled=True,
        execution_isolation="none",
        execution_allow_insecure_native=True,
    )
    ok, _ = execution_available(acknowledged)
    assert ok is True


def test_init_db_does_not_seed_the_demo_user_with_safe_defaults(monkeypatch) -> None:
    """A fresh database gets its catalog but no published login."""
    import backend.app.db.session as session_module
    from backend.app.core.config import Settings

    engine = _fresh_engine()
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", factory)
    monkeypatch.setattr(
        session_module,
        "settings",
        Settings(
            _env_file=None,
            auto_create_tables=True,
            seed_problem_catalog=False,
            seed_demo_data=False,
        ),
    )

    session_module.init_db()

    with factory() as session:
        assert session.scalar(select(User).where(User.email == DEMO_USER_EMAIL)) is None


def test_init_db_seeds_the_demo_user_when_opted_in(monkeypatch) -> None:
    """An operator who asks for the demo account, explicitly gets it."""
    import backend.app.db.session as session_module
    from backend.app.core.config import Settings

    engine = _fresh_engine()
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", factory)
    monkeypatch.setattr(
        session_module,
        "settings",
        Settings(
            _env_file=None,
            auto_create_tables=True,
            seed_problem_catalog=False,
            seed_demo_data=True,
        ),
    )

    session_module.init_db()

    with factory() as session:
        assert session.scalar(select(User).where(User.email == DEMO_USER_EMAIL)) is not None


def test_run_refused_when_execution_is_enabled_but_no_isolation(client) -> None:
    """Intent alone does not open the gate: no isolation means 503, not a run."""
    from backend.app.core.config import Settings, get_settings
    from backend.app.main import app

    headers = _learner_headers(client)
    problem = _problem_id(client, "two-sum")

    def override_get_settings():
        return Settings(execution_enabled=True, execution_allow_insecure_native=False)

    app.dependency_overrides[get_settings] = override_get_settings
    try:
        response = client.post(
            f"/api/v1/problems/{problem}/run",
            json={"language": "python", "source_code": "print(1)"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert "isolation" in response.json()["detail"].lower()


def test_submission_refused_and_kept_when_execution_is_enabled_but_no_isolation(
    client,
) -> None:
    """Submission without isolation is refused, and the row stays ``queued``."""
    from backend.app.core.config import Settings, get_settings
    from backend.app.main import app

    headers = _learner_headers(client)
    problem = _problem_id(client, "two-sum")

    app.dependency_overrides[get_settings] = lambda: Settings(
        execution_enabled=True, execution_allow_insecure_native=False
    )
    try:
        response = client.post(
            "/api/v1/submissions",
            json={"problem_id": problem, "language": "python", "source_code": "KEPT = 1"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert "isolation" in response.json()["detail"].lower()

    listing = client.get("/api/v1/submissions", headers=headers).json()
    assert listing["total"] == 1
    assert listing["items"][0]["status"] == "queued"


def test_languages_reports_execution_unavailable_without_isolation(client) -> None:
    """The editor must not offer a Run button that would 503."""
    from backend.app.core.config import Settings, get_settings
    from backend.app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        execution_enabled=True, execution_allow_insecure_native=False
    )
    try:
        payload = client.get("/api/v1/judge/languages").json()
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert payload["execution_enabled"] is False