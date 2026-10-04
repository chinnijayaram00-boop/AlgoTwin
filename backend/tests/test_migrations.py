"""Alembic migration behaviour: the chain, and what each revision does to real data.

These are the tests for the three database blockers the audit found, each written
against the failure rather than against the fix:

* the baseline revision named ``display_name`` unconditionally, so it could not
  adopt the ``users`` table the shipped development databases actually have;
* ``c_submission_records`` rebuilt ``submissions`` from a fixed shape that omitted
  ``judged_at``, so migrating a ``create_all``-provisioned database silently
  emptied every recorded judging timestamp;
* the runtime upgrader in ``backend.app.db.schema`` rebuilt the same table from a
  hand-written column map that had fallen out of step with the model, and died on
  a ``KeyError`` before copying a single row.

Every test here runs Alembic in-process against a database under pytest's
``tmp_path``. The repository's own ``.db`` files are never opened -- the harness
builds an absolute URL per test rather than resolving a relative one, because a
relative URL would silently point Alembic at ``./algotwin.db`` and migrate a
developer's real data.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from database.models import Base
from sqlalchemy import create_engine

from backend.app.core.config import get_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: The single head, asserted literally so a second branch or an accidental new
#: head fails here rather than surfacing later as two databases sitting at
#: different revisions under the same name.
EXPECTED_HEAD = "f_ai_insights"

#: The chain, oldest first, also asserted literally. The ordering is the point:
#: ``c_submission_records`` rebuilds ``submissions`` and
#: ``e_judged_submissions`` adds ``judged_at`` immediately after it, and the
#: relationship between those two is what the ``judged_at`` preservation rests on.
EXPECTED_CHAIN = (
    "533005ea0596",
    "b_progress_learner_tracking",
    "c_submission_records",
    "d_problem_catalog",
    "e_judged_submissions",
    "f_ai_insights",
)


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(REPOSITORY_ROOT / "database" / "migrations"))
    return config


@contextmanager
def _database(database_path: Path):
    """Point Alembic and the settings cache at ``database_path`` for one command.

    ``env.py`` overrides the URL from settings on every run, so the database is
    selected through the environment rather than through the config, which would
    be silently discarded. ``get_settings`` is ``lru_cache``d, so it has to be
    cleared on both sides or a later test would inherit this database's URL.
    """
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    get_settings.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def _upgrade_to_head(database_path: Path) -> None:
    with _database(database_path):
        command.upgrade(_config(), "head")


def _stamp(database_path: Path, revision: str) -> None:
    with _database(database_path):
        command.stamp(_config(), revision)


def _connect(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(database_path)


def _run(database_path: Path, script: str) -> None:
    with _connect(database_path) as connection:
        connection.executescript(script)


def _columns(database_path: Path, table: str) -> list[str]:
    with _connect(database_path) as connection:
        return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _indexes(database_path: Path, table: str) -> set[str]:
    with _connect(database_path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (table,)
            )
        }


def _version(database_path: Path) -> str | None:
    with _connect(database_path) as connection:
        try:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.OperationalError:
            return None
    return row[0] if row else None


def _foreign_key_violations(database_path: Path) -> list[tuple]:
    with _connect(database_path) as connection:
        return connection.execute("PRAGMA foreign_key_check").fetchall()


# ---------------------------------------------------------------------------
# Fixtures describing database states
# ---------------------------------------------------------------------------

#: ``users`` exactly as ``Base.metadata.create_all`` builds it, which is what both
#: shipped development databases have: canonical column names, ``NOT NULL`` on the
#: columns the model marks required, and no ``display_name`` anywhere.
CANONICAL_USERS_TABLE = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
"""

#: ``users`` as SQLite leaves an *adopted* table: it cannot relax or enforce NOT
#: NULL with ``ALTER TABLE``, so a table that predates the rename keeps a nullable
#: ``name``. This is the state the baseline's backfill has to cope with when a row
#: has no name to read.
ADOPTED_USERS_TABLE = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    name VARCHAR(120),
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (id)
);
"""

#: The pre-rename table, and the only state in which ``display_name`` exists.
LEGACY_USERS_TABLE = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    email VARCHAR(320) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
"""

