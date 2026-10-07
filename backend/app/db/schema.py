from database.models.ai_insight import AIInsight
from database.models.interview import InterviewQuestion, InterviewSession
from database.models.problem import (
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_TIME_LIMIT_MS,
    PROBLEM_ADDED_COLUMNS,
)
from database.models.progress import LEGACY_STATUS_MAP, PROGRESS_STATUS_VALUES
from database.models.submission import SUBMISSION_STATUS_VALUES, Submission
from sqlalchemy import Column, DateTime, String, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import Dialect


def _column_types(bind: Engine) -> tuple[str, str, str]:
    return (
        String(120).compile(dialect=bind.dialect),
        String(255).compile(dialect=bind.dialect),
        DateTime(timezone=True).compile(dialect=bind.dialect),
    )


def ensure_problem_schema(bind: Engine) -> None:
    """Add the judge columns a pre-catalog ``problems`` table does not have.

    Mirrors the Alembic revision ``d_problem_catalog``. Every step is additive
    and idempotent: a column is added only when it is missing, and no row is
    deleted or rewritten. A problem that predates this release keeps working --
    it simply has no test cases, and the judge reports that a problem has no
    test data rather than inventing a verdict.
    """
    inspector = inspect(bind)
    if "problems" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("problems")}
    missing = [
        (column, ddl) for column, ddl in PROBLEM_ADDED_COLUMNS if column not in existing_columns
    ]
    if not missing:
        return

    with bind.begin() as connection:
        for column, ddl in missing:
            connection.execute(text(f'ALTER TABLE problems ADD COLUMN "{column}" {ddl}'))
        # `time_limit_ms` and `memory_limit_mb` are NOT NULL, and a table that
        # predates them has rows with no value to read, so the backfill has to
        # run in the same pass. Without it the first read of an older row would
        # fail instead of reporting the default.
        connection.execute(
            text(
                "UPDATE problems SET time_limit_ms = :default WHERE time_limit_ms IS NULL"
            ),
            {"default": DEFAULT_TIME_LIMIT_MS},
        )
        connection.execute(
            text(
                "UPDATE problems SET memory_limit_mb = :default WHERE memory_limit_mb IS NULL"
            ),
            {"default": DEFAULT_MEMORY_LIMIT_MB},
        )


