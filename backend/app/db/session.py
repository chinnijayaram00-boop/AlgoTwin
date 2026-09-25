from collections.abc import Generator

from database.models import Base
from database.seed import seed_demo_data
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.db.schema import ensure_user_schema

settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    ensure_user_schema(engine)
    if settings.auto_create_tables and settings.seed_demo_data:
        with SessionLocal() as session:
            seed_demo_data(session)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
