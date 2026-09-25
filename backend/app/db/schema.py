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
