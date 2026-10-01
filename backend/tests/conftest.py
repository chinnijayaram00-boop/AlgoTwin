import os
import secrets
from collections.abc import Generator, Iterator

import pytest
from database.models import Base
from database.problem_catalog import CATALOG, validate_catalog
from database.seed import seed_demo_data
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings

# Authentication refuses to issue or verify tokens without a secret, so the
# suite installs a throwaway one before any application module is imported.
os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(32))

# `/api/v1/health` reports the configured service name, so the suite pins
# APP_NAME too. Without this the assertion depends on whatever the developer's
# local `.env` happens to set, which makes the test pass or fail based on the
# machine it runs on.
os.environ["APP_NAME"] = "ALgotwin API"

TEST_JWT_SECRET = "test-only-jwt-secret-0123456789abcdef"
TEST_JWT_ALGORITHM = "HS256"
PASSWORD = "correct-horse-battery-staple"

#: How many problems the fixture database is seeded with, and how many of each
#: difficulty. Read from the catalog rather than written as a literal, so a test
#: that asserts "the summary counts every problem" keeps asserting that when the
#: catalog grows -- which it did when the twelve `database/problem_defs`
#: definitions were first wired into the seeder, breaking six assertions that had
#: `4` baked in as the number of problems the platform ships.
CATALOG_SIZE = len(CATALOG)
CATALOG_BY_DIFFICULTY: dict[str, int] = {}
for _definition in CATALOG:
    CATALOG_BY_DIFFICULTY[_definition["difficulty"]] = (
        CATALOG_BY_DIFFICULTY.get(_definition["difficulty"], 0) + 1
    )
CATALOG_SLUGS: list[str] = [definition["slug"] for definition in CATALOG]

#: How many catalog problems carry each topic. A problem may carry several, so
#: these counts sum to more than :data:`CATALOG_SIZE`.
CATALOG_TOPIC_COUNTS: dict[str, int] = {}
for _definition in CATALOG:
    for _topic in _definition["topics"]:
        CATALOG_TOPIC_COUNTS[_topic] = CATALOG_TOPIC_COUNTS.get(_topic, 0) + 1

#: The topics of each catalog problem, by slug.
CATALOG_TOPICS: dict[str, list[str]] = {
    definition["slug"]: list(definition["topics"]) for definition in CATALOG
}

# The catalog is validated once at import so a broken definition is a collection
# error naming the problem, not a hundred individual assertion failures.
validate_catalog()


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
