from pydantic import BaseModel, ConfigDict, Field


class ProblemExample(BaseModel):
    input: str
    output: str
    explanation: str | None = None


class ProblemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str
    difficulty: str
    topics: list[str] = Field(default_factory=list)


class ProblemDetail(ProblemSummary):
    examples: list[ProblemExample] = Field(default_factory=list)
    constraints: str | None = None
    starter_code: dict[str, str] = Field(default_factory=dict)


class ProblemListResponse(BaseModel):
    items: list[ProblemSummary]
    total: int
    limit: int
    offset: int


class DashboardSummary(BaseModel):
    total_problems: int
    by_difficulty: dict[str, int]
