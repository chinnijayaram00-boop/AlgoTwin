"""Mock interview sessions and their recorded question selections

Adds ``interview_sessions`` and ``interview_questions``: the tables behind the
Mock Interview feature. A session row describes one timed rehearsal (its state,
its timer window, its calibration), and the question rows record *which*
published problems were drawn and in what order, plus a link to the judge's
submission for each answered question.

Design points worth stating here, because they are constraints rather than
details:

* **The selection is durable before the session can run.** ``interview_sessions``
  and ``interview_questions`` are written together at creation, so a session's
  problems are always recorded and never re-derivable from the request. The two
  unique pairs -- ``(session_id, position)`` and ``(session_id, problem_id)`` --
  make a duplicated or reordered selection impossible.
* **Verdicts come from the judge, not from this table.** ``submission_id``
  references ``submissions`` with ``ON DELETE SET NULL``, so if a judged
  submission record ever disappears the question keeps existing and simply
  carries no linked verdict. This revision touches nothing in ``submissions`` and
  does not copy a verdict anywhere.
* **The lifecycle is a CHECK.** A session can only ever hold
  ``'created' | 'in_progress' | 'completed' | 'abandoned'``, and a question only
  ``'pending' | 'submitted'``, so a direct SQL session cannot store a state the
  API cannot read back.
* **The score is bounded.** ``score`` may be NULL (a session that has not been
  completed) or a 0-100 percentage, written only at completion.
* **The timer is server-owned.** ``started_at`` and ``expires_at`` are written
  once, by ``start``; the application derives remaining time from the stored
  expiry against the server clock -- no client-supplied remaining time is
  stored anywhere in this revision.

The upgrade is additive and idempotent, so it is safe on a database already
provisioned by ``Base.metadata.create_all`` and safe to run twice. It creates two
new tables and touches nothing else: no existing table is altered, no existing
row is read or rewritten.

``downgrade`` is intentionally inert. The question rows are a learner's recorded
interview history -- which problems were drawn, what the judge reported --
and dropping the tables destroys that irrecoverably, so -- as with every revision
here that would drop learner data -- this is forward-only.

Revision ID: g_interview_sessions
Revises: f_ai_insights
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g_interview_sessions"
down_revision = "f_ai_insights"
branch_labels = None
depends_on = None

SESSIONS_TABLE = "interview_sessions"
QUESTIONS_TABLE = "interview_questions"


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    """Create the two interview tables if this release has not already created them.

    The checks are separate statements from the creates rather than a
    ``checkfirst`` flag, because the indexes and constraints below would then
    still be attempted against a table that was already there. Checking once at
    the top makes "already provisioned" -- by ``create_all``, or by a previous run
    of this revision -- a clean no-op, and it is the same idempotence guarantee
    every other revision in this repository makes.
    """
    if not _table_exists(SESSIONS_TABLE):
        op.create_table(
            SESSIONS_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("role", sa.String(80), nullable=False),
            sa.Column("level", sa.String(30), nullable=True),
            sa.Column("difficulty", sa.String(20), nullable=True),
            sa.Column("topic", sa.String(80), nullable=True),
            sa.Column("question_count", sa.Integer(), nullable=False),
            sa.Column("duration_seconds", sa.Integer(), nullable=False),
            sa.Column("current_index", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_interview_sessions_user_id", ondelete="CASCADE"),
            sa.CheckConstraint(
                "status IN ('created', 'in_progress', 'completed', 'abandoned')",
                name="ck_interview_sessions_status",
            ),
            sa.CheckConstraint(
                "score IS NULL OR (score >= 0 AND score <= 100)",
                name="ck_interview_sessions_score",
            ),
            sa.CheckConstraint(
                "question_count >= 1 AND question_count <= 10",
                name="ck_interview_sessions_question_count",
            ),
            sa.CheckConstraint(
                "duration_seconds >= 300 AND duration_seconds <= 7200",
                name="ck_interview_sessions_duration_seconds",
            ),
            sa.CheckConstraint(
                "current_index >= 0",
                name="ck_interview_sessions_current_index",
            ),
        )
        op.create_index(
            "ix_interview_sessions_user_id", SESSIONS_TABLE, ["user_id"], unique=False
        )
        op.create_index(
            "ix_interview_sessions_status", SESSIONS_TABLE, ["status"], unique=False
        )
        op.create_index(
            "ix_interview_sessions_user_status",
            SESSIONS_TABLE,
            ["user_id", "status"],
            unique=False,
        )
        op.create_index(
            "ix_interview_sessions_user_created",
            SESSIONS_TABLE,
            ["user_id", "created_at"],
            unique=False,
        )

    if not _table_exists(QUESTIONS_TABLE):
        op.create_table(
            QUESTIONS_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("problem_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("submission_id", sa.Integer(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["session_id"], ["interview_sessions.id"], name="fk_interview_questions_session_id", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["problem_id"], ["problems.id"], name="fk_interview_questions_problem_id", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["submission_id"], ["submissions.id"], name="fk_interview_questions_submission_id", ondelete="SET NULL"
            ),
            sa.UniqueConstraint(
                "session_id", "position", name="uq_interview_questions_session_position"
            ),
            sa.UniqueConstraint(
                "session_id", "problem_id", name="uq_interview_questions_session_problem"
            ),
            sa.CheckConstraint("position >= 0", name="ck_interview_questions_position"),
            sa.CheckConstraint("attempts >= 0", name="ck_interview_questions_attempts"),
            sa.CheckConstraint(
                "status IN ('pending', 'submitted')", name="ck_interview_questions_status"
            ),
        )
        op.create_index(
            "ix_interview_questions_session_id", QUESTIONS_TABLE, ["session_id"], unique=False
        )
        op.create_index(
            "ix_interview_questions_problem_id", QUESTIONS_TABLE, ["problem_id"], unique=False
        )
        op.create_index(
            "ix_interview_questions_submission_id", QUESTIONS_TABLE, ["submission_id"], unique=False
        )


def downgrade() -> None:
    """Do nothing.

    The tables hold a learner's recorded interview history and its judged
    outcomes. Dropping them would destroy that history irrecoverably, and there
    is no configuration in which a schema downgrade is the right way to remove a
    feature that is governed by learner data instead.
    """