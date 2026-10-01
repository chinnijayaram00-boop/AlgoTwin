"""problem catalog and judge data

Grows ``problems`` from the card metadata the initial baseline shipped into a
full judge-ready problem: a statement, an input and output format, a five-level
hint ladder, an editorial, the languages starter code exists for, the complexity
a good solution reaches, per-problem judge limits, the test cases (visible and
hidden), and a reference solution per language.

The upgrade is additive and idempotent, so it is safe on a database already
provisioned by ``Base.metadata.create_all`` and safe to run twice:

* every missing column is added; no column and no row is dropped;
* ``time_limit_ms`` and ``memory_limit_mb`` are ``NOT NULL`` and a table that
  predates them has rows with nothing to read, so both are backfilled in the
  same pass. Without that, the first read of a pre-catalog row would fail
  instead of reporting the default;
* a problem that predates this revision keeps working. It simply has no test
  cases, and the judge reports "this problem has no test data" rather than
  inventing a verdict for it.

Nothing here backfills test cases. Seeding the catalog is the seeder's job
(``database.problem_catalog``), and a test asserts that every seeded problem
carries at least one visible and one hidden case, so a half-populated problem
cannot reach a learner through the catalog endpoint.

``downgrade()`` is intentionally inert, for the same reason the three earlier
revisions are: dropping these columns would destroy problem content and judge
data that no writer could reconstruct. Express any reversal as a new forward
revision instead.

Revision ID: d_problem_catalog
Revises: c_submission_records
Create Date: 2026-09-28 11:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

from database.models.problem import (
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_TIME_LIMIT_MS,
    PROBLEM_ADDED_COLUMNS,
)

revision: str = "d_problem_catalog"
down_revision: str | None = "c_submission_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_column_names() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("problems")}


def _create_problems_with_catalog_columns() -> None:
    """Create the target table for a database that has no ``problems`` table.

    Written out in full because the offline path has no live connection to
    inspect and cannot run the additive statements below. ``if_not_exists`` keeps
    it harmless when the table does already exist.
    """
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
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_format", sa.Text(), nullable=True),
        sa.Column("output_format", sa.Text(), nullable=True),
        sa.Column("hints", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("supported_languages", sa.JSON(), nullable=True),
        sa.Column("expected_time_complexity", sa.String(length=60), nullable=True),
        sa.Column("expected_space_complexity", sa.String(length=60), nullable=True),
        sa.Column(
            "time_limit_ms", sa.Integer(), nullable=False, server_default=str(DEFAULT_TIME_LIMIT_MS)
        ),
        sa.Column(
            "memory_limit_mb", sa.Integer(), nullable=False, server_default=str(DEFAULT_MEMORY_LIMIT_MB)
        ),
        sa.Column("test_cases", sa.JSON(), nullable=True),
        sa.Column("reference_solutions", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_problems_slug", "problems", ["slug"], unique=True, if_not_exists=True)
    op.create_index("ix_problems_difficulty", "problems", ["difficulty"], unique=False, if_not_exists=True)
    op.create_index("ix_problems_is_published", "problems", ["is_published"], unique=False, if_not_exists=True)


def upgrade() -> None:
    if "problems" not in sa.inspect(op.get_bind()).get_table_names():
        _create_problems_with_catalog_columns()
        return

    if context.is_offline_mode():
        # No live connection: the additive path below needs to see which columns
        # exist, so emit the target shape instead.
        _create_problems_with_catalog_columns()
        return

    connection = op.get_bind()
    existing = _existing_column_names()
    for column, ddl in PROBLEM_ADDED_COLUMNS:
        if column not in existing:
            connection.execute(sa.text(f'ALTER TABLE problems ADD COLUMN "{column}" {ddl}'))
        # The column now exists, so the backfill in this same pass can rely on it.
        # Without that, one `alembic upgrade` would leave the limits null and a
        # second one would be needed to fill them in.
        existing.add(column)

    for column, default in (
        ("time_limit_ms", DEFAULT_TIME_LIMIT_MS),
        ("memory_limit_mb", DEFAULT_MEMORY_LIMIT_MB),
    ):
        connection.execute(
            sa.text(f"UPDATE problems SET {column} = :default WHERE {column} IS NULL"),
            {"default": default},
        )


def downgrade():
    """Intentionally inert.

    Dropping these columns would destroy problem content and judge data that no
    writer can reconstruct. Express any reversal as a new forward revision.
    """
