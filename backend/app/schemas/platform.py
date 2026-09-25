from pydantic import BaseModel


class AlgorithmResponse(BaseModel):
    id: str
    name: str
    category: str
    time_complexity: str | None = None
    space_complexity: str | None = None
    supported_languages: list[str]


class AlgorithmListResponse(BaseModel):
    items: list[AlgorithmResponse]


class AIStatusResponse(BaseModel):
    provider: str
    configured: bool
    model: str
    message: str
