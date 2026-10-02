"""The one shape every AI provider implements.

A provider is asked a single thing: given a system instruction and a user
instruction, produce text. Everything above this line -- prompts, grounding,
caching, rate limiting -- is provider-agnostic, and everything below it is one
HTTP conversation. That is the whole point of the boundary: the OpenAI-compatible
provider and the deterministic fake differ in exactly one method and share no
code path above it.

Two things are part of the contract rather than incidental:

* **``configured`` is a property of the provider, not of the settings.** This is
  the fix for the defect this boundary previously had. ``AIService`` used to
  decide "is AI on?" by reading the configuration while holding a provider that
  was always the disabled one, so a deployment with a valid key reported itself
  ready and then failed every call. A provider that can answer ``configured``
  truthfully is the only thing allowed to answer it.
* **Completion is a coroutine.** Provider calls are network calls, and the
  routes that make them are ``async def`` so the event loop is not blocked for
  the length of a model response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.app.ai.errors import (
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderTimeoutError,
)

#: The kinds of insight this application asks a provider for. A provider uses it
#: to decide the shape of its answer: an explanation is prose, a complexity
#: analysis is a small JSON object the service validates before storing. The
#: values are the persisted ``ai_insights.kind`` vocabulary, so a prompt and a
#: stored row can never disagree about what was requested.
KIND_PROBLEM_EXPLANATION = "problem_explanation"
KIND_SUBMISSION_DIAGNOSIS = "submission_diagnosis"
KIND_CODE_COMPLEXITY = "code_complexity"

AI_INSIGHT_KINDS: tuple[str, ...] = (
    KIND_PROBLEM_EXPLANATION,
    KIND_SUBMISSION_DIAGNOSIS,
    KIND_CODE_COMPLEXITY,
)


@dataclass(frozen=True)
class AICompletionRequest:
    """One request to a model: what is being asked, and in what form.

    The instructions are already fully rendered. A provider must not append,
    reinterpret, or rewrite them: the service is what knows the grounded facts
    and what has been withheld from the model, and a provider that amended the
    prompt could quietly reintroduce something the redaction removed.
    """

    kind: str
    system: str
    user: str
    max_output_tokens: int
    temperature: float


@dataclass(frozen=True)
class AICompletionResponse:
    """A completion, attributed to the provider and model that produced it.

    The attribution is stored alongside every generated insight, so a cached row
    always reports the model that actually wrote it rather than whichever model
    happens to be configured now.
    """

    text: str
    provider: str
    model: str


@runtime_checkable
class AIProvider(Protocol):
    """What :mod:`backend.app.ai.service` requires of a provider."""

    #: Stable, human-readable identifier. Stored on every insight row.
    name: str

    #: The model this provider will name in its responses.
    model: str

    @property
    def configured(self) -> bool:
        """Whether this provider can actually answer right now.

        ``False`` means a request would raise
        :class:`~backend.app.ai.errors.AIProviderNotConfiguredError` rather than
        reach a network. It must never be ``True`` for a provider that cannot
        succeed -- that disagreement is the defect this property exists to make
        impossible.
        """
        ...

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """Produce a completion, or raise an ``AIError`` subclass.

        Raises
            AIProviderNotConfiguredError
                If this provider cannot answer, checked before any request.
            AIProviderTimeoutError
                If the provider did not answer within the budget.
            AIProviderError
                For any other unusable outcome: a refused connection, an error
                status, an empty completion, or a body that is not the shape the
                request asked for.
        """
        ...

    async def aclose(self) -> None:
        """Release any pooled connection. Safe to call more than once."""
        ...


__all__ = [
    "AI_INSIGHT_KINDS",
    "KIND_CODE_COMPLEXITY",
    "KIND_PROBLEM_EXPLANATION",
    "KIND_SUBMISSION_DIAGNOSIS",
    "AICompletionRequest",
    "AICompletionResponse",
    "AIProvider",
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "AIProviderTimeoutError",
]
