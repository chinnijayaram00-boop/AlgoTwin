"""Personalized coach endpoints.

Two routes, both authenticated with ``CurrentUser``, the same guard every other
learner-scoped route uses. The learner's identity comes only from the bearer
token: there is no ``user_id`` parameter, query field, or body field anywhere in
this module, so a caller cannot read another learner's profile or ask the coach
about someone else.

``GET /personalization/profile`` is a pure read. It assembles the learner's
strengths, weaknesses, next steps, and focus areas from the same deterministic
computations the analytics and learning-path pages already run, so the coach can
never contradict those pages.

``POST /personalization/mentor`` turns that profile into coaching. The request
body is optional and carries at most a ``focus`` label; the facts behind the
advice are never taken from the caller, only from the profile this route just
read. The route always answers ``200``: when no model is available, or the
learner is at their rate limit, or the provider fails or times out, the response
carries the deterministic fallback and names why in ``degraded_reason``. Asking
for advice should return advice, so this is the one AI-shaped route whose
failures are reported in the body rather than as an error status.

The provider comes from ``AIProviderDependency`` rather than ``AIService`` built
inline, for the same reason as the AI routes: one pooled client per process, closed
by the application lifespan.
"""

from database.models.progress import utc_now
from fastapi import APIRouter

from backend.app.api.dependencies import (
    AIProviderDependency,
    AppSettings,
    CurrentUser,
    DbSession,
)
from backend.app.schemas.personalization import (
    DEFAULT_MENTOR_FOCUS,
    MentorGuidanceRequest,
    MentorGuidanceResponse,
    PersonalizationProfileResponse,
)
from backend.app.services import ai_service, personalization_service

router = APIRouter(prefix="/personalization", tags=["personalization"])


@router.get("/profile", response_model=PersonalizationProfileResponse)
def read_my_profile(
    db: DbSession,
    current_user: CurrentUser,
) -> PersonalizationProfileResponse:
    """The authenticated learner's personalized profile in one read.

    Every signal is derived from the learner's own persisted rows via the
    analytics and learning-path services, so this endpoint introduces no new
    computation that could disagree with the pages that already show the same
    underlying counts.
    """
    return personalization_service.load_profile(db, current_user.id)


@router.post("/mentor", response_model=MentorGuidanceResponse)
async def mentor_guidance(
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
    provider: AIProviderDependency,
    payload: MentorGuidanceRequest | None = None,
) -> MentorGuidanceResponse:
    """Grounded coaching for the authenticated learner.

    The profile is recomputed on every request rather than cached, because advice
    about what to do next is a statement about the learner's state now. The body is
    optional; an absent body means the default ``overview`` focus, and the only
    thing a body can change is which part of the profile the coach centres on.
    """
    profile = personalization_service.load_profile(db, current_user.id)
    result = await personalization_service.generate_mentor_guidance(
        user_id=current_user.id,
        profile=profile,
        settings=settings,
        provider=provider,
        limiter=ai_service.build_limiter(settings),
        focus=payload.focus if payload is not None else DEFAULT_MENTOR_FOCUS,
    )
    return MentorGuidanceResponse(
        focus=result.focus,
        content=result.content,
        provider=result.provider,
        model=result.model,
        grounding=result.grounding,
        fallback=result.fallback,
        degraded_reason=result.degraded_reason,
        is_demo_output=result.is_demo_output,
        generated_at=utc_now(),
    )


__all__ = ["router"]
