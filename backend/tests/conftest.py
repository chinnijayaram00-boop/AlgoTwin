import os
import secrets
from collections.abc import Generator, Iterator

import pytest
from database.models import Base
from database.seed import seed_demo_data
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings

# Authentication refuses to issue or verify tokens without a secret, so the
# suite installs a throwaway one before any application module is imported.
os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(32))

TEST_JWT_SECRET = "test-only-jwt-secret-0123456789abcdef"
TEST_JWT_ALGORITHM = "HS256"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    """A private in-memory database for one test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """A session on the private database, for asserting on stored rows."""
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    """A TestClient wired to the private database."""
    from backend.app.db.session import get_db
    from backend.app.main import app

    with Session(db_engine) as session:
        seed_demo_data(session)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def settings() -> Settings:
    """Settings pinned to a known secret so tests can mint their own tokens."""
    return Settings(
        jwt_secret_key=TEST_JWT_SECRET,
        jwt_algorithm=TEST_JWT_ALGORITHM,
        access_token_expire_minutes=60,
    )


@pytest.fixture
def client_with_known_secret(db_engine: Engine) -> Iterator[TestClient]:
    """A client whose accepted JWT secret is :data:`TEST_JWT_SECRET`."""
    from backend.app.core.config import get_settings
    from backend.app.db.session import get_db
    from backend.app.main import app

    with Session(db_engine) as session:
        seed_demo_data(session)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=TEST_JWT_SECRET,
        jwt_algorithm=TEST_JWT_ALGORITHM,
        access_token_expire_minutes=60,
    )
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
