from typing import Protocol


class AIProvider(Protocol):
    name: str

    async def explain(self, problem: str, solution: str, language: str) -> str:
        ...
