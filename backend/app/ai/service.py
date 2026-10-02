"""The AI boundary: one object that owns a resolved provider and answers two questions.

This class is deliberately thin. It holds a settings object and the provider the
registry resolved from it, and it exposes ``configured`` and ``complete``. Every
decision about *what* to send, *whether* to send it, and *what to do with the
answer* belongs to :mod:`backend.app.services.ai_service`. Keeping the boundary
this small is what makes it possible to state the invariant that matters:

    ``AIService.configured`` is the provider's own answer.

That is the defect this file replaces. The previous version held a
``DisabledAIProvider`` unconditionally while reading ``configured`` from the
settings, so a deployment with a valid key advertised itself as ready and then
failed every call. Nothing here may re-derive ``configured`` from settings; if a
caller needs the configuration-level precondition, it reads
``Settings.ai_is_configured``, and the two are documented to mean different
things.
"""

from __future__ import annotations

from backend.app.ai.errors import AIProviderNotConfiguredError
from backend.app.ai.provider import AICompletionRequest, AICompletionResponse, AIProvider
from backend.app.ai.registry import provider_status, resolve_provider


class AIService:
    """A provider, plus the ability to say honestly whether it can answer."""

    def __init__(self, settings, provider: AIProvider | None = None) -> None:
        self.settings = settings
        #: Resolved from settings when no provider is injected. A caller that
        #: passes one is a test or an application choosing its own provider, and
        #: the injected instance wins -- which is the only way the fake provider
        #: can be reached through the same interface a deployment configures.
        self.provider: AIProvider = provider if provider is not None else resolve_provider(settings)

    @property
    def configured(self) -> bool:
        """Whether a request through this service would reach a provider.

        Read from the provider, never recomputed. This is the single answer the
        routes, the status endpoint, and the settings screen all use.
        """
        return bool(getattr(self.provider, "configured", False))

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def model(self) -> str:
        return self.provider.model

    def status(self):
        """What ``GET /ai/status`` reports.

        Resolved through the registry rather than described from this instance, so
        the status endpoint reports the provider a *request* would get rather than
        the provider this particular object happens to hold. For a service built
        from settings -- which is every one a route uses -- the two are the same
        object.
        """
        return provider_status(self.settings)

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """Send one request, or refuse before anything leaves the host.

        The check here and the check inside the provider are not redundant. This
        one keeps an unconfigured deployment from building a prompt at all, and
        raises the not-configured error rather than the generic provider error,
        so the route can answer 503 instead of 502.
        """
        if not self.configured:
            raise AIProviderNotConfiguredError()
        return await self.provider.complete(request)

    async def aclose(self) -> None:
        await self.provider.aclose()


__all__ = ["AIService"]
