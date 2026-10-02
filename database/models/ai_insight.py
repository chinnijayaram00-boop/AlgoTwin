"""One generated AI insight, and the cache key that makes it reusable.

A row here is a *generation record*: who asked, what was asked about, what came
back, which provider and model produced it, and what was sent to produce it. It
is deliberately not a second copy of the catalog. The problem's editorial, the
submission's verdict, and the complexity targets all already exist in their own
tables; storing a copy here would create a second answer to "what is the target
complexity", and the two would drift.

**Grounding is a record of what was sent, and it is bounded by construction.** The
JSON column holds only the safe facts that went into the prompt -- the problem
statement and editorial for an explanation, the stored verdict for a diagnosis,
the loops and nesting depth for a complexity analysis. It never holds test case
inputs, expected outputs, the learner's program output, or a reference solution,
because :mod:`backend.app.ai.redaction` never puts them in. A column that stores
the grounding is a column that can leak, so it exists to make the guarantee
checkable rather than to make the prompt reproducible: ``scope_key`` already
covers reproducibility.

**The cache key is a digest of the prompt, not a hand-maintained version.** It is
a SHA-256 over the provider, the model, the kind, and the exact rendered system and
user instructions. Three consequences, all of them wanted:

* a change to any grounded fact -- a corrected editorial, a re-judged submission,
  edited source -- changes the digest and therefore misses the cache, instead of
  serving an answer about the previous version of the input;
* no separate invalidation logic exists that can be forgotten when a prompt grows a
  new field;
* the key is one-way, so the digest of a prompt containing a learner's source code
  cannot be used to recover that source.

The uniqueness is ``(user_id, scope_key)`` rather than ``scope_key`` alone: the
lookup is always "the latest answer *this learner* got for *this exact request*",
so the index matches the query and two learners never contend for one row. It is
what makes the cache exact rather than best-effort -- two concurrent requests for
the same scope cannot both insert, so a learner cannot be billed twice for the
same answer.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.progress import as_utc, utc_now

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.user import User


class AIInsightKind(str, enum.Enum):
    """The kinds of insight this platform generates.

    These values are persisted and they are the vocabulary a deployment's stored
    rows must match. ``backend.app.ai.provider`` declares the same three values,
    because a prompt and a stored row cannot disagree about what was asked for;
    ``backend/tests/test_ai.py`` asserts the two lists are identical so the
    duplication cannot drift the way two unlinked lists do.
    """

    PROBLEM_EXPLANATION = "problem_explanation"
    SUBMISSION_DIAGNOSIS = "submission_diagnosis"
    CODE_COMPLEXITY = "code_complexity"


AI_INSIGHT_KIND_VALUES: tuple[str, ...] = tuple(kind.value for kind in AIInsightKind)

#: A generated insight is a focused paragraph or two, not an essay. The ceiling is
#: well above what ``AI_MAX_OUTPUT_TOKENS`` can produce -- a token is at least one
#: character, so the configured maximum already bounds the text -- and exists to
#: stop a provider that ignores the token budget from writing a row that costs a
#: megabyte to read back.
MAX_INSIGHT_CONTENT_LENGTH: int = 65_536

#: Provider and model names are short and come from configuration or from a fixed
#: registry, but the columns are sized generously because a third-party gateway
#: reports whatever model string it likes and truncating the attribution would make
#: the record lie about which model answered.
MAX_PROVIDER_NAME_LENGTH: int = 40
MAX_MODEL_NAME_LENGTH: int = 160

#: A SHA-256 digest in hex, and nothing else.
SCOPE_KEY_LENGTH: int = 64


class AIInsight(Base):
    """A generated insight, attributed to the learner who requested it."""

    __tablename__ = "ai_insights"
    __table_args__ = (
        # The vocabulary is enforced in the database, not only in the service, so a
        # direct SQL session cannot store a kind the API cannot read back. Written
        # out literally because a SQL CHECK cannot reference a Python enum.
        CheckConstraint(
            "kind IN ('problem_explanation', 'submission_diagnosis', 'code_complexity')",
            name="ck_ai_insights_kind",
        ),
        # The cache contract. This is the constraint that makes "one answer per
        # request scope" true rather than aspirational.
        UniqueConstraint("user_id", "scope_key", name="uq_ai_insights_user_scope"),
        # Both lookups the API performs: "this learner's insights of one kind" and
        # "the insight for this exact request scope".
        Index("ix_ai_insights_user_kind", "user_id", "kind"),
        Index("ix_ai_insights_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)

    # What the insight is about. Both are nullable because the three kinds point
    # at different things: an explanation is about a problem, a diagnosis about a
    # submission, and a complexity analysis about a snippet that need not belong
    # to either. Exactly one is set per kind, which
    # :mod:`backend.app.services.ai_service` is responsible for, and which the
    # foreign keys enforce for us -- a row cannot reference a problem or a
    # submission that no longer exists.
    problem_id: Mapped[int | None] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=True, index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=True, index=True
    )

    #: The cache key: a digest of the provider, model, kind, and rendered prompt.
    #: Unique per learner, see the module docstring for why it is a digest.
    scope_key: Mapped[str] = mapped_column(String(SCOPE_KEY_LENGTH), nullable=False, index=True)

    #: The generated text, stored verbatim as the provider returned it. It is never
    #: rewritten, trimmed, or re-rendered on the way in: a record that differs from
    #: what the model actually wrote cannot be audited.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    #: Attribution. A cached row must keep reporting the model that wrote it, so a
    #: deployment that switches models serves the old answer labelled as the old
    #: model instead of silently reattributing a model it never called.
    provider: Mapped[str] = mapped_column(String(MAX_PROVIDER_NAME_LENGTH), nullable=False)
    model: Mapped[str] = mapped_column(String(MAX_MODEL_NAME_LENGTH), nullable=False)

    #: Exactly which safe facts were sent. Recorded so a grounding complaint can be
    #: answered from the record rather than by re-deriving a prompt that may since
    #: have changed.
    grounding: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )

    user: Mapped["User"] = relationship(back_populates="ai_insights")

    @property
    def created_at_utc(self) -> datetime:
        """The creation time as an aware UTC datetime.

        Normalised the same way the submission and progress rows are, because
        SQLite drops the offset on the way in and three models that disagree about
        whether a timestamp is aware is not a thing worth having.
        """
        return as_utc(self.created_at)


__all__ = [
    "AI_INSIGHT_KIND_VALUES",
    "MAX_INSIGHT_CONTENT_LENGTH",
    "MAX_MODEL_NAME_LENGTH",
    "MAX_PROVIDER_NAME_LENGTH",
    "SCOPE_KEY_LENGTH",
    "AIInsight",
    "AIInsightKind",
]
