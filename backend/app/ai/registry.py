"""The one place ``AI_PROVIDER`` is turned into a provider.

This module exists to remove a defect, not to add indirection. Before it, the
configuration named a provider, ``AIService`` decided "is AI on?" by reading that
configuration, and the provider it actually held was unconditionally the disabled
one. A deployment with a valid key therefore reported itself ready -- through
``GET /ai/status`` and through the settings screen, which both render
"configured" -- and then failed every single call. Two sources of truth about the
same fact, and the second one was hard-coded.

So there is exactly one resolution step, and everything else asks it:

* :func:`resolve_provider` maps the configured name to a provider instance, and
  returns the disabled provider for an unknown name, for ``disabled``, or for a
  named provider that cannot be constructed. It never raises and never guesses.
* :func:`provider_status` reports what that resolution decided and why, so
  ``/ai/status`` and the settings screen describe the *actual* provider rather
  than restating an environment variable.
* :class:`~backend.app.ai.service.AIService` holds the resolved instance and reads
  ``configured`` off it, which makes "is AI on?" and "will this call work?" the
  same question with one answer.

Failing closed is deliberate throughout. An unrecognised provider name is a
configuration mistake, and the safe response to one is a platform that serves a
clear 503 rather than a platform that picks a provider and bills somebody for it.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.ai.errors import AIError, AIProviderNotConfiguredError
from backend.app.ai.provider import AIProvider
from backend.app.ai.providers.disabled import DisabledAIProvider
from backend.app.ai.providers.fake import FakeAIProvider
from backend.app.ai.providers.openai_compatible import OpenAICompatibleProvider

#: Every provider name a deployment may configure, mapped to its factory.
#:
#: ``disabled`` and ``fake`` take no credential. ``fake`` is in the shipped table
#: rather than being test-only because it is what ``AI_PROVIDER=fake`` means, and a
#: registry that could not resolve a name a deployment is documented to use would
#: not be the single source of truth it claims to be.
PROVIDER_FACTORIES: dict[str, object] = {
    "disabled": lambda settings: DisabledAIProvider("disabled"),
    "fake": lambda settings: FakeAIProvider(settings),
    "openai_compatible": lambda settings: OpenAICompatibleProvider(settings),
    # An alias, because "openai" is what an operator will type first and a name
    # that resolves to the disabled provider is a confusing way to learn that.
    "openai": lambda settings: OpenAICompatibleProvider(settings),
}

#: The name reported for the disabled provider, whatever was configured.
DISABLED_PROVIDER_NAME = "disabled"

#: Every accepted ``AI_PROVIDER`` value, in the order they are documented.
PROVIDER_NAMES: tuple[str, ...] = ("disabled", "fake", "openai_compatible")


@dataclass(frozen=True)
class AIProviderStatus:
    """What the resolution decided, and the reason a caller may report.

    ``configured`` is the provider's own answer, not a re-reading of the
    environment. ``reason`` is safe to show a learner and to put in a log: it is
    written here, never taken from a provider or an upstream response.
    """

    requested: str
    provider: str
    model: str
    configured: bool
    reason: str


def normalize_provider_name(value: str | None) -> str:
    """The canonical form of a configured provider name.

    Lower-cased and trimmed, because a provider name is a deployment setting and
    ``OpenAI-Compatible`` and ``openai_compatible`` are the same instruction.
    """
    return (value or "").strip().lower()


def resolve_provider(settings) -> AIProvider:
    """The provider ``settings`` names, or the disabled provider.

    Never raises and never returns ``None``. A factory that fails for any reason
    -- most plausibly a provider whose credential is missing at construction --
    falls back to the disabled provider, because a start-up that fails on a
    misconfigured AI provider would take the catalog, the judge, and every other
    working feature down with it.
    """
    requested = normalize_provider_name(getattr(settings, "ai_provider", None))
    factory = PROVIDER_FACTORIES.get(requested)
    if factory is None:
        return DisabledAIProvider(requested or "disabled")
    try:
        return factory(settings)
    except AIError:
        return DisabledAIProvider(requested)
    except Exception:  # noqa: BLE001 - a broken provider must not break start-up
        return DisabledAIProvider(requested)


def provider_status(settings) -> AIProviderStatus:
    """Describe the provider that :func:`resolve_provider` would return.

    Called by ``GET /ai/status``. It resolves exactly as a request would, so the
    status a learner sees is the status their next request will get.
    """
    requested = normalize_provider_name(getattr(settings, "ai_provider", None)) or DISABLED_PROVIDER_NAME
    provider = resolve_provider(settings)
    configured = bool(getattr(provider, "configured", False))

    if configured:
        reason = (
            f"AI requests are served by {provider.name} using {provider.model}."
            if provider.name != "fake"
            # The fake provider answers with fixed text and never contacts a
            # model, so naming a model here would imply a generation that did
            # not happen.
            else "AI is served by the deterministic `fake` provider, which returns fixed text and contacts no model."
        )
    elif requested == DISABLED_PROVIDER_NAME:
        reason = "AI is disabled on this deployment. Set AI_PROVIDER and the provider credential to enable it."
    elif requested not in PROVIDER_FACTORIES:
        reason = (
            f"AI_PROVIDER is {requested!r}, which is not a known provider, so AI is disabled. "
            f"Known providers: {', '.join(PROVIDER_NAMES)}."
        )
    else:
        reason = (
            f"AI_PROVIDER names {requested}, but that provider has no usable credential, "
            "so AI is disabled."
        )

    return AIProviderStatus(
        requested=requested,
        provider=provider.name,
        model=provider.model,
        configured=configured,
        reason=reason,
    )


__all__ = [
    "DISABLED_PROVIDER_NAME",
    "PROVIDER_FACTORIES",
    "PROVIDER_NAMES",
    "AIProviderStatus",
    "AIProviderNotConfiguredError",
    "normalize_provider_name",
    "provider_status",
    "resolve_provider",
]