#: ``problems`` complete, so the catalog revision finds nothing to add and these
#: tests exercise the adoption path rather than the column adds.
COMPLETE_PROBLEMS_TABLE = """
CREATE TABLE problems (
    id INTEGER NOT NULL,
    slug VARCHAR(120) NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary TEXT NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    topics JSON NOT NULL,
    examples JSON NOT NULL,
    constraints TEXT,
    starter_code JSON NOT NULL,
    is_published BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    description TEXT,
    input_format TEXT,
    output_format TEXT,
    hints JSON NOT NULL,
    explanation TEXT,
    supported_languages JSON NOT NULL,
    expected_time_complexity VARCHAR(60),
    expected_space_complexity VARCHAR(60),
    time_limit_ms INTEGER NOT NULL,
    memory_limit_mb INTEGER NOT NULL,
    test_cases JSON NOT NULL,
    reference_solutions JSON NOT NULL,
    PRIMARY KEY (id)
);
"""

PROBLEM_INSERT = """
INSERT INTO problems (id, slug, title, summary, difficulty, topics, examples, constraints,
                      starter_code, is_published, created_at, hints, supported_languages,
                      time_limit_ms, memory_limit_mb, test_cases, reference_solutions)
    VALUES (1, 'two-sum', 'Two Sum', 'Find the pair that sums to a target.',
            'easy', '["arrays"]', '[]', NULL, '{"python": "def solve(): pass"}', 1,
            '2026-01-01 00:00:00', '[]', '["python"]', 2000, 256,
            '[{"input": "1 2", "expected_output": "3"}]', '{"python": "def solve(): pass"}');
"""

USER_INSERT = """
INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
    VALUES (1, 'Dev One', 'dev1@example.com', 'argon2-hash', '2026-01-01 00:00:00', '2026-01-01 00:00:00');
"""

SUBMISSION_INSERT = """
INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                         test_cases_passed, test_cases_total, runtime_ms, memory_mb,
                         error_message, submitted_at, judged_at)
    VALUES (1, 1, 1, 'python', 'def solve(): return 3', 'accepted', 3, 4, 17, 9,
            'partial output on the hidden cases', '2026-02-01 10:00:00', '2026-02-01 10:00:01');
"""

#: The full record of one judged submission. Comparing this tuple before and after
#: a migration is how "nothing was lost" is asserted -- column by column would let
#: a rebuilt row keep its shape while quietly losing a measurement.
JUDGED_RECORD_COLUMNS = (
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

JUDGED_RECORD_SELECT = ", ".join(JUDGED_RECORD_COLUMNS)


def _provision_with_create_all(database_path: Path) -> None:
    """Build the database ``Base.metadata.create_all`` produces.

    This is the shape a development machine ends up with, and the reason the
    ``judged_at`` bug was reachable at all: the table already carries ``judged_at``
    before any migration runs.
    """
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()


def _differences(database_path: Path) -> list:
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": False}
        )
        found = compare_metadata(context, Base.metadata)
    engine.dispose()
    return found


# ---------------------------------------------------------------------------
# The chain itself
# ---------------------------------------------------------------------------


def test_the_chain_is_linear_and_ends_at_f_ai_insights() -> None:
    script = ScriptDirectory.from_config(_config())

    assert script.get_heads() == [EXPECTED_HEAD]

    walked: list[str] = []
    revision = script.get_revision(EXPECTED_HEAD)
    while revision is not None:
        walked.append(revision.revision)
        revision = script.get_revision(revision.down_revision) if revision.down_revision else None
    walked.reverse()

    assert walked == list(EXPECTED_CHAIN)


def test_a_fresh_database_upgrades_to_the_head(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"

    _upgrade_to_head(database)

    assert _version(database) == EXPECTED_HEAD
    with _connect(database) as connection:
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"users", "problems", "progress", "submissions", "ai_insights"} <= tables
    # A fresh migration lands on the whole model shape, `judged_at` included, so a
    # migrated database and a `create_all` one agree on the table.
    assert set(JUDGED_RECORD_COLUMNS) <= set(_columns(database, "submissions"))
    assert {
        "ix_submissions_user_id",
        "ix_submissions_problem_id",
        "ix_submissions_status",
        "ix_submissions_submitted_at",
        "ix_submissions_user_submitted_at",
    } <= _indexes(database, "submissions")


def test_upgrading_twice_changes_nothing(tmp_path: Path) -> None:
    database = tmp_path / "twice.db"
    _upgrade_to_head(database)
    columns_after_first = _columns(database, "submissions")

    _upgrade_to_head(database)

    assert _version(database) == EXPECTED_HEAD
    assert _columns(database, "submissions") == columns_after_first


