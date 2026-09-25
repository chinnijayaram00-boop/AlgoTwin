from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.pool import StaticPool

from backend.app.db.schema import ensure_user_schema

LEGACY_SCHEMA = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    email VARCHAR(320) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE TABLE problems (
    id INTEGER NOT NULL,
    slug VARCHAR(80) NOT NULL,
    PRIMARY KEY (id)
);
CREATE TABLE progress (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(problem_id) REFERENCES problems (id) ON DELETE CASCADE
);
"""


def build_legacy_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        for statement in LEGACY_SCHEMA.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
        connection.execute(text("INSERT INTO users (id, email, display_name, created_at) VALUES (1, 'old@example.com', 'Old Learner', '2024-01-01 00:00:00')"))
        connection.execute(text("INSERT INTO problems (id, slug) VALUES (1, 'two-sum')"))
        connection.execute(text("INSERT INTO progress (id, user_id, problem_id, status, updated_at) VALUES (1, 1, 1, 'completed', '2024-01-02 00:00:00')"))
    return engine


def test_legacy_user_table_is_upgraded_without_losing_data() -> None:
    engine = build_legacy_engine()

    ensure_user_schema(engine)
    ensure_user_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert columns == {"id", "name", "email", "password_hash", "created_at", "updated_at"}

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, name, email, created_at, updated_at FROM users")).all()
        assert rows == [(1, "Old Learner", "old@example.com", "2024-01-01 00:00:00", "2024-01-01 00:00:00")]
        assert connection.execute(text("SELECT user_id, problem_id, status FROM progress")).all() == [(1, 1, "completed")]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []

        connection.execute(
            text(
                "INSERT INTO users (name, email, password_hash, created_at, updated_at)"
                " VALUES ('New Learner', 'new@example.com', 'argon2-hash', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
            )
        )
        connection.commit()
        assert connection.execute(text("SELECT count(*) FROM users")).scalar() == 2