def _rebuild_legacy_sqlite_users(bind: Engine, existing_columns: set[str]) -> None:
    string_type, hash_type, date_type = _column_types(bind)
    name_expression = "COALESCE(name, display_name, email, 'Learner')" if "name" in existing_columns else "COALESCE(display_name, email, 'Learner')"
    password_expression = "password_hash" if "password_hash" in existing_columns else "NULL"
    created_expression = "created_at" if "created_at" in existing_columns else "CURRENT_TIMESTAMP"
    updated_expression = (
        f"COALESCE(updated_at, {created_expression}, CURRENT_TIMESTAMP)"
        if "updated_at" in existing_columns
        else f"COALESCE({created_expression}, CURRENT_TIMESTAMP)"
    )

    with bind.connect() as connection:
        foreign_keys_enabled = bool(connection.exec_driver_sql("PRAGMA foreign_keys").scalar())
        connection.commit()
        if foreign_keys_enabled:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(
                f"""
                CREATE TABLE users_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name {string_type} NOT NULL,
                    email VARCHAR(320) NOT NULL,
                    password_hash {hash_type},
                    created_at {date_type} NOT NULL,
                    updated_at {date_type} NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                f"""
                INSERT INTO users_new (id, name, email, password_hash, created_at, updated_at)
                SELECT id, {name_expression}, email, {password_expression}, {created_expression}, {updated_expression}
                FROM users
                """
            )
            connection.exec_driver_sql("DROP TABLE users")
            connection.exec_driver_sql("ALTER TABLE users_new RENAME TO users")
            connection.exec_driver_sql("CREATE UNIQUE INDEX ix_users_email ON users (email)")
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            if foreign_keys_enabled:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()


def _migrate_legacy_postgres_users(bind: Engine, existing_columns: set[str]) -> None:
    string_type, hash_type, date_type = _column_types(bind)
    with bind.begin() as connection:
        if "created_at" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "created_at" {date_type}'))
        if "name" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "name" {string_type}'))
        if "password_hash" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "password_hash" {hash_type}'))
        if "updated_at" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "updated_at" {date_type}'))
        connection.execute(text("UPDATE users SET name = COALESCE(display_name, email, 'Learner') WHERE name IS NULL"))
        connection.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        connection.execute(text("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL"))
        connection.execute(text("ALTER TABLE users ALTER COLUMN display_name DROP NOT NULL"))


def ensure_user_schema(bind: Engine) -> None:
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    if "display_name" in existing_columns:
        if bind.dialect.name == "sqlite":
            _rebuild_legacy_sqlite_users(bind, existing_columns)
        elif bind.dialect.name == "postgresql":
            _migrate_legacy_postgres_users(bind, existing_columns)
        inspector = inspect(bind)
        existing_columns = {column["name"] for column in inspector.get_columns("users")}

    string_type, hash_type, date_type = _column_types(bind)
    with bind.begin() as connection:
        if "created_at" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "created_at" {date_type}'))
        if "name" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "name" {string_type}'))
        if "password_hash" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "password_hash" {hash_type}'))
        if "updated_at" not in existing_columns:
            connection.execute(text(f'ALTER TABLE users ADD COLUMN "updated_at" {date_type}'))
        connection.execute(text("UPDATE users SET name = email WHERE name IS NULL"))
        connection.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        connection.execute(text("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL"))


# Columns the learner progress release added on top of the original table.
PROGRESS_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("attempts_count", "INTEGER NOT NULL DEFAULT 0"),
    ("best_runtime_ms", "INTEGER"),
    ("best_memory_mb", "INTEGER"),
    ("last_attempted_at", "TIMESTAMP"),
    ("solved_at", "TIMESTAMP"),
    ("created_at", "TIMESTAMP"),
)


def _status_backfill_case() -> str:
    """A SQL CASE that rewrites every legacy status label to the new vocabulary.

    Generated from :data:`LEGACY_STATUS_MAP` so the SQL and the Python reader in
    ``database.models.progress`` can never disagree about a legacy value.
    """
    branches = " ".join(
        f"WHEN '{legacy}' THEN '{current}'" for legacy, current in LEGACY_STATUS_MAP.items()
    )
    return f"CASE status {branches} ELSE 'not_started' END"


def ensure_progress_schema(bind: Engine) -> None:
    """Bring an adopted ``progress`` table up to the learner progress shape.

    Mirrors the Alembic revision ``b_progress_learner_tracking``, so a
    ``AUTO_CREATE_TABLES=true`` development database and a migrated deployed
    database end up with the same columns, indexes, and backfilled values. The
    upgrade is additive and idempotent: no row is deleted, and every legacy
    column is left in place for a later revision to drop once no deployment
    still carries it.

    The one intentional difference is the ``ck_progress_status`` CHECK. Alembic
    can attach it to an adopted SQLite table by rebuilding it, and does. Here
    the rebuild is deliberately avoided, because this path runs automatically
    at start-up against a developer's live file, and rebuilding a table to add
    a constraint is not a risk worth taking without a migration to back it up.
    On PostgreSQL the CHECK is added directly, as in the migration. On SQLite
    the vocabulary is still enforced by the strict status validation in the
    progress service, so an unknown label cannot be stored through the API.
    """
    inspector = inspect(bind)
    if "progress" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("progress")}
    with bind.begin() as connection:
        for column, ddl in PROGRESS_ADDED_COLUMNS:
            if column not in existing_columns:
                connection.execute(text(f'ALTER TABLE progress ADD COLUMN "{column}" {ddl}'))
            # The column now exists, so later steps in this same pass can rely on
            # it just as safely as one that was already in the table.
            existing_columns.add(column)

        # A row that predates the release has no separate creation or attempt
        # timestamps, so the best available evidence is its last update.
        connection.execute(
            text(
                "UPDATE progress SET created_at = COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)"
                " WHERE created_at IS NULL"
            )
        )
        connection.execute(
            text(f"UPDATE progress SET status = {_status_backfill_case()} WHERE status IS NOT NULL")
        )
        connection.execute(
            text(
                "UPDATE progress SET last_attempted_at = COALESCE(last_attempted_at, updated_at)"
                " WHERE status IN ('attempted', 'solved')"
            )
        )
        if "completed_at" in existing_columns:
            # The old table recorded when a learner completed a problem in
            # `completed_at`, so that is better evidence than `updated_at`.
            # It runs first so the fallback below only fills the gaps.
            connection.execute(
                text(
                    "UPDATE progress SET solved_at = completed_at"
                    " WHERE status = 'solved' AND solved_at IS NULL AND completed_at IS NOT NULL"
                )
            )
        connection.execute(
            text(
                "UPDATE progress SET solved_at = COALESCE(solved_at, updated_at)"
                " WHERE status = 'solved' AND solved_at IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE progress SET attempts_count = 1"
                " WHERE (attempts_count IS NULL OR attempts_count < 1)"
                "   AND status IN ('attempted', 'solved')"
            )
        )
        connection.execute(text("UPDATE progress SET attempts_count = 0 WHERE attempts_count IS NULL"))

        if "best_time_ms" in existing_columns and "best_runtime_ms" in existing_columns:
            # Preserve the only runtime measurement the old column ever held.
            connection.execute(
                text(
                    "UPDATE progress SET best_runtime_ms = best_time_ms"
                    " WHERE best_runtime_ms IS NULL AND best_time_ms IS NOT NULL"
                )
            )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_progress_user_status"
                " ON progress (user_id, status)"
            )
        )

    if bind.dialect.name == "postgresql":
        # SQLite cannot attach a CHECK constraint to an existing table without
        # rebuilding it. Rebuilding risks learner data, so on SQLite the status
        # is enforced by the request schema and the service instead.
        with bind.begin() as connection:
            constraints = {
                constraint["name"]
                for constraint in inspect(bind).get_check_constraints("progress")
            }
            if "ck_progress_status" not in constraints:
                values = ", ".join(f"'{value}'" for value in PROGRESS_STATUS_VALUES)
                connection.execute(
                    text(
                        "ALTER TABLE progress ADD CONSTRAINT ck_progress_status"
                        f" CHECK (status IN ({values}))"
                    )
                )



# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

# The learner submissions release added these on top of the placeholder table
# shipped with the initial baseline. Kept identical to the Alembic revision
# ``c_submission_records`` so both paths converge on the same shape.
SUBMISSION_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("test_cases_passed", "INTEGER"),
    ("test_cases_total", "INTEGER"),
    ("runtime_ms", "INTEGER"),
    ("memory_mb", "INTEGER"),
("error_message", "TEXT"),
    ("submitted_at", "TIMESTAMP"),
    # The judged-at timestamp, mirroring Alembic revision ``e_judged_submissions``.
    # Nullable and undefaulted: only a judge writes it.
    ("judged_at", "TIMESTAMP"),
)

# The placeholder table is retired. `results` was a JSON blob nothing read or
# wrote, and the release replaces it with the explicit measurement columns above.
# `created_at` was the placeholder's name for the submission time, and
# `submitted_at` takes that value over, so the old column goes rather than being
# left behind as a second, divergent copy of the same fact. Both were declared
# `NOT NULL` with no default, so a canonical insert -- which omits them -- would
# be rejected until they are gone.
SUBMISSION_RETIRED_COLUMNS: tuple[str, ...] = ("results", "created_at")

# The vocabulary and the measurement sanity rules as real database constraints,
# not only application rules, so a direct SQL session or a future import cannot
# store a status the API cannot read back or a run that passed more cases than it
# ran. Mirrors ``Submission.__table_args__``.
SUBMISSION_CHECK_CONSTRAINTS: tuple[tuple[str, str], ...] = (
    (
        "ck_submissions_status",
        (
            "status IN ('queued', 'running', 'accepted', 'wrong_answer', 'runtime_error',"
            " 'compilation_error', 'time_limit_exceeded', 'memory_limit_exceeded', 'failed')"
        ),
    ),
    (
        "ck_submissions_test_case_counts",
        (
            "(test_cases_passed IS NULL OR test_cases_passed >= 0)"
            " AND (test_cases_total IS NULL OR test_cases_total >= 0)"
            " AND (test_cases_passed IS NULL OR test_cases_total IS NULL"
            " OR test_cases_passed <= test_cases_total)"
        ),
    ),
    ("ck_submissions_runtime_ms", "runtime_ms IS NULL OR runtime_ms >= 0"),
    ("ck_submissions_memory_mb", "memory_mb IS NULL OR memory_mb >= 0"),
)

SUBMISSION_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_submissions_user_id", "user_id"),
    ("ix_submissions_problem_id", "problem_id"),
    ("ix_submissions_status", "status"),
    ("ix_submissions_submitted_at", "submitted_at"),
    ("ix_submissions_user_submitted_at", "user_id, submitted_at"),
)

# Columns the rebuilt table carries, in the order the model declares them.
#
# Derived from the model rather than written out, for the reason
# `ensure_ai_insight_schema` gives: there is exactly one definition of this
# table's shape, so the rebuild cannot be handed a stale copy of it. It used to
# be a literal tuple paired with a second literal `column_ddl` mapping, and the
# two disagreed -- `judged_at` was in the tuple and not in the mapping, so
# `_rebuild_sqlite_submissions` died on a `KeyError` and every step after the
# rebuild (the `submitted_at` backfill, retiring the placeholder columns, adding
# the indexes) never ran. Two hand-maintained copies of one shape is the defect;
# one copy read from the model is the fix.
SUBMISSION_CANONICAL_COLUMNS: tuple[str, ...] = tuple(Submission.__table__.columns.keys())


def _submission_column_ddl(column: Column, dialect: Dialect) -> str:
    """Render one model column as a SQLite column definition.

    The type is compiled against the engine's own dialect rather than spelled
    out, so ``DateTime(timezone=True)`` becomes whatever that backend actually
    stores dates as, and nullability and the primary key come from the model
    instead of from a hand-copied list.
    """
    parts = [f'"{column.name}"', column.type.compile(dialect=dialect)]
    if not column.nullable:
        parts.append("NOT NULL")
    if column.primary_key:
        parts.append("PRIMARY KEY")
    return " ".join(parts)


def _submission_foreign_key_ddl(column: Column) -> list[str]:
    """Render the table-level foreign keys one model column declares.

    ``ON DELETE`` is carried across verbatim. It is what makes a removed account
    or problem leave no submissions behind, so dropping it during a rebuild would
    quietly change the table's behaviour rather than just its shape.
    """
    statements = []
    for foreign_key in column.foreign_keys:
        target = foreign_key.column
        on_delete = f" ON DELETE {foreign_key.ondelete}" if foreign_key.ondelete else ""
        statements.append(
            f'FOREIGN KEY("{column.name}")'
            f" REFERENCES {target.table.name}({target.name}){on_delete}"
        )
    return statements


def _submission_status_case() -> str:
    """A SQL CASE that rewrites any stored status onto the canonical vocabulary.

    Generated from :data:`SUBMISSION_STATUS_VALUES` so this SQL and the Python
    reader in ``database.models.submission`` cannot disagree about a value. An
    unrecognised label becomes ``failed``: the placeholder table had no CHECK, so
    a legacy row can hold something the API cannot express, and reporting it as
    unusable is the only honest reading. A verdict is never invented.
    """
    branches = " ".join(f"WHEN '{value}' THEN '{value}'" for value in SUBMISSION_STATUS_VALUES)
    return f"CASE LOWER(TRIM(status)) {branches} ELSE 'failed' END"


def _rebuild_sqlite_submissions(bind: Engine) -> None:
    """Rebuild ``submissions`` on SQLite into the canonical shape, rows intact.

    SQLite cannot ``ALTER TABLE ... ADD CONSTRAINT`` or drop a column it treats
    as constraint-bearing, so the only way to reach the canonical shape -- with
    its vocabulary enforced and its retired columns gone -- is to build the table
    again and copy the rows across. This is the same pattern
    ``_rebuild_legacy_sqlite_users`` already uses at start-up, and the Alembic
    revision ``c_submission_records`` is there to back it up.

    Nothing is lost. Every canonical column is copied when the table already has
    it and filled with the best available evidence when it does not:

    * ``status`` goes through the vocabulary CASE, because a legacy label would
      not fit a table that enforces the vocabulary;
    * ``submitted_at`` falls back to the placeholder's ``created_at``, which was
      the same fact under the old name, and then to the current time;
    * a measurement the table does not have is null, which is the honest value
      for a run that has not been reported;
    * a measurement that could not have happened -- a negative duration, more
      cases passed than run -- is nulled in the copy itself, by the same rules the
      statements below apply afterwards. Copying it verbatim would be rejected by
      the constraints the rebuild is creating, aborting the whole upgrade on the
      exact rows the rules exist to repair.
    """
    existing = {column["name"] for column in inspect(bind).get_columns("submissions")}
    canonical = Submission.__table__
    checks = ", ".join(
        f"CONSTRAINT {name} CHECK ({expression})"
        for name, expression in SUBMISSION_CHECK_CONSTRAINTS
    )

    def measurement(column: str) -> str:
        """A non-negative measurement, with an impossible one already nulled."""
        value = column if column in existing else "NULL"
        return f"CASE WHEN {value} IS NOT NULL AND {value} < 0 THEN NULL ELSE {value} END"

    # Resolved in dependency order: the passed count is judged against the total
    # the copy is actually going to store, not against the stored total, so a
    # negative total that is nulled here cannot condemn the count beside it.
    total_cases = measurement("test_cases_total")
    passed_cases = measurement("test_cases_passed")
    passed_cases = (
        f"CASE WHEN {passed_cases} IS NOT NULL AND {passed_cases} > {total_cases}"
        f" THEN NULL ELSE {passed_cases} END"
    )
    measurements = {
        "test_cases_total": total_cases,
        "test_cases_passed": passed_cases,
        "runtime_ms": measurement("runtime_ms"),
        "memory_mb": measurement("memory_mb"),
    }

    def source_for(column: str) -> str:
        if column in measurements:
            return measurements[column]
        if column == "status":
            return _submission_status_case()
        if column == "submitted_at":
            # `created_at` is the placeholder's name for the same value, so it is
            # the right fallback rather than a guess.
            fallback = "created_at" if "created_at" in existing else None
            parts = [column] if column in existing else []
            if fallback:
                parts.append(fallback)
            parts.append("CURRENT_TIMESTAMP")
            return f"COALESCE({', '.join(parts)})"
        return column if column in existing else "NULL"

    select_list = ", ".join(source_for(column) for column in SUBMISSION_CANONICAL_COLUMNS)
    target_list = ", ".join(f'"{column}"' for column in SUBMISSION_CANONICAL_COLUMNS)
    # Every column and every foreign key is read off the model, so a column added
    # to `Submission` is rebuilt correctly without a second edit here. `judged_at`
    # in particular is copied when the live table already has it, which is what
    # preserves a recorded judging timestamp.
    definitions = ",\n                    ".join(
        _submission_column_ddl(column, bind.dialect) for column in canonical.columns
    )
    foreign_keys = ",\n                    ".join(
        statement for column in canonical.columns for statement in _submission_foreign_key_ddl(column)
    )

    with bind.connect() as connection:
        foreign_keys_enabled = bool(connection.exec_driver_sql("PRAGMA foreign_keys").scalar())
        connection.commit()
        if foreign_keys_enabled:
            # The copy would otherwise trip the foreign keys that point at
            # `submissions` while the table is mid-replacement.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(
                f"""
                CREATE TABLE submissions_rebuilt (
                    {definitions},
                    {foreign_keys},
                    {checks}
                )
                """
            )
            connection.exec_driver_sql(
                f"INSERT INTO submissions_rebuilt ({target_list})"
                f" SELECT {select_list} FROM submissions"
            )
            connection.exec_driver_sql("DROP TABLE submissions")
            connection.exec_driver_sql("ALTER TABLE submissions_rebuilt RENAME TO submissions")
            for name, columns in SUBMISSION_INDEXES:
                connection.exec_driver_sql(f"CREATE INDEX {name} ON submissions ({columns})")
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            if foreign_keys_enabled:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()


def _ensure_submission_indexes(bind: Engine) -> None:
    """Create the submission indexes, skipping any that already exist.

    ``IF NOT EXISTS`` is what makes a repeated start-up a genuine no-op rather
    than an error, and it is safe to call again after a table rebuild in case an
    index was taken with it.
    """
    with bind.begin() as connection:
        for name, columns in SUBMISSION_INDEXES:
            connection.execute(
                text(f"CREATE INDEX IF NOT EXISTS {name} ON submissions ({columns})")
            )


def _drop_retired_submission_columns(bind: Engine, retired: list[str]) -> None:
    """Remove nullable placeholder columns without touching the table shape.

    PostgreSQL can drop a column in place, and so can SQLite as long as the column
    is not referenced by an index or a constraint -- which neither placeholder
    column ever was. The rebuild is reserved for the case that actually needs it:
    SQLite refusing an insert that omits a ``NOT NULL`` column.
    """
    with bind.begin() as connection:
        for name in retired:
            if bind.dialect.name == "postgresql":
                connection.execute(
                    text(f'ALTER TABLE submissions DROP COLUMN IF EXISTS "{name}"')
                )
            else:
                connection.execute(text(f'ALTER TABLE submissions DROP COLUMN "{name}"'))


def _add_submission_checks(bind: Engine, missing: list[tuple[str, str]]) -> None:
    """Add the missing constraints on a backend that can alter in place.

    Only reached on PostgreSQL. SQLite cannot ``ALTER TABLE ... ADD CONSTRAINT``,
    so its missing constraints are resolved by :func:`_rebuild_sqlite_submissions`
    before this point, and the call below is a no-op there.
    """
    with bind.begin() as connection:
        for name, expression in missing:
            connection.execute(
                text(f"ALTER TABLE submissions ADD CONSTRAINT {name} CHECK ({expression})")
            )


def _missing_submission_checks(bind: Engine) -> list[tuple[str, str]]:
    present = {constraint["name"] for constraint in inspect(bind).get_check_constraints("submissions")}
    return [
        (name, expression)
        for name, expression in SUBMISSION_CHECK_CONSTRAINTS
        if name not in present
    ]


def ensure_submission_schema(bind: Engine) -> None:
    """Bring an adopted ``submissions`` table up to the submission-record shape.

    Mirrors the Alembic revision ``c_submission_records``, so an
    ``AUTO_CREATE_TABLES=true`` development database and a migrated deployed
    database end up with the same columns, indexes, constraints, and values.

    The upgrade is additive and idempotent: no row is deleted, and running it
    twice, or running it against a database that is already canonical, changes
    nothing.

    The one structural step is retiring the placeholder columns. A pre-release
    SQLite table declares both ``NOT NULL`` with no default, so it has to be
    rebuilt before a submission can be inserted at all. That rebuild copies every
    row across and the Alembic revision is there to back it up.
    """
    inspector = inspect(bind)
    if "submissions" not in inspector.get_table_names():
        return

    columns = inspector.get_columns("submissions")
    existing_columns = {column["name"] for column in columns}
    retired = [name for name in SUBMISSION_RETIRED_COLUMNS if name in existing_columns]

    has_checks = bool(inspect(bind).get_check_constraints("submissions"))
    if bind.dialect.name == "sqlite" and (retired or not has_checks):
        # A nullable placeholder column could simply be dropped, and a table
        # without the vocabulary enforced could be left alone; neither is worth a
        # rebuild. A ``NOT NULL`` placeholder, or a table with no constraints at
        # all, is.
        nullable = {column["name"]: column["nullable"] for column in columns}
        blocked = [name for name in retired if not nullable.get(name, True)]
        if blocked or not has_checks:
            _rebuild_sqlite_submissions(bind)
            inspector = inspect(bind)
            existing_columns = {column["name"] for column in inspector.get_columns("submissions")}
            retired = [name for name in SUBMISSION_RETIRED_COLUMNS if name in existing_columns]

    with bind.begin() as connection:
        for column, ddl in SUBMISSION_ADDED_COLUMNS:
            if column not in existing_columns:
                connection.execute(text(f'ALTER TABLE submissions ADD COLUMN "{column}" {ddl}'))
            # The column now exists, so later steps in this same pass can rely on
            # it just as safely as one that was already in the table.
            existing_columns.add(column)

        # A row written before the release has no submission time of its own, so
        # the best available evidence is when it was stored. The placeholder
        # called that column `created_at`; the rebuild above has already carried
        # it into `submitted_at` and dropped the old name, so the fallback is
        # only referenced when the column is genuinely still there.
        if "created_at" in existing_columns:
            connection.execute(
                text(
                    "UPDATE submissions SET submitted_at = COALESCE"
                    " (submitted_at, created_at, CURRENT_TIMESTAMP)"
                    " WHERE submitted_at IS NULL"
                )
            )
        else:
            connection.execute(
                text(
                    "UPDATE submissions SET submitted_at = CURRENT_TIMESTAMP"
                    " WHERE submitted_at IS NULL"
                )
            )

        # The placeholder table had no status constraint, so an unrecognised
        # label can be sitting in a row that predates the vocabulary. Report it
        # as `failed` rather than inventing a verdict, matching what the reader
        # in `database.models.submission` does.
        connection.execute(text(f"UPDATE submissions SET status = {_submission_status_case()}"))

        # A recorded run cannot have passed more cases than it ran, and neither
        # count can be negative.
        connection.execute(
            text(
                "UPDATE submissions SET test_cases_passed = NULL"
                " WHERE test_cases_passed IS NOT NULL AND test_cases_passed < 0"
            )
        )
        connection.execute(
            text(
                "UPDATE submissions SET test_cases_total = NULL"
                " WHERE test_cases_total IS NOT NULL AND test_cases_total < 0"
            )
        )
        connection.execute(
            text(
                "UPDATE submissions SET test_cases_passed = NULL"
                " WHERE test_cases_total IS NOT NULL AND test_cases_passed > test_cases_total"
            )
        )

    if retired:
        _drop_retired_submission_columns(bind, retired)

    missing = _missing_submission_checks(bind)
    if missing:
        if bind.dialect.name == "sqlite":
            # Unreachable in practice -- the rebuild above always leaves the
            # constraints in place -- but rebuilding is the only way SQLite can
            # add one, and guessing would corrupt a learner's table.
            _rebuild_sqlite_submissions(bind)
        else:
            _add_submission_checks(bind, missing)

    _ensure_submission_indexes(bind)


# ---------------------------------------------------------------------------
# AI insights
# ---------------------------------------------------------------------------


def ensure_ai_insight_schema(bind: Engine) -> None:
    """Create the ``ai_insights`` table when this release introduces it.

    Mirrors the Alembic revision ``f_ai_insights``, and unlike every other
    ``ensure_*`` function here it does not adopt a legacy shape. This is the
    release that adds the table, so there is no earlier version of it to bring
    forward: the only state to reach is "present" or "absent".

    The DDL comes from the model itself rather than from a hand-written copy.
    Every other function in this module mirrors a table that predates the
    declarative models and therefore has to state its own SQL; here the two
    cannot drift, because there is only one definition. It is also the only
    honest way to reproduce a composite unique constraint, a CHECK over the kind
    vocabulary, and four indexes consistently on SQLite and PostgreSQL.

    Creating a table that does not exist is non-destructive by definition, so
    this runs unconditionally at start-up. It is idempotent: the presence check
    makes a second call a no-op, which also covers a database
    ``Base.metadata.create_all`` has already provisioned.
    """
    if "ai_insights" in inspect(bind).get_table_names():
        return
    AIInsight.__table__.create(bind=bind, checkfirst=True)


# -------------------------------------------------------------------------------
# Mock interviews
# -------------------------------------------------------------------------------


def ensure_interview_schema(bind: Engine) -> None:
    """Create the two interview tables when this release introduces them.

    Mirrors the Alembic revision ``g_interview_sessions``, and like
    :func:`ensure_ai_insight_schema` this does not adopt a legacy shape: there is
    no earlier version of these tables to bring forward, so the only state to
    reach is "present" or "absent".

    The DDL comes from the models themselves rather than from a hand-written
    copy, for the same reason ``ensure_ai_insight_schema`` gives: there is only
    one definition of each table's shape, so the two cannot drift. The question
    table declares foreign keys into the session table, so the session table has
    to exist first.
    """
    tables = set(inspect(bind).get_table_names())
    if "interview_sessions" not in tables:
        InterviewSession.__table__.create(bind=bind, checkfirst=True)
    if "interview_questions" not in tables:
        InterviewQuestion.__table__.create(bind=bind, checkfirst=True)
