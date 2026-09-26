"""learner progress tracking

Grows ``progress`` from the placeholder shape shipped with the initial
baseline into the full learner record: an explicit three-value status, an
attempt counter, runtime and memory bests, and separate attempt/solve/creation
timestamps.

The upgrade is additive and idempotent, so it is safe on a database already
provisioned by ``Base.metadata.create_all``:

* missing columns are added; no column or row is dropped;
* legacy status labels are rewritten onto the canonical vocabulary
  (``in_progress`` -> ``attempted``, ``completed`` -> ``solved``), so no record
  is left in a state the API cannot express;
* legacy ``completed_at`` and ``best_time_ms`` values are carried into
  ``solved_at`` and ``best_runtime_ms`` rather than discarded;
* a composite ``(user_id, status)`` index backs the summary query.

``ck_progress_status`` is added on PostgreSQL only. SQLite cannot attach a
CHECK constraint to an existing table without rebuilding it, and rebuilding a
learner table is not a risk worth taking, so on SQLite the status vocabulary is
enforced by the request schema and the service layer instead.

``downgrade()`` is intentionally inert for the same reason as the baseline:
reversing this would mean dropping recorded learner progress.

Revision ID: b_progress_learner_tracking
Revises: 533005ea0596
Create Date: 2026-09-25 23:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

from database.models.progress import LEGACY_STATUS_MAP, PROGRESS_STATUS_VALUES

revision: str = "b_progress_learner_tracking"
down_revision: str | None = "533005ea0596"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept identical to backend.app.db.schema.PROGRESS_ADDED_COLUMNS so the runtime
# upgrader and this revision converge on the same table shape.
ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("attempts_count", "INTEGER NOT NULL DEFAULT 0"),
    ("best_runtime_ms", "INTEGER"),
    ("best_memory_mb", "INTEGER"),
    ("last_attempted_at", "TIMESTAMP"),
    ("solved_at", "TIMESTAMP"),
    ("created_at", "TIMESTAMP"),
)


def _existing_column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _status_backfill_case() -> str:
    branches = " ".join(
        f"WHEN '{legacy}' THEN '{current}'" for legacy, current in LEGACY_STATUS_MAP.items()
    )
    return f"CASE status {branches} ELSE 'not_started' END"


def _add_missing_columns(existing: set[str]) -> None:
    connection = op.get_bind()
    for column, ddl in ADDED_COLUMNS:
        if column not in existing:
            connection.execute(sa.text(f'ALTER TABLE progress ADD COLUMN "{column}" {ddl}'))
        # The column now exists, so the backfill in this same pass can rely on
        # it. Without this a single ``alembic upgrade`` would leave a recorded
        # ``best_time_ms`` behind instead of carrying it across.
        existing.add(column)


def _backfill(existing: set[str]) -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE progress SET created_at = COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)"
            " WHERE created_at IS NULL"
        )
    )
    connection.execute(
        sa.text(f"UPDATE progress SET status = {_status_backfill_case()} WHERE status IS NOT NULL")
    )
    connection.execute(
        sa.text(
            "UPDATE progress SET last_attempted_at = COALESCE(last_attempted_at, updated_at)"
            " WHERE status IN ('attempted', 'solved')"
        )
    )
    if "completed_at" in existing:
        # The old table recorded when a learner completed a problem in
        # `completed_at`, so that is better evidence than `updated_at`. It runs
        # first so the fallback below only fills the remaining gaps.
        connection.execute(
            sa.text(
                "UPDATE progress SET solved_at = completed_at"
                " WHERE status = 'solved' AND solved_at IS NULL AND completed_at IS NOT NULL"
            )
        )
    connection.execute(
        sa.text(
            "UPDATE progress SET solved_at = COALESCE(solved_at, updated_at)"
            " WHERE status = 'solved' AND solved_at IS NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE progress SET attempts_count = 1"
            " WHERE (attempts_count IS NULL OR attempts_count < 1)"
            "   AND status IN ('attempted', 'solved')"
        )
    )
    connection.execute(sa.text("UPDATE progress SET attempts_count = 0 WHERE attempts_count IS NULL"))

    if "best_time_ms" in existing and "best_runtime_ms" in existing:
        # Preserve the only runtime measurement the old column ever held.
        connection.execute(
            sa.text(
                "UPDATE progress SET best_runtime_ms = best_time_ms"
                " WHERE best_runtime_ms IS NULL AND best_time_ms IS NOT NULL"
            )
        )


def _add_status_check() -> None:
    """Add the status vocabulary as a real database constraint.

    The application already rejects an unknown status, but a constraint is the
    last line of defence: it holds for any writer, including a direct SQL
    session or a future import script. It is applied on every backend so a
    migrated database matches one built by ``create_all``.

    SQLite cannot ``ALTER TABLE ... ADD CONSTRAINT``, so the constraint is added
    through batch mode, which rebuilds the table and copies the rows across.
    PostgreSQL gets the cheap direct ``ALTER``.
    """
    bind = op.get_bind()
    names = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints("progress")
    }
    if "ck_progress_status" in names:
        return

    values = ", ".join(f"'{value}'" for value in PROGRESS_STATUS_VALUES)
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(f"ALTER TABLE progress ADD CONSTRAINT ck_progress_status CHECK (status IN ({values}))")
        )
        return

    with op.batch_alter_table("progress") as batch_op:
        batch_op.create_check_constraint(
            "ck_progress_status", sa.text(f"status IN ({values})")
        )


def upgrade() -> None:
    if "progress" not in sa.inspect(op.get_bind()).get_table_names():
        if context.is_offline_mode():
            op.create_table(
                "progress",
                sa.Column("id", sa.Integer(), nullable=False),
                sa.Column("user_id", sa.Integer(), nullable=False),
                sa.Column("problem_id", sa.Integer(), nullable=False),
                sa.Column("status", sa.String(length=30), nullable=False),
                sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("best_runtime_ms", sa.Integer(), nullable=True),
                sa.Column("best_memory_mb", sa.Integer(), nullable=True),
                sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint("user_id", "problem_id", name="uq_progress_user_problem"),
                sa.CheckConstraint(
                    "status IN ('not_started', 'attempted', 'solved')",
                    name="ck_progress_status",
                ),
            )
            op.create_index("ix_progress_user_id", "progress", ["user_id"], unique=False, if_not_exists=True)
            op.create_index("ix_progress_problem_id", "progress", ["problem_id"], unique=False, if_not_exists=True)
            op.create_index(
                "ix_progress_user_status", "progress", ["user_id", "status"], unique=False, if_not_exists=True
            )
        return

    if context.is_offline_mode():
        return

    existing = _existing_column_names("progress")
    _add_missing_columns(existing)
    _backfill(existing)
    # The constraint is added first: on SQLite it rebuilds the table, and doing
    # that before the composite index keeps the index definition applied to the
    # final table shape.
    _add_status_check()
    op.create_index(
        "ix_progress_user_status", "progress", ["user_id", "status"], unique=False, if_not_exists=True
    )


def downgrade() -> None:
    """Intentionally inert.

    Dropping the learner progress columns would destroy recorded attempts and
    solve dates. Express any reversal as a new forward revision instead.
    """
