"""AI providers shipped with the platform.

Importing this package does not import the HTTP provider's dependencies eagerly
beyond ``httpx``, which is already a backend dependency. Keeping the three
implementations in their own modules is what lets the registry resolve a name to
one class without importing the others, and lets a test reach for the
deterministic fake without the real transport anywhere in the path.
"""

from backend.app.ai.providers.disabled import DisabledAIProvider
from backend.app.ai.providers.fake import FakeAIProvider
from backend.app.ai.providers.openai_compatible import OpenAICompatibleProvider

__all__ = ["DisabledAIProvider", "FakeAIProvider", "OpenAICompatibleProvider"]
