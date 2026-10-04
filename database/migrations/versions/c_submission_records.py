"""submission records

Grows ``submissions`` from the placeholder shape shipped with the initial
baseline into the durable record this release needs: an explicit status
vocabulary, test-case counts, runtime and memory measurements, an error message,
and a submission timestamp.

The upgrade is additive and idempotent, so it is safe on a database already
provisioned by ``Base.metadata.create_all`` and safe to run twice:

* missing columns are added; no row is deleted;
* a pre-release row's ``created_at`` is carried into ``submitted_at``, so a
  submission recorded before the release still has a usable time;
* a status outside the canonical vocabulary is rewritten to ``failed``. The
  placeholder table had no CHECK, and a label the API cannot express is reported
  as unusable rather than silently promoted to a verdict;
* a test-case count that cannot be true (negative, or more passed than run) is
  nulled rather than trusted;
* the placeholder ``results`` JSON blob and its ``created_at`` are dropped.
  Nothing ever read or wrote the blob, and ``submitted_at`` takes over the value
  ``created_at`` held, so neither has anything left to carry;
* the vocabulary and measurement CHECK constraints are added, so a migrated
  database enforces the same rules as one built by ``create_all``;
* the submission indexes are created to match the history query.

On PostgreSQL that is plain ``ALTER TABLE`` statements. SQLite cannot add a
constraint or drop a constraint-bearing column in place, so the table is rebuilt
once in batch mode from the canonical definition, which copies the rows across
and leaves a table identical to the one ``create_all`` would have produced. That
rebuild is *lossless* for every column the database already has, including the
ones a later revision owns: ``judged_at`` is copied when it is present and left
for ``e_judged_submissions`` to add when it is not.

The migration and the start-up upgrader in ``backend.app.db.schema`` perform the
same steps against the same constants, so an ``AUTO_CREATE_TABLES=true``
development database and a migrated deployed database end up identical.

``downgrade()`` drops only what this revision created that carries no data: the
new indexes. The added columns stay, because removing them would destroy recorded
submissions. The retired placeholder columns are not restored, because restoring
them would mean fabricating a value no writer ever produced. Express any further
change as a new forward revision instead.

Revision ID: c_submission_records
Revises: b_progress_learner_tracking
Create Date: 2026-09-26 09:15:00.000000
"""

from collections.abc import Callable, Sequence

import sqlalchemy as sa
from alembic import context, op

from database.models.submission import SUBMISSION_STATUS_VALUES

revision: str = "c_submission_records"
down_revision: str | None = "b_progress_learner_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept identical to backend.app.db.schema.SUBMISSION_ADDED_COLUMNS so the runtime
# upgrader and this revision converge on the same table shape.
ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("test_cases_passed", "INTEGER"),
    ("test_cases_total", "INTEGER"),
    ("runtime_ms", "INTEGER"),
    ("memory_mb", "INTEGER"),
    ("error_message", "TEXT"),
    ("submitted_at", "TIMESTAMP"),
)

# Kept identical to backend.app.db.schema.SUBMISSION_RETIRED_COLUMNS.
RETIRED_COLUMNS: tuple[str, ...] = ("results", "created_at")

# Kept identical to backend.app.db.schema.SUBMISSION_CHECK_CONSTRAINTS, and to the
# CHECK constraints on the `Submission` model.
CHECK_CONSTRAINTS: tuple[tuple[str, str], ...] = (
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

# Kept identical to backend.app.db.schema.SUBMISSION_INDEXES.
INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_submissions_user_id", "user_id"),
    ("ix_submissions_problem_id", "problem_id"),
    ("ix_submissions_status", "status"),
    ("ix_submissions_submitted_at", "submitted_at"),
    ("ix_submissions_user_submitted_at", "user_id, submitted_at"),
)


#: The canonical column set, as ``(name, type factory, nullable)`` in the order
#: ``database.models.submission.Submission`` declares them. The type is a factory
#: rather than an instance because a ``Column`` is parented to the table it is
#: declared on, so a second table has to be described with second objects.
CANONICAL_COLUMNS: tuple[tuple[str, Callable[[], sa.types.TypeEngine], bool], ...] = (
    ("id", lambda: sa.Integer(), False),
    ("user_id", lambda: sa.Integer(), False),
    ("problem_id", lambda: sa.Integer(), False),
    ("language", lambda: sa.String(length=40), False),
    ("source_code", lambda: sa.Text(), False),
    ("status", lambda: sa.String(length=30), False),
    ("test_cases_passed", lambda: sa.Integer(), True),
    ("test_cases_total", lambda: sa.Integer(), True),
    ("runtime_ms", lambda: sa.Integer(), True),
    ("memory_mb", lambda: sa.Integer(), True),
    ("error_message", lambda: sa.Text(), True),
    ("submitted_at", lambda: sa.DateTime(timezone=True), False),
    # Added by ``e_judged_submissions``. Nullable and undefaulted on purpose: a
    # submission that was stored but never judged has no judging time, and
    # inventing one would assert a verdict that never happened.
    ("judged_at", lambda: sa.DateTime(timezone=True), True),
)


