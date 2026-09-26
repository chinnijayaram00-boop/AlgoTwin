from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.progress import Progress


class Problem(Base):
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

    # Every learner's record for this problem hangs off the problem row, but the
    # owning learner is always the only caller that may read or write them.
    progress_entries: Mapped[list["Progress"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
