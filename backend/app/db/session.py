from collections.abc import Generator

from database.models import Base
from database.problem_catalog import sync_catalog
from database.seed import seed_demo_user
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.db.schema import (
    ensure_problem_schema,
    ensure_progress_schema,
    ensure_submission_schema,
    ensure_user_schema,
)

settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

#: The session factory every background worker opens its own session with.
#:
#: Request handlers receive a session through the ``get_db`` dependency, which a
#: test suite can override. Anything that runs outside a request -- the judge
#: worker, chiefly -- cannot use that dependency, so it resolves the factory
#: through here instead. Keeping it in one place is what lets a test point
#: background work at the same in-memory database the request used, rather than
#: letting a background job silently write to the developer's real database.
_session_factory: sessionmaker = SessionLocal


def get_session_factory() -> sessionmaker:
    return _session_factory


def set_session_factory(factory: sessionmaker) -> None:
    global _session_factory
    _session_factory = factory


def init_db() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    ensure_user_schema(engine)
    ensure_problem_schema(engine)
    ensure_progress_schema(engine)
    ensure_submission_schema(engine)
    # The catalog and the demo account are seeded independently. The catalog is
    # what a learner actually practises on, and a deployment that turns
    # `SEED_DEMO_DATA` off to avoid shipping the published demo password must
    # still get a catalog to read.
    if settings.auto_create_tables and settings.seed_problem_catalog:
        with SessionLocal() as session:
            sync_catalog(session)
    if settings.auto_create_tables and settings.seed_demo_data:
        with SessionLocal() as session:
            seed_demo_user(session)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
