import os
import secrets

import pytest
from database.models import Base
from database.seed import seed_demo_data
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(32))


@pytest.fixture
def client() -> TestClient:
    from backend.app.db.session import get_db
    from backend.app.main import app

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    with Session(test_engine) as session:
        seed_demo_data(session)

    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
    test_engine.dispose()