@pytest.mark.parametrize("revision", EXPECTED_CHAIN[1:])
def test_each_revision_applies_on_its_own(tmp_path: Path, revision: str) -> None:
    """Every step applies to a fresh database one at a time.

    ``upgrade head`` only proves the chain runs end to end. Stepping through it
    proves no revision quietly depends on a later one having already run -- which
    is the property that let ``c`` and ``e`` disagree about ``judged_at``.
    """
    database = tmp_path / f"step_{revision}.db"

    with _database(database):
        command.upgrade(_config(), revision)

    assert _version(database) == revision


# ---------------------------------------------------------------------------
# A5: the baseline adopting a database that already exists
# ---------------------------------------------------------------------------


def test_baseline_adopts_an_already_canonical_users_table(tmp_path: Path) -> None:
    """The failure this fixes, on the state the shipped databases are actually in.

    ``Base.metadata.create_all`` builds ``users`` with the canonical columns and no
    ``display_name``. The baseline's backfill named ``display_name`` in every
    branch, so on precisely those databases it raised ``no such column:
    display_name`` and aborted the whole upgrade -- taking every later revision
    with it, because SQLite DDL is not transactional.
    """
    database = tmp_path / "canonical.db"
    _run(
        database,
        CANONICAL_USERS_TABLE
        + COMPLETE_PROBLEMS_TABLE
        + USER_INSERT
        + PROBLEM_INSERT
        + """
        INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
            VALUES (2, 'Dev Two', 'dev2@example.com', 'argon2-hash',
                    '2024-03-04 05:06:07', '2024-03-04 05:06:07');
        """,
    )

    _upgrade_to_head(database)

    assert _version(database) == EXPECTED_HEAD
    with _connect(database) as connection:
        rows = connection.execute(
            "SELECT id, name, email, created_at, updated_at FROM users ORDER BY id"
        ).fetchall()
    # Byte-for-byte, including a timestamp that is neither midnight nor the epoch:
    # a backfill that rewrote existing values would be as damaging as one that
    # dropped them.
    assert rows == [
        (1, "Dev One", "dev1@example.com", "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
        (2, "Dev Two", "dev2@example.com", "2024-03-04 05:06:07", "2024-03-04 05:06:07"),
    ]
    # The unique email index is created once the column set is canonical, and it
    # is created only once even though the table already had one.
    assert "ix_users_email" in _indexes(database, "users")


def test_baseline_backfills_an_adopted_users_row_that_has_no_name(tmp_path: Path) -> None:
    """A row the adopted table left without a name is completed, not left null.

    SQLite cannot enforce NOT NULL on an added column, so a table adopted from a
    pre-rename shape can hold a ``NULL`` name. The backfill has to fill it from
    evidence the row already carries -- here its email -- because the API reads
    ``name`` and would otherwise serialise ``None``.
    """
    database = tmp_path / "adopted.db"
    _run(
        database,
        ADOPTED_USERS_TABLE
        + COMPLETE_PROBLEMS_TABLE
        + PROBLEM_INSERT
        + """
        INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
            VALUES (1, 'Dev One', 'dev1@example.com', 'argon2-hash', '2026-01-01', '2026-01-01');
        INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
            VALUES (2, NULL, 'noname@example.com', NULL, NULL, NULL);
        """,
    )

    _upgrade_to_head(database)

    assert _version(database) == EXPECTED_HEAD
    with _connect(database) as connection:
        rows = connection.execute(
            "SELECT id, name, email, created_at, updated_at FROM users ORDER BY id"
        ).fetchall()
    assert rows[0][1] == "Dev One"
    assert rows[1][0] == 2
    assert rows[1][1] == "noname@example.com"
    # The timestamps are filled from the current time rather than left null.
    assert rows[1][3] is not None
    assert rows[1][4] is not None


def test_baseline_adopts_a_legacy_display_name_users_table(tmp_path: Path) -> None:
    """The pre-rename shape still carries its display name across, and keeps it."""
    database = tmp_path / "legacy.db"
    _run(
        database,
        LEGACY_USERS_TABLE
        + COMPLETE_PROBLEMS_TABLE
        + PROBLEM_INSERT
        + """
        INSERT INTO users (id, display_name, email, created_at, updated_at)
            VALUES (1, 'Legacy Learner', 'legacy@example.com', '2024-01-01', '2024-01-02');
        """,
    )

    _upgrade_to_head(database)

    assert _version(database) == EXPECTED_HEAD
    with _connect(database) as connection:
        assert connection.execute(
            "SELECT name FROM users WHERE id = 1"
        ).fetchone() == ("Legacy Learner",)
    # The old column is left in place rather than dropped: this baseline may have
    # adopted a table holding real rows, and discarding one would lose data.
    assert "display_name" in _columns(database, "users")


def test_baseline_adopts_the_shipped_development_database_shape(tmp_path: Path) -> None:
    """The end-to-end version: what a developer's own ``.db`` file contains.

    Every table already at its current shape, real rows in ``users``, ``problems``
    and ``submissions``, and no ``alembic_version`` at all -- the state a database
    is in after running the app with ``AUTO_CREATE_TABLES=true``. If this passes,
    the deploy path the README documents works against a real database.
    """
    database = tmp_path / "devshape.db"
    _run(
        database,
        CANONICAL_USERS_TABLE
        + COMPLETE_PROBLEMS_TABLE
        + """
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
        CREATE TABLE progress (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            status VARCHAR(30) NOT NULL,
            completed_at DATETIME,
            best_time_ms INTEGER,
            updated_at DATETIME NOT NULL,
            attempts_count INTEGER NOT NULL DEFAULT 0,
            best_runtime_ms INTEGER,
            best_memory_mb INTEGER,
            last_attempted_at DATETIME,
            solved_at DATETIME,
            created_at DATETIME,
            PRIMARY KEY (id)
        );
        """
        + USER_INSERT
        + PROBLEM_INSERT
        + SUBMISSION_INSERT,
    )
    assert _version(database) is None

    _upgrade_to_head(database)

    assert _version(database) == EXPECTED_HEAD
    with _connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM problems").fetchone() == (1,)
        assert connection.execute(
            f"SELECT {JUDGED_RECORD_SELECT} FROM submissions WHERE id = 1"
        ).fetchone() == (
            1,
            1,
            1,
            "python",
            "def solve(): return 3",
            "accepted",
            3,
            4,
            17,
            9,
            "partial output on the hidden cases",
            "2026-02-01 10:00:00",
            "2026-02-01 10:00:01",
        )
    assert _foreign_key_violations(database) == []


# ---------------------------------------------------------------------------
# Reading autogen differences
# ---------------------------------------------------------------------------
#
# `compare_metadata` does not return one uniform kind of element, and a reader
# that assumes a single shape discards differences without saying so. The two
# shapes, as actually observed on this schema:
#
#   ('remove_index', Index(...))                     -> tuple, 2 elements
#   ('remove_column', None, 'progress', Column(...)) -> tuple, 4 elements
#   [('modify_nullable', None, 'users', 'name', {...}, True, False)]
#                                                     -> *list* of tuples
#
# So `isinstance(difference, tuple)` matches the first two and silently drops
# every `modify_*` difference -- which is every nullability, type and default
# difference, i.e. most of what these tests exist to catch. Matching
# `(list, tuple)` instead is not enough either: on the nested shape, `difference[0]`
# is a tuple rather than the operation name, so a substring/equality scan of the
# top level still finds no table name.
#
# Everything below therefore *flattens* first, and a difference that still cannot
# be read is reported rather than dropped -- see `_unreadable`.


def _flatten(difference) -> list[tuple]:
    """Every flat ``(operation, ...)`` tuple inside one returned element."""
    if isinstance(difference, tuple):
        return [difference]
    if isinstance(difference, list):
        flattened: list[tuple] = []
        for item in difference:
            flattened.extend(_flatten(item))
        return flattened
    return []


def _object_table(obj) -> str | None:
    """The table an ``Index``/constraint/``Column``/``Table`` belongs to.

    ``remove_index`` and the constraint operations name no table as a string, so
    the only way to attribute them to a table is through the object itself.
    """
    owner = getattr(obj, "table", None)
    if owner is not None:
        return getattr(owner, "name", None)
    # An Index reports its columns rather than a table; the first one settles it.
    for column in getattr(obj, "columns", ()) or ():
        return getattr(getattr(column, "table", None), "name", None)
    return None


def _describe(entry: tuple) -> tuple[str, str | None, str | None] | None:
    """``(operation, table, column)`` for one flat tuple, or ``None`` if unreadable."""
    if not entry or not isinstance(entry[0], str):
        return None
    operation = entry[0]

    # `(op, schema, tname, ...)` positions the table at index 2. `quoted_name` is
    # a `str` subclass, so a schema-qualified name compares as a string too.
    table = str(entry[2]) if len(entry) >= 3 and isinstance(entry[2], str) else None
    if table is None:
        for part in entry[1:]:
            table = _object_table(part)
            if table is not None:
                break

    # `(op, schema, tname, cname, existing, new)` names the column at index 3;
    # for `add_column`/`remove_column` that slot holds a `Column` instead.
    column = (
        str(entry[3])
        if len(entry) >= 4 and table is not None and isinstance(entry[3], str)
        else None
    )
    return operation, table, column


def _difference_parts(difference) -> list[tuple[str, str | None, str | None]]:
    """Every ``(operation, table, column)`` inside one returned element.

    Empty means the element could not be read, which is a problem in this reader
    and never a statement about the database -- so callers must check for it.
    """
    parts = []
    for entry in _flatten(difference):
        described = _describe(entry)
        if described is not None:
            parts.append(described)
    return parts


def _unreadable(differences: list) -> list:
    """Differences this reader could not interpret at all.

    Asserted empty by the drift tests. Without it, an Alembic release that
    returns a new shape would make every filter below quietly match nothing and
    turn a real assertion into a vacuous one -- which is exactly the failure this
    section exists to prevent.
    """
    return [difference for difference in differences if not _difference_parts(difference)]


def _touches(difference, table: str) -> bool:
    """Whether an autogen difference refers to ``table``, in either shape."""
    return any(part[1] == table for part in _difference_parts(difference))


def test_a_migrated_users_table_matches_the_model(tmp_path: Path) -> None:
    """The baseline leaves the model's ``users`` table exactly as it found it.

    The fixture is the table ``Base.metadata.create_all`` builds, which is what
    both shipped development databases have. After a full upgrade it must still
    agree with the model on columns, types, nullability, foreign keys, and
    indexes -- the baseline adds nothing it already has and rewrites nothing it
    already has, so there is no residue to explain away.

    (A table adopted from the pre-rename shape legitimately keeps a nullable
    ``name``, because SQLite cannot enforce ``NOT NULL`` with ``ALTER TABLE``.
    That case is covered by
    ``test_baseline_backfills_an_adopted_users_row_that_has_no_name``; asserting
    zero drift here would be asserting a rewrite this revision must not perform.)

    ``compare_server_default`` is off because a revision may set a
    ``server_default`` where the model uses a Python-side default; on SQLite the
    two are the same value with no behavioural difference.
    """
    database = tmp_path / "users_drift.db"
    _run(database, CANONICAL_USERS_TABLE + COMPLETE_PROBLEMS_TABLE + PROBLEM_INSERT)

    _upgrade_to_head(database)

    differences = _differences(database)
    assert _unreadable(differences) == []
    assert [d for d in differences if _touches(d, "users")] == []


# ---------------------------------------------------------------------------
# A4: c_submission_records and the judged_at it used to destroy
# ---------------------------------------------------------------------------


def test_the_rebuild_preserves_judged_at(tmp_path: Path) -> None:
    """A judged submission keeps its judging time across ``c_submission_records``.

    ``c`` rebuilds ``submissions`` from a fixed ``copy_from`` shape, and Alembic
    copies exactly the columns that shape names. A column missing from it is
    dropped by the rebuild and then re-added empty by ``e_judged_submissions``: the
    shape came out right and every timestamp was gone, with nothing reporting it.
    This asserts the value, not the column's existence.
    """
    database = tmp_path / "judged.db"
    _provision_with_create_all(database)
    _run(database, USER_INSERT + PROBLEM_INSERT + SUBMISSION_INSERT)
    # Park the database immediately before the revision that rebuilds the table,
    # which is where a `create_all`-provisioned development database sits once it
    # has been stamped at all.
    _stamp(database, "b_progress_learner_tracking")

    with _connect(database) as connection:
        before = connection.execute(
            f"SELECT {JUDGED_RECORD_SELECT} FROM submissions WHERE id = 1"
        ).fetchone()
    assert before is not None
    assert before[-1] == "2026-02-01 10:00:01"

    _upgrade_to_head(database)

    with _connect(database) as connection:
        after = connection.execute(
            f"SELECT {JUDGED_RECORD_SELECT} FROM submissions WHERE id = 1"
        ).fetchone()
    assert after is not None
    # The headline assertion: the judging time is still that judging time.
    assert after[-1] == "2026-02-01 10:00:01"
    # And the rest of the record came through untouched, so this is a test that the
    # data survived rather than that the column is still declared.
    assert after == before
    assert _version(database) == EXPECTED_HEAD
    assert _foreign_key_violations(database) == []
    assert {
        "ix_submissions_user_id",
        "ix_submissions_problem_id",
        "ix_submissions_status",
        "ix_submissions_submitted_at",
        "ix_submissions_user_submitted_at",
    } <= _indexes(database, "submissions")


def test_the_rebuild_preserves_judged_at_for_every_row(tmp_path: Path) -> None:
    """Preservation is per-row, not a lucky single row.

    One row could survive by being the one the copy happened to touch. Three rows
    with three different judging times, plus one that was never judged, cannot.
    """
    database = tmp_path / "judged_many.db"
    _provision_with_create_all(database)
    _run(
        database,
        USER_INSERT
        + PROBLEM_INSERT
        + """
        INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
            VALUES (2, 'Dev Two', 'dev2@example.com', 'argon2-hash', '2026-01-01', '2026-01-01');
        """
        + """
        INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                                 test_cases_passed, test_cases_total, runtime_ms, memory_mb,
                                 error_message, submitted_at, judged_at)
            VALUES (1, 1, 1, 'python', 'a', 'accepted', 1, 1, 5, 3, NULL,
                    '2026-02-01 10:00:00', '2026-02-01 10:00:01'),
                   (2, 2, 1, 'javascript', 'b', 'wrong_answer', 0, 2, 8, 4, NULL,
                    '2026-02-02 11:00:00', '2026-02-02 11:00:09'),
                   (3, 1, 1, 'python', 'c', 'queued', NULL, NULL, NULL, NULL, NULL,
                    '2026-02-03 12:00:00', NULL);
        """,
    )
    _stamp(database, "b_progress_learner_tracking")

    with _connect(database) as connection:
        before = connection.execute(
            f"SELECT {JUDGED_RECORD_SELECT} FROM submissions ORDER BY id"
        ).fetchall()

    _upgrade_to_head(database)

    with _connect(database) as connection:
        after = connection.execute(
            f"SELECT {JUDGED_RECORD_SELECT} FROM submissions ORDER BY id"
        ).fetchall()
    assert [row[-1] for row in before] == [
        "2026-02-01 10:00:01",
        "2026-02-02 11:00:09",
        None,
    ]
    assert after == before


def test_the_rebuild_does_not_invent_a_judging_time(tmp_path: Path) -> None:
    """A stored-but-never-judged row must not acquire one.

    The mirror of the preservation test: keeping a real ``judged_at`` is only
    meaningful if a missing one stays missing, because a fabricated judging time
    would assert a verdict that never happened.
    """
    database = tmp_path / "unjudged.db"
    _provision_with_create_all(database)
    _run(
        database,
        USER_INSERT
        + PROBLEM_INSERT
        + """
        INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                                 submitted_at) VALUES (1, 1, 1, 'python', 'x', 'queued',
                                                       '2026-02-01 10:00:00');
        """,
    )
    _stamp(database, "b_progress_learner_tracking")

    _upgrade_to_head(database)

    with _connect(database) as connection:
        assert connection.execute(
            "SELECT status, judged_at FROM submissions WHERE id = 1"
        ).fetchone() == ("queued", None)


def test_the_rebuild_keeps_generated_insights_that_reference_a_submission(
    tmp_path: Path,
) -> None:
    """A cascade must not take a learner's generated insights with it.

    The rebuild drops and recreates ``submissions``, and ``ai_insights`` declares
    ``ON DELETE CASCADE`` into it. Anything on the far end of that reference has to
    survive the drop.
    """
    database = tmp_path / "insights.db"
    _provision_with_create_all(database)
    _run(
        database,
        USER_INSERT
        + PROBLEM_INSERT
        + SUBMISSION_INSERT
        + """
        INSERT INTO ai_insights (id, user_id, kind, problem_id, submission_id, scope_key,
                                 content, provider, model, grounding, created_at)
            VALUES (1, 1, 'submission_diagnosis', 1, 1, 'deadbeef', 'an answer',
                    'fake', 'a-model', '{}', '2026-02-02 10:00:00');
        """,
    )
    _stamp(database, "b_progress_learner_tracking")

    _upgrade_to_head(database)

    with _connect(database) as connection:
        assert connection.execute(
            "SELECT id, submission_id, content FROM ai_insights"
        ).fetchall() == [(1, 1, "an answer")]


def test_a_pre_release_submissions_table_is_rebuilt_without_inventing_a_verdict(
    tmp_path: Path,
) -> None:
    """The pre-release placeholder table still migrates, honestly.

    ``results`` and ``created_at`` are ``NOT NULL`` with no default, which is why
    the revision rebuilds rather than altering. The submission time has to come
    from ``created_at``, and a status outside the vocabulary has to become
    ``failed`` -- never promoted to a verdict the judge never reached.
    """
    database = tmp_path / "prerelease.db"
    _run(
        database,
        CANONICAL_USERS_TABLE
        + COMPLETE_PROBLEMS_TABLE
        + """
        CREATE TABLE submissions (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            language VARCHAR(40) NOT NULL,
            source_code TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            results JSON NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        );
        """
        + USER_INSERT
        + PROBLEM_INSERT
        + """
        INSERT INTO submissions (id, user_id, problem_id, language, source_code, status,
                                 results, created_at)
            VALUES (1, 1, 1, 'python', 'def solve(): return 3', 'PASSED', '[]',
                    '2024-05-05 08:00:00');
        """,
    )

    _upgrade_to_head(database)

    with _connect(database) as connection:
        row = connection.execute(
            "SELECT status, submitted_at, judged_at FROM submissions WHERE id = 1"
        ).fetchone()
    columns = _columns(database, "submissions")
    assert "results" not in columns
    assert "created_at" not in columns
    assert row == ("failed", "2024-05-05 08:00:00", None)
    assert _foreign_key_violations(database) == []
    assert {
        "ix_submissions_user_id",
        "ix_submissions_problem_id",
        "ix_submissions_status",
        "ix_submissions_submitted_at",
        "ix_submissions_user_submitted_at",
    } <= _indexes(database, "submissions")


#: The one difference a migrated ``submissions`` table is allowed to still have,
#: as ``(operation, table, column)`` from ``_difference_parts``. SQLite has no
#: native timestamp type, so ``ALTER TABLE ... ADD COLUMN ... TIMESTAMP`` (what
#: ``e_judged_submissions`` emits for ``judged_at``) declares a different spelling
#: from the ``DATETIME`` a ``create_all`` database gets, while storing the same
#: instants. Keyed on all three parts, so a new column or a different operation
#: is not quietly absorbed, and the entry can be deleted outright once that
#: cosmetic difference is gone.
TOLERATED_SUBMISSION_DIFFERENCES = {("modify_type", "submissions", "judged_at")}


def _is_tolerated(difference) -> bool:
    """Whether every difference inside one element is explicitly tolerated.

    An element that could not be read is never tolerated. ``_unreadable`` is the
    guard for that case, and defaulting an unreadable element to "fine" here
    would quietly undo it.
    """
    parts = _difference_parts(difference)
    return bool(parts) and set(parts) <= TOLERATED_SUBMISSION_DIFFERENCES


def test_a_migrated_submissions_table_matches_the_model(tmp_path: Path) -> None:
    """``submissions`` is the table these fixes own, so it has to agree exactly.

    Every difference outside :data:`TOLERATED_SUBMISSION_DIFFERENCES` is a real
    disagreement and fails here: a missing column, a wrong nullability, a lost
    index, a dropped check constraint. That is the assertion that would have
    caught ``judged_at`` going missing in the first place, and the one that will
    catch the table drifting from the model again.
    """
    database = tmp_path / "submissions_drift.db"
    _upgrade_to_head(database)

    differences = _differences(database)
    # Read this reader's own blind spot first: if any difference were unreadable,
    # the filter below would match nothing and the assertion would pass for the
    # wrong reason.
    assert _unreadable(differences) == []

    disagreements = [
        difference
        for difference in differences
        if _touches(difference, "submissions") and not _is_tolerated(difference)
    ]
    assert disagreements == []