def _canonical_columns(names: set[str] | None = None) -> list[sa.Column]:
    """Fresh canonical ``Column`` objects, optionally narrowed to ``names``.

    A fresh object per call is required rather than convenient: SQLAlchemy
    parents a ``Column`` to the first table it is declared on and refuses to
    declare it on a second (``Column object 'id' already assigned to Table
    'submissions'``), which is exactly what happens when the same definition
    describes both the create-from-nothing table and the rebuild copy source.
    """
    specs = CANONICAL_COLUMNS if names is None else [spec for spec in CANONICAL_COLUMNS if spec[0] in names]
    return [sa.Column(name, factory(), nullable=nullable) for name, factory, nullable in specs]


def _canonical_constraints() -> list[sa.Constraint]:
    """Fresh constraints for the canonical table.

    Like a column, a constraint is parented to its table, so these are built per
    call for the same reason :func:`_canonical_columns` does it. Every column
    they name -- ``id``, ``user_id``, ``problem_id``, and the columns the CHECK
    expressions read -- is present in every version of this table, and by the
    time either table is built :func:`_add_missing_columns` has added the rest,
    so all of them apply unconditionally.
    """
    return [
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        *[sa.CheckConstraint(expression, name=name) for name, expression in CHECK_CONSTRAINTS],
    ]


def _canonical_table() -> sa.Table:
    """The exact table this revision is converging on.

    This is the shape ``database.models.submission.Submission`` declares, written
    out here because a migration has to describe the target independently of the
    model it is migrating. :func:`_create_submissions_fresh` creates a database
    with no ``submissions`` table straight from it, which is what makes a fresh
    ``alembic upgrade`` land on the same table ``create_all`` would have built.
    """
    return sa.Table(
        "submissions",
        sa.MetaData(),
        *_canonical_columns(),
        *_canonical_constraints(),
    )


def _copy_source_table(live_columns: set[str]) -> sa.Table:
    """The table the SQLite rebuild copies into: canonical, limited to what exists.

    Alembic's batch rebuild copies every column ``copy_from`` names by selecting
    that same column from the live table, and it does not intersect the two
    itself. A fixed copy source therefore fails in one of two ways, and this
    revision hit both:

    * naming a column the table does not have aborts the migration -- the
      ``INSERT INTO _alembic_tmp_submissions ... SELECT submissions.judged_at``
      cannot resolve a column the live table was never given, because
      ``e_judged_submissions`` adds it *after* this revision runs;
    * omitting a column the table does have silently deletes it. That is how
      ``judged_at`` was lost: a database provisioned by
      ``Base.metadata.create_all`` already carried the column and every recorded
      judging timestamp, the rebuild left it out, and ``e`` afterwards restored
      the column as empty. The shape came out right and the data was gone, with
      nothing reporting it.

    So the source is derived from the table actually in front of us: the
    canonical shape, keeping exactly the columns this database has. A column a
    later revision owns is preserved when it is already there and left for that
    revision to add when it is not, which is the one behaviour that is correct in
    both cases rather than one that trades a crash for a data loss.
    """
    return sa.Table(
        "submissions",
        sa.MetaData(),
        *_canonical_columns(live_columns),
        *_canonical_constraints(),
    )


def _existing_column_names() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("submissions")}


def _existing_check_names() -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("submissions")
    }


def _status_case() -> str:
    """Rewrite any stored status onto the canonical vocabulary.

    Generated from :data:`SUBMISSION_STATUS_VALUES` so this SQL and the Python
    reader in ``database.models.submission`` cannot disagree. An unrecognised
    label becomes ``failed``: reporting a broken record as unusable is the only
    honest reading, and a verdict is never invented.
    """
    branches = " ".join(f"WHEN '{value}' THEN '{value}'" for value in SUBMISSION_STATUS_VALUES)
    return f"CASE LOWER(TRIM(status)) {branches} ELSE 'failed' END"


def _create_submissions_fresh(*, if_not_exists: bool = False) -> None:
    """Create the canonical table outright, for a database that has no submissions."""
    canonical = _canonical_table()
    op.create_table(
        "submissions",
        *canonical.columns,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        *[sa.CheckConstraint(expression, name=name) for name, expression in CHECK_CONSTRAINTS],
        if_not_exists=if_not_exists,
    )
    _ensure_indexes()


def _add_missing_columns() -> None:
    existing = _existing_column_names()
    connection = op.get_bind()
    for column, ddl in ADDED_COLUMNS:
        if column not in existing:
            connection.execute(sa.text(f'ALTER TABLE submissions ADD COLUMN "{column}" {ddl}'))
        # The column now exists, so the backfill in this same pass can rely on it.
        # Without this, one `alembic upgrade` would leave `submitted_at` empty and
        # a second one would be needed to fill it.
        existing.add(column)


