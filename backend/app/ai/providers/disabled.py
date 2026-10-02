"""The provider that answers nothing, and says so.

This is the fail-closed default. It is what ``AI_PROVIDER=disabled`` resolves to,
what an unknown provider name resolves to, and what a named provider that cannot
be constructed -- a missing credential, an unusable base URL -- falls back to
rather than raising at start-up and taking the whole API down.

It raises rather than returning a canned string. A stub that returned plausible
prose would be the worst possible failure mode for this feature: the learner
would be shown a confident explanation of a problem, and nothing would indicate
that no model was ever consulted.
"""

from __future__ import annotations

from backend.app.ai.errors import AIProviderNotConfiguredError
from backend.app.ai.provider import AICompletionRequest, AICompletionResponse


class DisabledAIProvider:
    """Refuses every request. Never reports itself as configured."""

    def __init__(self, requested_provider: str | None = None) -> None:
        #: The name that was configured, kept only so ``/ai/status`` can tell an
        #: operator which value to fix. Never a credential.
        self.requested_provider = (requested_provider or "disabled").strip().lower()
        self.name = "disabled"
        self.model = "none"

    @property
    def configured(self) -> bool:
        """Always ``False``.

        Not configurable and not derived from anything: this provider has no path
        to a completion, so the honest answer is no in every deployment and in
        every state.
        """
        return False

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        raise AIProviderNotConfiguredError(
            "AI is disabled on this deployment. Set AI_PROVIDER and the provider's "
            "credential to enable AI features."
        )

    async def aclose(self) -> None:
        """Nothing to release."""
        return None


__all__ = ["DisabledAIProvider"]
