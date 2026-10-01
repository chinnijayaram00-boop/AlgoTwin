"""judged submission records

Adds ``judged_at`` to ``submissions`` so a judged submission records *when the
judge answered*, which is a different instant from ``submitted_at`` (when the
learner sent the code). Without it, a submission that spent most of a second
spawning a worker process would be indistinguishable from one judged instantly,
and "how long did judging take" would be unanswerable from the record.

The upgrade is additive and idempotent, so it is safe on a database already
provisioned by ``Base.metadata.create_all`` and safe to run twice. It adds one
nullable column and touches nothing else: no column and no row is dropped, no
existing value is rewritten, and every stored submission keeps its status,
measurements, and source.

``downgrade`` is intentionally inert. Dropping the column would destroy the
judging timestamps of every recorded attempt, and this repository has never
downgraded a column that holds learner data -- see ``c_submission_records`` for
the same decision applied to the measurement columns.

Revision ID: e_judged_submissions
Revises: d_problem_catalog
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "e_judged_submissions"
down_revision = "d_problem_catalog"
branch_labels = None
depends_on = None

#: ``(column_name, DDL type)`` for every column this revision adds, matching the
#: additive style of ``c_submission_records``.
ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    # Nullable with no default: a submission that was never judged has no
    # judging time, and inventing one for existing rows would assert a judge
    # verdict that never happened.
    ("judged_at", "TIMESTAMP"),
)


def _existing_column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("submissions")}


def _add_missing_columns() -> None:
    """Add every column this revision introduces that the table does not have.

    Idempotent: a column that already exists is skipped, so running the upgrade
    twice is harmless, and a database provisioned by ``Base.metadata.create_all``
    -- which already has ``judged_at`` -- is left alone.
    """
    existing = _existing_column_names()
    connection = op.get_bind()
    for column, ddl in ADDED_COLUMNS:
        if column not in existing:
            connection.execute(sa.text(f'ALTER TABLE submissions ADD COLUMN "{column}" {ddl}'))
        existing.add(column)


def upgrade() -> None:
    if context.is_offline_mode():
        # There is no live connection to inspect, so the additive path cannot run
        # against an unknown table. Emit the target shape instead; the guard in
        # the online path keeps it harmless on a database that already has it.
        _add_missing_columns()
        return

    if "submissions" not in sa.inspect(op.get_bind()).get_table_names():
        # Nothing to alter. A database without submissions either predates
        # `c_submission_records` or is fresh; in both cases the base
        # ``create_all``/``c_submission_records`` path owns the table shape, and
        # skipping here avoids failing on a table that does not exist yet.
        return

    _add_missing_columns()


def downgrade() -> None:
    """Do nothing.

    The column holds judging timestamps for learner submissions. Dropping it
    would destroy recorded history, so this revision -- like the ones before it --
    is forward-only.
    """
