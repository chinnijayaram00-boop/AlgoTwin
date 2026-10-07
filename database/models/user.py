from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from database.models.ai_insight import AIInsight
    from database.models.interview import InterviewSession
    from database.models.progress import Progress
    from database.models.submission import Submission


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Progress is reachable from the learner, and only from the learner. The
    # ORM cascade matches the `ondelete="CASCADE"` on the foreign key so a
    # removed account leaves no orphaned progress behind either way.
    progress_entries: Mapped[list["Progress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Same reasoning for submissions: a removed account must leave no recorded
    # attempt behind, so the ORM cascade mirrors the `ondelete="CASCADE"` on the
    # foreign key.
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Generated AI insights are the learner's own: nobody else may read them, and
    # a deleted account must leave none behind. Same reasoning as the two above,
    # and the `ondelete="CASCADE"` on the foreign key means the rows go even if
    # the ORM cascade never runs.
    ai_insights: Mapped[list["AIInsight"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Mock interview sessions are the learner's own timed rehearsals, and a
    # deleted account must leave none behind -- including the recorded question
    # selections, which cascade with the session.
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
