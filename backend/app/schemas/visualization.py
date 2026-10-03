"""Request and response bodies for the algorithm lab.

Two things are worth saying about the shapes here.

**Every field a caller did not send is absent, not zero.** ``runtime_ms`` and
``peak_memory_mb`` on a comparison side are both optional, and both are optional for
the same reason: they are measured in a separate process on a platform that may not
be able to measure them at all. Windows has no ``getrusage``, so peak memory is
genuinely unknown there. The frontend renders an absent measurement as ``"Not
measured"``, and the one thing it must never do is render it as ``0`` -- a zero is
a claim, and the honest claim is "we did not measure this".

**The frame list is ordered and complete up to ``truncated``.** A visualization
returns every frame the algorithm reached, in order, with ``step`` matching the
index. A client can therefore scrub to any index and know it is the state the
algorithm was really in at that point, which is the entire reason the timeline is
useful.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: The request bodies forbid unknown fields, matching the rest of the API. A typo in
#: ``max_frames`` should be a 422, not a silently ignored request that runs with the
#: default budget.
_STRICT = ConfigDict(extra="forbid")


class AlgorithmSummary(BaseModel):
    """One algorithm as the catalog lists it."""

    id: str
    name: str
    category: str
    time_complexity: str | None = None
    space_complexity: str | None = None
    supported_languages: list[str]
    summary: str
    input_grammar: str
    input_hint: str
    comparison_group: str
    state_kind: str
    sample_input: str
    is_stable: bool | None = None


class AlgorithmDetail(AlgorithmSummary):
    """One algorithm in full, for the page that will visualize it.

    ``comparable_with`` is included so the frontend never has to hold the whole
    registry to know which pairings the backend would accept. It is the backend's
    answer to its own question: two algorithms may only be compared when they solve
    the same task, and the client must not be able to offer a pairing the backend
    would refuse.
    """

    comparable_with: list[str]
    compares_on: list[str]


class FrameCellResponse(BaseModel):
    label: str
    tone: str
    detail: str | None = None


class FrameRowResponse(BaseModel):
    label: str
    cells: list[FrameCellResponse]


class VisualizationStateResponse(BaseModel):
    """One normalized state: what the renderer draws, and what the run has counted.

    The shape does not vary by algorithm. A sort draws bars, a stack draws labelled
    boxes, a grid draws a grid, and all three are this object with a different
    ``kind`` -- so the frontend has one renderer instead of fourteen.
    """

    kind: str
    rows: list[FrameRowResponse]
    auxiliary: list[FrameRowResponse]
    pointers: dict[str, int] = Field(default_factory=dict)
    #: Real operation counts. A key that is absent means "this algorithm does not
    #: perform that operation", never "zero of them happened".
    metrics: dict[str, int] = Field(default_factory=dict)
    status: str
    result: str | None = None


class VisualizationFrameResponse(BaseModel):
    """One step of a timeline."""

    step: int
    state: VisualizationStateResponse
    explanation: str


class VisualizationRequestBody(BaseModel):
    """Ask for a timeline of one algorithm on one input."""

    model_config = _STRICT

    input: str = Field(min_length=1, description="The input, in the algorithm's own grammar.")
    #: A ceiling on the returned frames. Lowering it is how a caller asks for a
    #: shorter response; the run is reported as truncated if the ceiling is what
    #: stopped it, so a capped timeline is never presented as the whole run.
    max_frames: int | None = Field(default=None, ge=1, le=20_000)
    wall_clock_ms: int | None = Field(default=None, ge=100, le=30_000)


class VisualizationResponse(BaseModel):
    """A timeline, plus everything needed to label it honestly."""

    algorithm: AlgorithmSummary
    input: str
    frames: list[VisualizationFrameResponse]
    #: The counters the algorithm recorded over the *whole* run, which may be more
    #: than the last returned frame if the timeline was capped.
    metrics: dict[str, int] = Field(default_factory=dict)
    result: str | None = None
    truncated: bool = False
    #: Wall clock of the worker process, reported so a slow run is visible as slow
    #: rather than looking like a hang. Not the algorithm's complexity.
    duration_ms: float | None = None
    #: Absent on platforms where the worker cannot measure it.
    peak_memory_mb: float | None = None


class ComparisonSideRequest(BaseModel):
    """One algorithm in a comparison.

    The input is *not* here. It belongs to the whole comparison, because the only
    thing that makes a comparison a comparison is that every side is handed the same
    input; a per-side input field would be an invitation to compare two different
    problems and call it a result.
    """

    model_config = _STRICT

    algorithm_id: str = Field(min_length=1)


class ComparisonRequestBody(BaseModel):
    """Ask for two or more algorithms to be run on the same input."""

    model_config = _STRICT

    algorithms: list[ComparisonSideRequest] = Field(min_length=2, max_length=4)
    input: str = Field(min_length=1, description="The one input every side receives.")
    max_frames: int | None = Field(default=None, ge=1, le=20_000)
    repetitions: int | None = Field(default=None, ge=1, le=25)
    wall_clock_ms: int | None = Field(default=None, ge=100, le=30_000)


class ComparisonSideResponse(BaseModel):
    """One algorithm's result, whether or not it produced one.

    Every requested side appears in the response, including the ones that failed.
    Dropping a failed side would quietly turn "three algorithms, two of which ran"
    into a two-way comparison that looks complete, and the whole point of this
    feature is that the learner can see what actually happened on each side.
    """

    algorithm: AlgorithmSummary
    #: ``ok``, ``failed``, or ``unavailable``. Never an HTTP error code: a 404 on the
    #: third side would be the API answering about itself rather than about the
    #: comparison.
    status: str
    runtime_ms: float | None = Field(
        default=None, description="Median in-process runtime. Absent when not measured."
    )
    peak_memory_mb: float | None = Field(
        default=None, description="Peak worker memory. Absent when not measurable."
    )
    repetitions: int | None = None
    metrics: dict[str, int] = Field(default_factory=dict)
    result: str | None = None
    frame_count: int | None = None
    error: str | None = None


class ComparisonResponse(BaseModel):
    """A comparison, with the shared input echoed back.

    Echoing ``input`` is not padding: it is the evidence that every side received
    the same bytes, and a learner comparing bubble sort against quicksort deserves to
    see what they were both handed.
    """

    input: str
    comparison_group: str
    algorithms: list[AlgorithmSummary]
    sides: list[ComparisonSideResponse]
    #: True when every side produced a result. False means at least one side failed,
    #: and the UI must say so rather than showing the surviving sides as if they were
    #: the whole comparison.
    complete: bool


class ComparisonNotAllowedError(Exception):
    """The requested algorithms do not solve the same task.

    Raised by the service rather than returned as a partially-populated comparison:
    running two algorithms over one input when they mean different things by that
    input produces numbers that look like results and are not, and the only honest
    response is to refuse the pairing.
    """


__all__ = [
    "AlgorithmDetail",
    "AlgorithmSummary",
    "ComparisonNotAllowedError",
    "ComparisonRequestBody",
    "ComparisonResponse",
    "ComparisonSideRequest",
    "ComparisonSideResponse",
    "FrameCellResponse",
    "FrameRowResponse",
    "VisualizationFrameResponse",
    "VisualizationRequestBody",
    "VisualizationResponse",
    "VisualizationStateResponse",
]