def _backfill() -> None:
    """Make the existing rows fit the canonical shape, before it is enforced.

    Runs before the constraints are attached, so a legacy label is rewritten
    before the table starts refusing values outside the vocabulary, and before the
    rebuild, so every row is already legal when it is copied.
    """
    connection = op.get_bind()
    # A row written before the release has no submission time of its own, so the
    # best available evidence is when it was stored.
    if "created_at" in _existing_column_names():
        connection.execute(
            sa.text(
                "UPDATE submissions SET submitted_at = COALESCE"
                " (submitted_at, created_at, CURRENT_TIMESTAMP)"
                " WHERE submitted_at IS NULL"
            )
        )
    else:
        connection.execute(
            sa.text(
                "UPDATE submissions SET submitted_at = CURRENT_TIMESTAMP"
                " WHERE submitted_at IS NULL"
            )
        )

    # The placeholder table had no status constraint, so an unrecognised label
    # can be sitting in a row that predates the vocabulary.
    connection.execute(sa.text(f"UPDATE submissions SET status = {_status_case()}"))

    # A recorded run cannot have passed more cases than it ran, and neither count
    # can be negative.
    for condition, column in (
        ("test_cases_passed IS NOT NULL AND test_cases_passed < 0", "test_cases_passed"),
        ("test_cases_total IS NOT NULL AND test_cases_total < 0", "test_cases_total"),
        ("test_cases_total IS NOT NULL AND test_cases_passed > test_cases_total", "test_cases_passed"),
    ):
        connection.execute(
            sa.text(f"UPDATE submissions SET {column} = NULL WHERE {condition}")
        )


def _rebuild_sqlite_submissions() -> None:
    """Rebuild ``submissions`` from the canonical definition, rows intact.

    ``recreate="always"`` is what forces the rebuild even though no column
    operation is queued: the point is the target schema, not a column edit. The
    copy source is derived from the live table by :func:`_copy_source_table`, so
    a column this revision does not own -- ``judged_at``, which
    ``e_judged_submissions`` adds next -- is copied across when the database
    already has it and is left for that revision to add when it does not.

    The retired placeholder columns are dropped by the rebuild, because Alembic
    copies across only the columns the two tables have in common, and their
    values are already carried into ``submitted_at`` by the backfill above.

    Indexes are not carried over by a batch rebuild, so :func:`_ensure_indexes`
    recreates them immediately afterwards.
    """
    with op.batch_alter_table(
        "submissions", copy_from=_copy_source_table(_existing_column_names()), recreate="always"
    ):
        pass


def _retire_columns_in_place() -> None:
    """PostgreSQL equivalent of :func:`_rebuild_sqlite_submissions`."""
    existing = _existing_column_names()
    for name in RETIRED_COLUMNS:
        if name in existing:
            op.execute(sa.text(f'ALTER TABLE submissions DROP COLUMN IF EXISTS "{name}"'))


def _add_missing_checks_in_place() -> None:
    """Attach the constraints a reflected table is missing.

    A database provisioned by ``create_all`` already has them from the model, and
    one rebuilt above has them from :func:`_canonical_table`. This is the path for
    a table that was never constrained at all, and every name is inspected first so
    a repeated upgrade is a no-op.
    """
    missing = [
        (name, expression)
        for name, expression in CHECK_CONSTRAINTS
        if name not in _existing_check_names()
    ]
    for name, expression in missing:
        op.execute(
            sa.text(f"ALTER TABLE submissions ADD CONSTRAINT {name} CHECK ({expression})")
        )


def _ensure_indexes() -> None:
    for name, columns in INDEXES:
        op.create_index(name, "submissions", columns.split(", "), unique=False, if_not_exists=True)


def upgrade() -> None:
    if context.is_offline_mode():
        # There is no live connection to inspect, so the additive path cannot run
        # against an unknown table. Emit the target shape instead; `if_not_exists`
        # keeps it harmless on a database that already has it.
        _create_submissions_fresh(if_not_exists=True)
        return

    if "submissions" not in sa.inspect(op.get_bind()).get_table_names():
        _create_submissions_fresh()
        return

    _add_missing_columns()
    _backfill()
    if op.get_bind().dialect.name == "sqlite":
        # One rebuild gives the canonical columns, their nullability, the foreign
        # keys, and the constraints in a single deterministic step.
        _rebuild_sqlite_submissions()
    else:
        _retire_columns_in_place()
        _add_missing_checks_in_place()
    _ensure_indexes()


def downgrade() -> None:
    """Reverse the parts of this revision that carry no data.

    The indexes are dropped, which is safe. The added columns stay, because
    dropping them would destroy recorded submissions -- the same reasoning the two
    earlier revisions use. The retired placeholder columns are not restored,
    because restoring them would mean inventing a value no writer ever produced.
    """
    present = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("submissions")}
    for name, _ in INDEXES:
        if name in present:
            op.drop_index(name, table_name="submissions")
