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
    #: The languages this problem ships a starter for. Only ever a subset of what
    #: `/judge/languages` reports, because a tab the runner cannot honour is the
    #: defect that produced a 422 on submit for four problems in an earlier
    #: release.
    supported_languages: list[str] = Field(default_factory=list)
    #: The limits a run on this problem is given, already clamped into the range
    #: the platform will honour, so the editor can show a learner the real numbers
    #: instead of a placeholder.
    time_limit_ms: int = Field(default=0, ge=0)
    memory_limit_mb: int = Field(default=0, ge=0)
    description: str | None = None
    input_format: str | None = None
    output_format: str | None = None
    expected_time_complexity: str | None = None
    expected_space_complexity: str | None = None


class ProblemListResponse(BaseModel):
    items: list[ProblemSummary]
    total: int
    limit: int
    offset: int


class DashboardSummary(BaseModel):
    total_problems: int
    by_difficulty: dict[str, int]
