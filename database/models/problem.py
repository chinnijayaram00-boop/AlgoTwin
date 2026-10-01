from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.progress import Progress
    from database.models.submission import Submission


#: Default judge limits for a problem that does not set its own. Two seconds and
#: 256 MB is generous for the linear and near-linear algorithms in the catalog
#: and still small enough that a runaway process is killed quickly.
DEFAULT_TIME_LIMIT_MS = 2_000
DEFAULT_MEMORY_LIMIT_MB = 256

#: Ceilings on the limits a problem may ask for, so a catalog row cannot demand a
#: worker that a developer's machine cannot honour. The judge clamps to these and
#: reports the clamped value, rather than quietly granting more.
MAX_TIME_LIMIT_MS = 10_000
MAX_MEMORY_LIMIT_MB = 1_024

#: The judge columns added on top of the original problem row, with the DDL used
#: by both the Alembic revision ``d_problem_catalog`` and the start-time upgrader
#: in ``backend.app.db.schema``, so the two cannot drift.
PROBLEM_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("description", "TEXT"),
    ("input_format", "TEXT"),
    ("output_format", "TEXT"),
    ("hints", "JSON"),
    ("explanation", "TEXT"),
    ("supported_languages", "JSON"),
    ("expected_time_complexity", "VARCHAR(60)"),
    ("expected_space_complexity", "VARCHAR(60)"),
    ("time_limit_ms", f"INTEGER NOT NULL DEFAULT {DEFAULT_TIME_LIMIT_MS}"),
    ("memory_limit_mb", f"INTEGER NOT NULL DEFAULT {DEFAULT_MEMORY_LIMIT_MB}"),
    ("test_cases", "JSON"),
    ("reference_solutions", "JSON"),
)

#: A problem must carry at least this many hints for the five hint levels to be
#: meaningful, and the hint ladder is addressed by index.
HINT_LEVELS = 5


class Problem(Base):
    """A published DSA problem, together with the data a judge needs.

    Two column groups, and the split is deliberate:

    * everything a learner may read -- ``summary``, ``description``,
      ``constraints``, ``input_format``, ``output_format``, ``examples``,
      ``hints``, ``explanation``, ``starter_code``, ``reference_solutions`` --
      is served by the public problem endpoints;
    * ``test_cases`` holds both the visible and the hidden cases. Only the
      visible subset is ever projected into an API response, so a hidden case's
      input cannot leak through a read endpoint; it is read exclusively by the
      judge, which runs it and reports only whether it passed.
    """

    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    examples: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    starter_code: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # The full statement. ``summary`` stays the one-line card text and ``title``
    # the heading, so neither has to double as the statement.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Exactly five hints, one per level: concept, approach, pseudocode, detailed
    # explanation, full solution. The count is fixed because the AI coach and the
    # UI both address a hint by level number, and a level with no content would
    # be an empty promise.
    hints: Mapped[list[str]] = mapped_column(JSON, default=list)

    # The editorial, written for the problem rather than generated per request.
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Languages this problem ships starter code for. A language is listed only
    # when a working starter exists for it, so the editor never offers a tab
    # that cannot run.
    supported_languages: Mapped[list[str]] = mapped_column(JSON, default=list)

    # The complexity a good solution reaches. Used to label a measured result as
    # on-target or not; it is never presented as a measurement.
    expected_time_complexity: Mapped[str | None] = mapped_column(String(60), nullable=True)
    expected_space_complexity: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Judge limits for this problem. Kept per problem so a graph traversal can be
    # given more room than an O(n) scan.
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2_000, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, nullable=False)

    # Judge inputs, each ``{"input", "expected_output", "is_hidden"}``. A hidden
    # case is never projected into any response.
    test_cases: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)

    # A working solution per language, used to validate the seeded test data and
    # to power the "reference solution" affordance. Never executed by a request
    # on the learner's behalf.
    reference_solutions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)

    # ------------------------------------------------------------------ readers
    #
    # These are the only shapes of ``test_cases`` this application understands,
    # and both readers reject anything else rather than guessing. Validation
    # belongs here so a hand-edited catalog row cannot reach the judge.

    def visible_test_cases(self) -> list[dict[str, object]]:
        """The cases a learner may see, with their inputs and expected outputs."""
        return [case for case in self.test_cases if not bool(case.get("is_hidden"))]

    def hidden_test_cases(self) -> list[dict[str, object]]:
        """The cases the judge runs but never discloses."""
        return [case for case in self.test_cases if bool(case.get("is_hidden"))]

    @property
    def effective_time_limit_ms(self) -> int:
        """The wall-clock limit, clamped into the range the platform will honour."""
        value = int(self.time_limit_ms or DEFAULT_TIME_LIMIT_MS)
        return max(1, min(value, MAX_TIME_LIMIT_MS))

    @property
    def effective_memory_limit_mb(self) -> int:
        """The memory ceiling, clamped into the range the platform will honour."""
        value = int(self.memory_limit_mb or DEFAULT_MEMORY_LIMIT_MB)
        return max(16, min(value, MAX_MEMORY_LIMIT_MB))

    # Every learner's record for this problem hangs off the problem row, but the
    # owning learner is always the only caller that may read or write them.
    progress_entries: Mapped[list["Progress"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Retiring a problem must not leave submissions pointing at a catalog entry
    # that can no longer be read, so the submissions go with it.
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
