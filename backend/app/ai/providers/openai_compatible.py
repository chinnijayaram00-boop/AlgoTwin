"""The OpenAI-compatible chat-completions provider.

"OpenAI-compatible" is a precise claim and a narrow one: this speaks the
``POST {AI_BASE_URL}/chat/completions`` request shape with a
``messages``/``model``/``max_tokens``/``temperature`` body and an
``Authorization: Bearer`` header, and reads ``choices[0].message.content`` out of
the reply. That is enough for OpenAI itself and for the services that
reimplemented that endpoint. It is *not* a general model API client: there is no
streaming, no tool calling, no batch, no embeddings, and no attempt to abstract
over providers that do not speak this dialect.

Three decisions worth stating:

* **One pooled client.** A new ``httpx.AsyncClient`` per request would mean a new
  TLS handshake per request and no connection reuse. The client is created once,
  lazily, and reused. ``aclose`` exists so an application shutting down can
  release it, and it is safe to call twice.
* **Every failure becomes one of three exceptions.** A refused connection, an
  error status, an empty choice list, and a non-JSON body all raise
  :class:`~backend.app.ai.errors.AIProviderError`; only a genuine transport
  timeout raises the timeout error. The routes map those to 502 and 504, so this
  module is the single place that decides what "the provider misbehaved" means.
* **No upstream text survives into an error.** An upstream error body can quote
  the request that produced it, which for this application means a learner's
  source code. Only the numeric upstream status is kept, and the message is
  generated here from a small table of known statuses. Nothing in this module
  logs, and nothing in it puts the credential into a string.
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.app.ai.errors import (
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderTimeoutError,
)
from backend.app.ai.provider import AICompletionRequest, AICompletionResponse

#: The provider name this module is registered under.
PROVIDER_NAME = "openai_compatible"

#: Upper bound on any upstream body this provider will read. A provider that
#: streams megabytes at a failed request must not be able to grow the process's
#: memory because of it; a completion this application can store is far smaller.
MAX_RESPONSE_BYTES = 256 * 1024

#: Connect timeout is a fraction of the total budget. A provider that cannot be
#: reached at all should fail fast and leave the read timeout to the model, which
#: is the part that is legitimately slow.
_CONNECT_BUDGET_FRACTION = 0.25

#: Human messages for the upstream statuses an operator actually acts on. Anything
#: not listed gets the generic message, so an upstream can never inject its own
#: text into a learner-facing error.
_STATUS_MESSAGES: dict[int, str] = {
    400: "The AI provider rejected the request.",
    401: "The AI provider rejected the configured credential.",
    403: "The AI provider refused access with the configured credential.",
    404: "The configured AI model was not found at this provider.",
    413: "The request was too large for the AI provider.",
    422: "The AI provider rejected the request.",
    429: "The AI provider is rate limiting this deployment.",
    500: "The AI provider reported an internal error.",
    502: "The AI provider reported a bad gateway.",
    503: "The AI provider reported itself unavailable.",
    504: "The AI provider reported a gateway timeout.",
}

_DEFAULT_STATUS_MESSAGE = "The AI provider returned an error status."


def _status_message(status: int) -> str:
    """A safe, fixed message for an upstream status. Never the upstream body."""
    return _STATUS_MESSAGES.get(status, _DEFAULT_STATUS_MESSAGE)


def _extract_text(payload: Any) -> str:
    """Pull the completion out of a chat-completions reply.

    Raises :class:`~backend.app.ai.errors.AIProviderError` for every shape that
    is not the one this provider asked for, including a reply whose content is
    empty. An empty completion is not a usable answer, and returning it would
    store a blank insight that reads as a successful generation.
    """
    if not isinstance(payload, dict):
        raise AIProviderError("The AI provider returned a response that was not a JSON object.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIProviderError("The AI provider returned no choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise AIProviderError("The AI provider returned an unusable choice.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise AIProviderError("The AI provider returned a choice with no message.")
    content = message.get("content")
    # Some gateways return a list of content parts rather than a string. Joining
    # them is the documented way to read that shape; anything else is unusable.
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        content = "".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise AIProviderError("The AI provider returned an empty completion.")
    return content.strip()


class OpenAICompatibleProvider:
    """One HTTP conversation with an OpenAI-compatible chat-completions API."""

    def __init__(self, settings, *, client: httpx.AsyncClient | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.name = PROVIDER_NAME
        self.model = settings.ai_model
        self._api_key = settings.ai_api_key_value
        self._url = settings.ai_chat_completions_url
        self._owns_client = client is None
        self._client = client
        self._transport = transport

    @property
    def configured(self) -> bool:
        """Whether a request could plausibly be delivered.

        True only with a non-empty credential and a base URL. Both are known
        without contacting anything, which is what lets ``/ai/status`` be honest
        and lets :class:`~backend.app.ai.service.AIService` refuse before a request
        is built rather than after it is sent.
        """
        return bool(self._api_key) and bool(self._url)

    def _timeout(self) -> httpx.Timeout:
        total_ms = int(getattr(self.settings, "ai_timeout_ms", 20_000))
        connect_ms = max(500, int(total_ms * _CONNECT_BUDGET_FRACTION))
        return httpx.Timeout(
            total_ms / 1000.0,
            connect=connect_ms / 1000.0,
            read=total_ms / 1000.0,
            write=total_ms / 1000.0,
            pool=connect_ms / 1000.0,
        )

    async def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout(),
                # A transport can only be supplied at construction, so a provider
                # built with one must construct its client lazily too.
                transport=self._transport,
                follow_redirects=False,
                headers={"Content-Type": "application/json"},
            )
            self._owns_client = True
        return self._client

    def _headers(self) -> dict[str, str]:
        # The credential appears here and nowhere else in this module: not in a
        # message, not in an exception, and not in a log line.
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def _body(self, request: AICompletionRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        if not self.configured:
            # Reachable only if the credential was revoked between construction
            # and the call, but it is the one branch that must never send a
            # request with an empty Authorization header.
            #
            # Raised as *not configured* rather than as a provider error so it maps
            # to 503. A deployment with no key is a setup problem with a specific
            # fix; reporting it as an upstream fault (502) sends the reader looking
            # at a provider that is working perfectly.
            raise AIProviderNotConfiguredError("The AI provider has no configured credential.")

        client = await self._client_or_create()
        try:
            response = await client.post(self._url, headers=self._headers(), json=self._body(request))
        except httpx.TimeoutException as error:
            raise AIProviderTimeoutError(
                "The AI provider did not respond within the configured timeout."
            ) from error
        except httpx.HTTPError as error:
            # The transport's message can name the host and, occasionally, echo
            # request detail. `safe_detail` inside the exception strips anything
            # credential-shaped and bounds the length; the timeout exception is
            # the only place the cause is worth keeping, and it is kept as `__cause__`
            # for a local traceback rather than for a response body.
            raise AIProviderError("The AI provider could not be reached.") from error

        if response.status_code >= 400:
            # The body is deliberately not read. An upstream error can quote the
            # request, and for this application the request contains a learner's
            # source code.
            raise AIProviderError(
                _status_message(response.status_code),
                upstream_status=response.status_code,
            )

        if len(response.content) > MAX_RESPONSE_BYTES:
            raise AIProviderError("The AI provider returned a response larger than this platform accepts.")

        try:
            payload = response.json()
        except ValueError as error:
            raise AIProviderError("The AI provider returned a response that was not JSON.") from error

        return AICompletionResponse(
            text=_extract_text(payload),
            provider=self.name,
            model=self.model,
        )

    async def aclose(self) -> None:
        """Close the pooled client, if this provider created it.

        A caller-supplied client belongs to the caller. Closing it here would
        break whoever lent it, which is why ownership is tracked rather than
        assumed.
        """
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None


__all__ = ["MAX_RESPONSE_BYTES", "PROVIDER_NAME", "OpenAICompatibleProvider"]
