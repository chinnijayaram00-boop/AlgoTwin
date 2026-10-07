"""Learner analytics endpoints.

Every route on this router is authenticated with ``CurrentUser``, the same
``get_current_user`` guard the progress, submission, and interview routes use.
The learner's identity comes only from the bearer token: there is no
``user_id`` parameter, query field, or body field anywhere in this module, so a
caller cannot read another learner's analytics by guessing an id.

The one query parameter, ``days``, bounds the activity series only -- it
selects a window over the caller's own timestamps and cannot widen the summary
past what the caller is allowed to see.
"""

from fastapi import APIRouter, Query

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.schemas.analytics import (
    DEFAULT_ACTIVITY_DAYS,
    MAX_ACTIVITY_DAYS,
    MIN_ACTIVITY_DAYS,
    AnalyticsSummaryResponse,
)
from backend.app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def read_my_analytics(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(
        default=DEFAULT_ACTIVITY_DAYS,
        ge=MIN_ACTIVITY_DAYS,
        le=MAX_ACTIVITY_DAYS,
        description=(
            "Days of activity history to include, ending today. Every other "
            "section of the summary covers the learner's whole recorded history."
        ),
    ),
) -> AnalyticsSummaryResponse:
    """The authenticated learner's full analytics summary in one read.

    Overview, difficulty and topic breakdowns, verdict distribution, the daily
    activity series, the learning path position, and mock interview
    performance -- all computed from the published catalog and this learner's
    own persisted rows. One endpoint rather than a family of narrowly-scoped
    ones, because every section projects the same rows over the same moment.

    An unrecognised ``days`` is a 422 from the ``Query`` bounds rather than a
    silent clamp: answering a different question than the one asked is worse
    than an error.
    """
    return analytics_service.load_summary(db, current_user.id, days=days)
