import pytest
from database.models import Submission
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateIndex, CreateTable

from backend.app.db.schema import (
    ensure_progress_schema,
    ensure_submission_schema,
    ensure_user_schema,
)

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


def test_a_single_upgrade_carries_best_time_ms_into_best_runtime_ms() -> None:
    """One upgrade has to backfill the runtime, not a second, later one.

    ``ensure_progress_schema`` adds ``best_runtime_ms`` and then copies
    ``best_time_ms`` into it. If the copy only looked at the columns that
    existed *before* the upgrade, the recorded runtime would survive in the
    legacy column but never reach the column the application reads, and a
    single ``alembic upgrade`` or start-up would silently lose it.
    """
    engine = build_pre_release_engine()

    ensure_progress_schema(engine)  # exactly one pass, as a deployment does

    with engine.connect() as connection:
        runtimes = connection.execute(
            text("SELECT id, best_time_ms, best_runtime_ms FROM progress ORDER BY id")
        ).all()

    assert [tuple(row) for row in runtimes] == [(1, 150, 150), (2, None, None), (3, 90, 90)]


def test_upgrade_is_a_no_op_without_a_progress_table() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    ensure_progress_schema(engine)

    assert "progress" not in inspect(engine).get_table_names()


# ---------------------------------------------------------------------------
# submissions
# ---------------------------------------------------------------------------

SUBMISSION_COLUMNS = (
    "id",
    "user_id",
    "problem_id",
    "language",
    "source_code",
    "status",
    "test_cases_passed",
    "test_cases_total",
    "runtime_ms",
    "memory_mb",
    "error_message",
    "submitted_at",
    "judged_at",
)

SUBMISSION_INDEXES = {
    "ix_submissions_problem_id",
    "ix_submissions_status",
    "ix_submissions_submitted_at",
    "ix_submissions_user_id",
    "ix_submissions_user_submitted_at",
}

SUBMISSION_CHECKS = {
    "ck_submissions_memory_mb",
    "ck_submissions_runtime_ms",
    "ck_submissions_status",
    "ck_submissions_test_case_counts",
}

# One judged and one still queued, so a test can tell a preserved verdict from an
# invented one.
SUBMISSION_ROWS = """
INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                         test_cases_passed, test_cases_total, runtime_ms, memory_mb,
                         error_message, submitted_at, judged_at)
    VALUES (1, 1, 1, 'python', 'def solve(): return 3', 'accepted', 3, 4, 17, 9,
            'partial output on the hidden cases', '2026-02-01 10:00:00', '2026-02-01 10:00:01'),
           (2, 1, 2, 'python', 'def solve(): raise', 'queued', NULL, NULL, NULL, NULL,
            NULL, '2026-02-02 11:00:00', NULL);
"""

REFERENCED_SCHEMA = """
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
    PRIMARY KEY (id)
);
INSERT INTO users (id, name, email, created_at, updated_at)
    VALUES (1, 'Old Learner', 'old@example.com', '2024-01-01 00:00:00', '2024-01-01 00:00:00');
INSERT INTO problems (id, slug) VALUES (1, 'two-sum'), (2, 'binary-search');
"""


def _canonical_submissions_ddl() -> str:
    """The ``submissions`` DDL as ``Base.metadata.create_all`` would emit it.

    Read off the model rather than written out here, so "canonical" cannot drift
    away from the thing the application actually builds and this test keeps
    meaning what it says.
    """
    table = Submission.__table__
    dialect = sqlite.dialect()
    statements = [
        str(CreateTable(table).compile(dialect=dialect)).strip(),
        *(str(CreateIndex(index).compile(dialect=dialect)).strip() for index in table.indexes),
    ]
    return ";\n".join(statements) + ";"


