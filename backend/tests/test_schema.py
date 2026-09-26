import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from backend.app.db.schema import ensure_progress_schema, ensure_user_schema

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


# A database provisioned before learner progress shipped, including the
# pre-release columns and status vocabulary the placeholder table used.
PRE_RELEASE_PROGRESS_SCHEMA = """
CREATE TABLE progress (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    completed_at DATETIME,
    best_time_ms INTEGER,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_progress_user_problem UNIQUE (user_id, problem_id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(problem_id) REFERENCES problems (id) ON DELETE CASCADE
);
CREATE TABLE users (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE TABLE problems (
    id INTEGER NOT NULL,
    slug VARCHAR(120) NOT NULL,
    is_published BOOLEAN NOT NULL,
    PRIMARY KEY (id)
);
"""


def build_pre_release_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        for statement in PRE_RELEASE_PROGRESS_SCHEMA.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
        connection.execute(
            text("INSERT INTO users (id, name, email, created_at, updated_at) VALUES (1, 'Old Learner', 'old@example.com', '2024-01-01 00:00:00', '2024-01-01 00:00:00')")
        )
        connection.execute(text("INSERT INTO problems (id, slug, is_published) VALUES (1, 'two-sum', 1)"))
        connection.execute(text("INSERT INTO problems (id, slug, is_published) VALUES (2, 'binary-search', 1)"))
        connection.execute(text("INSERT INTO problems (id, slug, is_published) VALUES (3, 'merge-intervals', 1)"))
        connection.execute(text("INSERT INTO problems (id, slug, is_published) VALUES (4, 'valid-parentheses', 1)"))
        # One solved problem with a recorded runtime, one still in progress.
        connection.execute(
            text(
                "INSERT INTO progress (id, user_id, problem_id, status, completed_at, best_time_ms, updated_at)"
                " VALUES (1, 1, 1, 'completed', '2024-01-02 00:00:00', 150, '2024-01-02 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO progress (id, user_id, problem_id, status, updated_at)"
                " VALUES (2, 1, 2, 'in_progress', '2024-01-03 00:00:00')"
            )
        )
        # Completed and last updated on different days, so the upgrade has to
        # prefer the completion date over the update date.
        connection.execute(
            text(
                "INSERT INTO progress (id, user_id, problem_id, status, completed_at, best_time_ms, updated_at)"
                " VALUES (3, 1, 3, 'completed', '2024-01-10 00:00:00', 90, '2024-01-20 00:00:00')"
            )
        )
    return engine


def test_pre_release_progress_table_is_upgraded_without_losing_learner_data() -> None:
    engine = build_pre_release_engine()

    ensure_progress_schema(engine)
    ensure_progress_schema(engine)  # idempotent

    columns = {column["name"] for column in inspect(engine).get_columns("progress")}
    assert {
        "user_id",
        "problem_id",
        "status",
        "attempts_count",
        "best_runtime_ms",
        "best_memory_mb",
        "last_attempted_at",
        "solved_at",
        "created_at",
        "updated_at",
    } <= columns

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, status, attempts_count, best_runtime_ms, best_memory_mb,"
                " last_attempted_at, solved_at, created_at FROM progress ORDER BY id"
            )
        ).all()

        # Legacy labels are rewritten onto the new vocabulary, and the solve
        # date and runtime measurement are carried across rather than dropped.
        assert rows[0] == (1, "solved", 1, 150, None, "2024-01-02 00:00:00", "2024-01-02 00:00:00", "2024-01-02 00:00:00")
        assert rows[1] == (2, "attempted", 1, None, None, "2024-01-03 00:00:00", None, "2024-01-03 00:00:00")
        # The old `completed_at` is the better evidence, so it wins over the
        # later `updated_at` for the solve date, while the activity and
        # creation stamps fall back to the update date.
        assert rows[2] == (3, "solved", 1, 90, None, "2024-01-20 00:00:00", "2024-01-10 00:00:00", "2024-01-20 00:00:00")
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []

        # The table stays writable, and the unique pair is still enforced on it.
        connection.execute(
            text(
                "INSERT INTO progress (user_id, problem_id, status, attempts_count, created_at, updated_at)"
                " VALUES (1, 4, 'attempted', 0, '2024-01-04 00:00:00', '2024-01-04 00:00:00')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO progress (user_id, problem_id, status, attempts_count, created_at, updated_at)"
                    " VALUES (1, 4, 'solved', 0, '2024-01-05 00:00:00', '2024-01-05 00:00:00')"
                )
            )
        connection.rollback()

    indexes = {index["name"] for index in inspect(engine).get_indexes("progress")}
    assert "ix_progress_user_status" in indexes


def test_upgrade_is_a_no_op_without_a_progress_table() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    ensure_progress_schema(engine)

    assert "progress" not in inspect(engine).get_table_names()
