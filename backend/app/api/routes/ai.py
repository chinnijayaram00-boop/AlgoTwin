from fastapi import APIRouter, Depends

from backend.app.ai.service import AIService
from backend.app.core.config import Settings, get_settings
from backend.app.schemas.platform import AIStatusResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=AIStatusResponse)
def ai_status(settings: Settings = Depends(get_settings)) -> AIStatusResponse:
    configured = settings.ai_is_configured
    return AIStatusResponse(
        provider=settings.ai_provider,
        configured=configured,
        model=settings.ai_model,
        message=(
            "AI provider is configured for future explanation requests."
            if configured
            else "AI is disabled; configure AI_PROVIDER and AI_API_KEY to enable it."
        ),
    )


@router.get("/service", response_model=AIStatusResponse, include_in_schema=False)
def ai_service_status(settings: Settings = Depends(get_settings)) -> AIStatusResponse:
    service = AIService(settings)
    return AIStatusResponse(
        provider=service.provider.name,
        configured=service.configured,
        model=settings.ai_model,
        message="AI service boundary is available.",
    )
