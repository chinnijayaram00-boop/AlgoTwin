"""AI insight records

Adds ``ai_insights``: the table behind the grounded AI coach's three endpoints. A
row is a generation record -- who asked, about what, what came back, which provider
and model produced it, and exactly which safe facts were sent to produce it.

Design points worth stating here, because they are constraints rather than
details:

* **``scope_key`` is a digest of the prompt, not a version number.** It is a
  SHA-256 over the provider, model, kind, and the rendered instructions. Any change
  to a grounded fact changes the digest, so an edited editorial or a re-judged
  submission misses the cache instead of serving an answer about the previous input.
  Nothing outside this module has to remember to invalidate anything, which is the
  failure mode a hand-maintained version invites. It is also one-way, so a digest
  computed over a prompt containing a learner's source code cannot be reversed into
  that source.
* **The uniqueness is ``(user_id, scope_key)``.** The lookup is always "the answer
  *this learner* got for *this exact request*", so this index is the query, and two
  learners never contend for one row. It also makes a double charge for one request
  impossible: two concurrent requests for the same scope cannot both insert.
* **``grounding`` records only safe facts.** Test case inputs, expected outputs,
  the program's output, and reference solutions are never placed in it, because the
  service that builds it never puts them in. The column exists so a grounding
  complaint can be answered from the record.
* **Attribution is stored, not derived.** A row keeps reporting the model that
  actually wrote it, so switching models does not silently reattribute answers.

The upgrade is additive and idempotent, so it is safe on a database already
provisioned by ``Base.metadata.create_all`` and safe to run twice. It creates one
new table and touches nothing else: no existing table is altered, no existing row
is read or rewritten.

``downgrade`` is intentionally inert. Every row is a paid-for generation result
and deleting the table destroys this learner's generated insights irrecoverably, so
-- as with every revision here that would drop learner data -- this is forward-only.

Revision ID: f_ai_insights
Revises: e_judged_submissions
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f_ai_insights"
down_revision = "e_judged_submissions"
branch_labels = None
depends_on = None

TABLE_NAME = "ai_insights"


def _table_exists() -> bool:
    return TABLE_NAME in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    """Create ``ai_insights`` if this release has not already created it.

    The check is a separate statement from the create rather than a ``checkfirst``
    flag, because the indexes below would then still be attempted against a table
    that was already there. Checking once at the top makes "already provisioned" --
    by ``create_all``, or by a previous run of this revision -- a clean no-op, and
    it is the same idempotence guarantee every other revision in this repository
    makes.
    """
    if _table_exists():
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=True),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("grounding", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Both cascades, not just the user: a generated insight about a retired
        # problem is an insight about something that can no longer be read, and one
        # about a deleted submission refers to a verdict that no longer exists.
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_ai_insights_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["problem_id"], ["problems.id"], name="fk_ai_insights_problem_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name="fk_ai_insights_submission_id",
            ondelete="CASCADE",
        ),
        # The vocabulary as a real constraint, so a direct SQL session cannot store
        # a kind the API cannot read back. Written literally because a SQL CHECK
        # cannot reference a Python enum.
        sa.CheckConstraint(
            "kind IN ('problem_explanation', 'submission_diagnosis', 'code_complexity')",
            name="ck_ai_insights_kind",
        ),
    )

    # The cache contract: one answer per request scope per learner.
    op.create_index("ix_ai_insights_scope_key", TABLE_NAME, ["scope_key"], unique=False)
    op.create_index("ix_ai_insights_user_id", TABLE_NAME, ["user_id"], unique=False)
    op.create_index("ix_ai_insights_user_kind", TABLE_NAME, ["user_id", "kind"], unique=False)
    op.create_index("ix_ai_insights_user_created", TABLE_NAME, ["user_id", "created_at"], unique=False)
    op.create_index("ix_ai_insights_problem_id", TABLE_NAME, ["problem_id"], unique=False)
    op.create_index("ix_ai_insights_submission_id", TABLE_NAME, ["submission_id"], unique=False)
    op.create_index("ix_ai_insights_created_at", TABLE_NAME, ["created_at"], unique=False)
    op.create_index(
        "uq_ai_insights_user_scope", TABLE_NAME, ["user_id", "scope_key"], unique=True
    )


def downgrade() -> None:
    """Do nothing.

    The table holds generated insights a learner has already been shown. Dropping
    it would destroy that history irrecoverably, and there is no configuration in
    which a schema downgrade is the right way to remove a feature that is switched
    off in settings instead.
    """
