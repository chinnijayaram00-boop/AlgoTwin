"""The failure vocabulary the AI layer can produce, and nothing else.

An AI request can go wrong in four distinguishable ways, and a caller needs to
be able to tell them apart because they mean different things to a learner and
to whoever is on call:

* :class:`AIProviderNotConfiguredError` -- this deployment has no working
  provider. Nothing was sent anywhere. The deployment's problem, reported as
  ``503``.
* :class:`AIProviderTimeoutError` -- the provider was contacted and did not
  answer inside the configured budget. Reported as ``504``.
* :class:`AIProviderError` -- the provider answered, or refused the connection,
  with something unusable. Reported as ``502``.
* :class:`AIRateLimitError` -- this learner has spent their per-minute budget.
  Reported as ``429`` with a retry hint.

The distinction matters most for the first two: "AI is switched off here" and
"the model is slow" are different bugs, and a caller that collapses them cannot
tell an operator which one occurred.

**No exception in this module may carry an upstream response body or a
credential.** :func:`safe_detail` is the only sanctioned way to build the human
message, and it clips and normalises whatever it is given. The API key is never
placed in an exception, and neither is any text copied from an upstream
response: an upstream error body can quote the request that produced it, which
would put a learner's source code into a log line.
"""

from __future__ import annotations

#: The longest human-facing detail any AI error may carry. An upstream body can
#: be arbitrarily long and can quote the request; clipping here means no caller
#: has to remember to clip.
MAX_DETAIL_LENGTH = 300

#: Substrings that must never survive into an error message. Anything derived
#: from an upstream response is filtered through this, so a provider that echoes
#: the request cannot move a learner's source code into an exception string.
_SECRET_MARKERS = (
    "authorization",
    "bearer ",
    "api_key",
    "api-key",
    "sk-",
    "openai_api_key",
    "secret",
    "password",
)


def safe_detail(text: str | None, fallback: str) -> str:
    """A bounded, single-line detail message that is safe to log and to return.

    Strips control characters and newlines (so a multi-line upstream body cannot
    forge log lines), collapses runs of whitespace, truncates, and refuses to
    return anything that looks like credential material -- in which case the
    caller gets its fallback instead.
    """
    if not text:
        return fallback
    flattened = " ".join(str(text).split())
    if not flattened:
        return fallback
    lowered = flattened.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return fallback
    if len(flattened) > MAX_DETAIL_LENGTH:
        flattened = f"{flattened[:MAX_DETAIL_LENGTH].rstrip()}…"
    return flattened


class AIError(RuntimeError):
    """Base class for every failure the AI layer reports."""


class AIProviderNotConfiguredError(AIError):
    """No usable provider is configured, so no request was attempted.

    Raised before anything leaves the host. It is deliberately *not* an
    ``AIProviderError``: there is no upstream to have failed, and a caller that
    answered this one with ``502`` would be reporting a fault that did not happen.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            safe_detail(
                message,
                "AI is not configured on this deployment.",
            )
        )


class AIProviderError(AIError):
    """The provider was contacted and could not produce a usable completion.

    ``upstream_status`` is the provider's own numeric HTTP status when there was
    one, and ``None`` for a connection failure, a timeout that the transport did
    not attribute to the provider, or a response whose shape was unusable. It is
    kept as a structured field rather than folded into the message so an operator
    can read it without any risk of carrying upstream text alongside it.
    """

    def __init__(self, message: str | None = None, *, upstream_status: int | None = None) -> None:
        super().__init__(safe_detail(message, "The AI provider could not be reached."))
        self.upstream_status = upstream_status


class AIProviderTimeoutError(AIProviderError):
    """The provider did not answer within the configured budget.

    A subclass of :class:`AIProviderError` because a timeout *is* a provider
    failure in the general sense, while every mapping in this application checks
    the timeout first so it can answer ``504`` rather than ``502``.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "The AI provider did not respond in time.")


class AIRateLimitError(AIError):
    """This learner has used their per-minute AI budget.

    ``retry_after_seconds`` is what the response advertises in ``Retry-After``.
    It is an estimate from the sliding window, not a promise: the caller is told
    when it is worth trying again, not when the slot is guaranteed.
    """

    def __init__(self, retry_after_seconds: float) -> None:
        self.retry_after_seconds = max(1, int(round(retry_after_seconds)))
        super().__init__(
            f"Too many AI requests. Try again in about {self.retry_after_seconds} second(s)."
        )


__all__ = [
    "MAX_DETAIL_LENGTH",
    "AIError",
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "AIProviderTimeoutError",
    "AIRateLimitError",
    "safe_detail",
]
