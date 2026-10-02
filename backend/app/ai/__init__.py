"""The AI layer: a provider boundary, the providers themselves, and one registry.

``backend.app.ai`` is deliberately independent of the database, the HTTP layer, and
the catalog. It knows how to ask a model a question and how to report failure; it
does not know what a problem or a submission is. The grounding, the caching, the
rate limit, and the persistence all live above it in
:mod:`backend.app.services.ai_service`, which is what lets the same provider be
exercised in a test without a database and the same service be exercised without a
network.
"""

from backend.app.ai.errors import (
    AIError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderTimeoutError,
    AIRateLimitError,
)
from backend.app.ai.provider import (
    AI_INSIGHT_KINDS,
    KIND_CODE_COMPLEXITY,
    KIND_PROBLEM_EXPLANATION,
    KIND_SUBMISSION_DIAGNOSIS,
    AICompletionRequest,
    AICompletionResponse,
    AIProvider,
)
from backend.app.ai.registry import (
    PROVIDER_NAMES,
    AIProviderStatus,
    normalize_provider_name,
    provider_status,
    resolve_provider,
)
from backend.app.ai.service import AIService

__all__ = [
    "AI_INSIGHT_KINDS",
    "KIND_CODE_COMPLEXITY",
    "KIND_PROBLEM_EXPLANATION",
    "KIND_SUBMISSION_DIAGNOSIS",
    "PROVIDER_NAMES",
    "AICompletionRequest",
    "AICompletionResponse",
    "AIError",
    "AIProvider",
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "AIProviderStatus",
    "AIProviderTimeoutError",
    "AIRateLimitError",
    "AIService",
    "normalize_provider_name",
    "provider_status",
    "resolve_provider",
]
