from database.models.progress import LEGACY_STATUS_MAP, PROGRESS_STATUS_VALUES
from sqlalchemy import DateTime, String, inspect, text
from sqlalchemy.engine import Engine


def _column_types(bind: Engine) -> tuple[str, str, str]:
    return (
        String(120).compile(dialect=bind.dialect),
        String(255).compile(dialect=bind.dialect),
        DateTime(timezone=True).compile(dialect=bind.dialect),
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
