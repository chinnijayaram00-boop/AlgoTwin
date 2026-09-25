from backend.app.ai.provider import AIProvider
from backend.app.core.config import Settings


class AIProviderNotConfiguredError(RuntimeError):
    pass


class DisabledAIProvider:
    name = "disabled"

    async def explain(self, problem: str, solution: str, language: str) -> str:
        raise AIProviderNotConfiguredError("AI explanations are disabled until a provider is configured.")


class AIService:
    def __init__(self, settings: Settings, provider: AIProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or DisabledAIProvider()

    @property
    def configured(self) -> bool:
        return self.settings.ai_is_configured

    async def explain(self, problem: str, solution: str, language: str) -> str:
        if not self.configured:
            raise AIProviderNotConfiguredError("AI explanations are disabled until a provider is configured.")
        return await self.provider.explain(problem, solution, language)