def build_submission_engine(submissions_table: str, rows: str = SUBMISSION_ROWS):
    """An engine holding ``submissions`` in a given shape, with rows to protect.

    Foreign keys are enforced, so a rebuild that drops a row or points one at the
    wrong parent fails here rather than going unnoticed.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        for statement in (REFERENCED_SCHEMA + submissions_table + rows).split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
    return engine


def build_canonical_submission_engine(rows: str = SUBMISSION_ROWS):
    return build_submission_engine(_canonical_submissions_ddl(), rows=rows)


def test_upgrade_is_a_no_op_without_a_submissions_table() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    ensure_submission_schema(engine)

    assert "submissions" not in inspect(engine).get_table_names()


def test_a_canonical_submissions_table_is_left_exactly_as_it_is() -> None:
    """The common case: a database already at the current shape changes nothing.

    Asserted as full-row equality on both sides of the call rather than on the
    values alone, so a rebuild that happened to reproduce the values would still
    fail this -- it would have thrown away the table's identity for no reason.
    """
    engine = build_canonical_submission_engine()

    with engine.connect() as connection:
        before = connection.execute(text("SELECT * FROM submissions ORDER BY id")).all()

    ensure_submission_schema(engine)
    ensure_submission_schema(engine)  # idempotent

    assert {column["name"] for column in inspect(engine).get_columns("submissions")} == set(
        SUBMISSION_COLUMNS
    )
    assert SUBMISSION_INDEXES <= {
        index["name"] for index in inspect(engine).get_indexes("submissions")
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM submissions ORDER BY id")).all() == before
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []


def test_a_submissions_table_missing_checks_and_indexes_gains_both_on_rebuild() -> None:
    """A table with the columns but not yet the constraints is rebuilt for both.

    The fixture is the interesting middle state: every canonical column is
    present and one CHECK is declared, so the earlier rebuild trigger -- retired
    ``NOT NULL`` placeholder columns, or no checks at all -- deliberately does not
    fire. The rebuild happens later instead, on the missing-checks path, because
    SQLite can only add a constraint by rebuilding the table.

    So this exercises the *second* trigger, and both reasons to rebuild at once:
    the three absent CHECKs and the five absent indexes. Because a rebuild really
    does happen, the rows have to come through it intact -- ``judged_at``
    included, since that is the column a rebuild is most able to lose.
    """
    engine = build_submission_engine(
        """
        CREATE TABLE submissions (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            language VARCHAR(40) NOT NULL,
            source_code TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            test_cases_passed INTEGER,
            test_cases_total INTEGER,
            runtime_ms INTEGER,
            memory_mb INTEGER,
            error_message TEXT,
            submitted_at DATETIME NOT NULL,
            judged_at DATETIME,
            PRIMARY KEY (id),
            CONSTRAINT ck_submissions_status CHECK (status IN ('queued', 'running',
                'accepted', 'wrong_answer', 'runtime_error', 'compilation_error',
                'time_limit_exceeded', 'memory_limit_exceeded', 'failed'))
        );
        """
    )
    assert {index["name"] for index in inspect(engine).get_indexes("submissions")} == set()

    ensure_submission_schema(engine)
    ensure_submission_schema(engine)  # idempotent

    assert SUBMISSION_INDEXES <= {
        index["name"] for index in inspect(engine).get_indexes("submissions")
    }
    assert SUBMISSION_CHECKS <= {
        constraint["name"]
        for constraint in inspect(engine).get_check_constraints("submissions")
    }
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT id, status, test_cases_passed, submitted_at, judged_at"
                 " FROM submissions ORDER BY id")
        ).all() == [
            (1, "accepted", 3, "2026-02-01 10:00:00", "2026-02-01 10:00:01"),
            (2, "queued", None, "2026-02-02 11:00:00", None),
        ]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []


def test_the_rebuild_keeps_judged_at_when_the_table_has_no_constraints() -> None:
    """A rebuild triggered by missing constraints keeps every recorded verdict.

    ``judged_at`` used to be missing from the rebuild's column map, so the moment
    the upgrader dropped and recreated the table the judging time was gone --
    leaving the shape correct and the data silently destroyed. ``judged_at`` is
    also the column most likely to be non-null here: the upgrade only runs on
    databases that predate the constraints, and those are the databases holding
    real judging history.
    """
    engine = build_submission_engine(
        """
        CREATE TABLE submissions (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            language VARCHAR(40) NOT NULL,
            source_code TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            test_cases_passed INTEGER,
            test_cases_total INTEGER,
            runtime_ms INTEGER,
            memory_mb INTEGER,
            error_message TEXT,
            submitted_at DATETIME NOT NULL,
            judged_at DATETIME,
            PRIMARY KEY (id)
        );
        """
    )

    ensure_submission_schema(engine)

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, status, test_cases_passed, runtime_ms, submitted_at, judged_at"
                 " FROM submissions ORDER BY id")
        ).all()
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    # The judged submission keeps its judging time, every measurement, and its
    # submission time; the queued one is left unjudged.
    assert rows == [
        (1, "accepted", 3, 17, "2026-02-01 10:00:00", "2026-02-01 10:00:01"),
        (2, "queued", None, None, "2026-02-02 11:00:00", None),
    ]
    assert {column["name"] for column in inspect(engine).get_columns("submissions")} == set(
        SUBMISSION_COLUMNS
    )
    assert SUBMISSION_CHECKS <= {
        constraint["name"]
        for constraint in inspect(engine).get_check_constraints("submissions")
    }


def test_a_pre_release_submissions_table_is_rebuilt_without_losing_data() -> None:
    """The placeholder table rebuilds, honestly.

    ``results`` and ``created_at`` are ``NOT NULL`` with no default, which is why
    the table has to be rebuilt before a submission can be inserted at all. The
    submission time has to come from ``created_at``, and a status outside the
    vocabulary has to become ``failed`` rather than a verdict the judge never
    reached.
    """
    engine = build_submission_engine(
        """
        CREATE TABLE submissions (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            language VARCHAR(40) NOT NULL,
            source_code TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            results JSON NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY(problem_id) REFERENCES problems (id) ON DELETE CASCADE
        );
        """,
        rows="""
        INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                                 results, created_at)
            VALUES (1, 1, 1, 'python', 'def solve(): return 3', 'PASSED', '[]',
                    '2024-05-05 08:00:00'),
                   (2, 1, 2, 'ruby', 'puts 1', 'error', '[]', '2024-05-06 09:00:00');
        """,
    )

    ensure_submission_schema(engine)
    ensure_submission_schema(engine)  # idempotent

    columns = {column["name"] for column in inspect(engine).get_columns("submissions")}
    assert "results" not in columns
    assert "created_at" not in columns
    assert set(SUBMISSION_COLUMNS) == columns

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, status, submitted_at, judged_at FROM submissions ORDER BY id")
        ).all()
        assert rows == [
            (1, "failed", "2024-05-05 08:00:00", None),
            (2, "failed", "2024-05-06 09:00:00", None),
        ]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        # The table is usable afterwards, constraints included.
        connection.execute(
            text(
                "INSERT INTO submissions (user_id, problem_id, language, source_code,"
                " status, submitted_at) VALUES (1, 1, 'python', 'x', 'accepted',"
                " '2026-03-01 00:00:00')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language, source_code,"
                    " status, submitted_at) VALUES (1, 1, 'python', 'x', 'maybe_passed',"
                    " '2026-03-01 00:00:00')"
                )
            )
        connection.rollback()

    indexes = {index["name"] for index in inspect(engine).get_indexes("submissions")}
    assert SUBMISSION_INDEXES <= indexes


def test_impossible_measurements_are_dropped_rather_than_kept() -> None:
    """A row that could not have happened is nulled, not left to assert a lie.

    Passing more cases than were run, or reporting a negative duration, is what a
    pre-vocabulary table accumulates. The counts are cleared because they are the
    numbers the dashboard aggregates; the status is left alone because it is the
    learner's record of what happened.
    """
    engine = build_submission_engine(
        """
        CREATE TABLE submissions (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            language VARCHAR(40) NOT NULL,
            source_code TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            test_cases_passed INTEGER,
            test_cases_total INTEGER,
            runtime_ms INTEGER,
            memory_mb INTEGER,
            error_message TEXT,
            submitted_at DATETIME NOT NULL,
            judged_at DATETIME,
            PRIMARY KEY (id)
        );
        """,
        rows="""
        INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                                 test_cases_passed, test_cases_total, runtime_ms, submitted_at)
            VALUES (1, 1, 1, 'python', 'a', 'accepted', 9, 4, 12, '2026-02-01 10:00:00'),
                   (2, 1, 2, 'python', 'b', 'accepted', -1, 4, 12, '2026-02-01 10:00:00');
        """,
    )

    ensure_submission_schema(engine)

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, status, test_cases_passed, test_cases_total FROM submissions"
                 " ORDER BY id")
        ).all()
    assert rows == [(1, "accepted", None, 4), (2, "accepted", None, 4)]
