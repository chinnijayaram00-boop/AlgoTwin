"""initial schema baseline

Establishes the canonical AlgoTwin schema and adopts databases that were
originally provisioned by ``Base.metadata.create_all`` rather than by Alembic.

The baseline is deliberately non-destructive:

* tables and indexes are created with ``if_not_exists=True`` so an already
  provisioned database is adopted rather than rejected;
* a pre-existing ``users`` table is upgraded in place. Legacy ``display_name``
  rows are carried over to ``name`` rather than dropped, so no learner data is
  lost and the unique email index is created once the column set is canonical;
* ``downgrade()`` is intentionally inert. This revision may adopt real user
  rows, so reversing it would mean dropping live data. Undo schema changes with
  a follow-up forward revision instead.

In offline (``--sql``) mode there is no live connection to inspect, so the
migration emits the fresh-database DDL path.

Revision ID: 533005ea0596
Revises:
Create Date: 2026-09-25 23:02:30.867834
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "533005ea0596"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANONICAL_USER_COLUMNS = ("name", "password_hash", "created_at", "updated_at")


def _existing_table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _create_problems() -> None:
    op.create_table(
        "problems",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("starter_code", sa.JSON(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_problems_slug", "problems", ["slug"], unique=True, if_not_exists=True)
    op.create_index("ix_problems_difficulty", "problems", ["difficulty"], unique=False, if_not_exists=True)
    op.create_index("ix_problems_is_published", "problems", ["is_published"], unique=False, if_not_exists=True)


def _create_users_fresh() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )


def _add_missing_user_columns(existing: set[str]) -> None:
    connection = op.get_bind()
    for column, ddl in (
        ("name", 'ALTER TABLE users ADD COLUMN "name" VARCHAR(120)'),
        ("password_hash", 'ALTER TABLE users ADD COLUMN "password_hash" VARCHAR(255)'),
        ("created_at", 'ALTER TABLE users ADD COLUMN "created_at" TIMESTAMP'),
        ("updated_at", 'ALTER TABLE users ADD COLUMN "updated_at" TIMESTAMP'),
    ):
        if column not in existing:
            connection.execute(sa.text(ddl))


def _backfill_user_columns() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE users SET name = COALESCE(display_name, email, 'Learner') WHERE name IS NULL")
    )
    connection.execute(sa.text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
    connection.execute(
        sa.text("UPDATE users SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
    )


def _tighten_users_on_postgres() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("ALTER TABLE users ALTER COLUMN name SET NOT NULL"))
    connection.execute(sa.text("ALTER TABLE users ALTER COLUMN created_at SET NOT NULL"))
    connection.execute(sa.text("ALTER TABLE users ALTER COLUMN updated_at SET NOT NULL"))
    connection.execute(sa.text("ALTER TABLE users ALTER COLUMN display_name DROP NOT NULL"))


def _create_users() -> None:
    if "users" not in _existing_table_names():
        _create_users_fresh()
        return

    existing = _existing_column_names("users")
    _add_missing_user_columns(existing)
    _backfill_user_columns()

    # SQLite cannot relax or enforce NOT NULL with ALTER TABLE, so an adopted
    # legacy table keeps a nullable `name`. The runtime schema upgrader in
    # backend.app.db.schema normalises it on next startup.
    if op.get_bind().dialect.name == "postgresql" and "display_name" in existing:
        _tighten_users_on_postgres()


def _create_progress() -> None:
    op.create_table(
        "progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("best_time_ms", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "problem_id", name="uq_progress_user_problem"),
        if_not_exists=True,
    )
    op.create_index("ix_progress_user_id", "progress", ["user_id"], unique=False, if_not_exists=True)
    op.create_index("ix_progress_problem_id", "progress", ["problem_id"], unique=False, if_not_exists=True)


def _create_submissions() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=40), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"], unique=False, if_not_exists=True)
    op.create_index("ix_submissions_problem_id", "submissions", ["problem_id"], unique=False, if_not_exists=True)
    op.create_index("ix_submissions_status", "submissions", ["status"], unique=False, if_not_exists=True)


def upgrade() -> None:
    _create_problems()
    if context.is_offline_mode():
        _create_users_fresh()
    else:
        _create_users()
    op.create_index("ix_users_email", "users", ["email"], unique=True, if_not_exists=True)
    _create_progress()
    _create_submissions()


def downgrade() -> None:
    """Intentionally inert.

    This baseline may have adopted pre-existing tables holding real rows, so
    dropping them would destroy learner data. Reversal is expressed as a new
    forward revision instead.
    """
