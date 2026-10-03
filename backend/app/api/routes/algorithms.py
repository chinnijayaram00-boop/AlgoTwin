"""Endpoints for the algorithm lab.

Five routes: three public reads and two authenticated runs.

The public ones -- ``GET /algorithms``, ``GET /algorithms/categories``,
``GET /algorithms/{algorithm_id}`` -- are public because a card that names a
complexity and a summary is not learner data, and making the lab's catalog readable
only after login leaves the marketing page with nothing to show. The two that start
a worker process require a token, and are guarded exactly the way the run endpoint
is: an unauthenticated request gets 401 before anything is spawned.

Two details that are easy to get wrong and load-bearing:

* **Registration order.** FastAPI matches in the order routes are added, and
  ``{algorithm_id}`` is a single path segment that would happily swallow
  ``categories``. The literal routes are therefore registered before the parameter
  route. The two POST paths never collide regardless, because a path parameter does
  not match across a ``/``.
* **The list envelope.** ``GET /algorithms`` still returns ``{"items": [...]}``,
  because that is what it has always returned and something already reads it. The
  per-algorithm fields the lab needs are added, and they are additive -- a client
  that ignores them is unaffected.

The handlers are ``def``, not ``async def``, so FastAPI runs them in the threadpool.
Each one is synchronous by design: the work is bounded by a wall clock and a frame
ceiling, and blocking the event loop while a worker is supervised would make one
slow visualization delay every other request on the process.
"""

from fastapi import APIRouter, HTTPException, Path, status

from backend.app.algorithms.registry import (
    AlgorithmDescriptor,
    algorithms_for_problem,
    list_algorithms,
    list_by_category,
    list_comparable,
)
from backend.app.api.dependencies import AppSettings, CurrentUser
from backend.app.schemas.visualization import (
    AlgorithmDetail,
    AlgorithmSummary,
    ComparisonRequestBody,
    ComparisonResponse,
    ComparisonSideResponse,
    VisualizationFrameResponse,
    VisualizationRequestBody,
    VisualizationResponse,
    VisualizationStateResponse,
)
from backend.app.services import comparison_service, visualization_service

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


def to_summary(descriptor: AlgorithmDescriptor) -> AlgorithmSummary:
    """One registry entry in the shape the catalog publishes."""
    return AlgorithmSummary(
        id=descriptor.id,
        name=descriptor.name,
        category=descriptor.category,
        time_complexity=descriptor.time_complexity,
        space_complexity=descriptor.space_complexity,
        supported_languages=list(descriptor.supported_languages),
        summary=descriptor.summary,
        input_grammar=descriptor.input_grammar,
        input_hint=descriptor.input_hint,
        comparison_group=descriptor.comparison_group,
        state_kind=descriptor.state_kind,
        sample_input=descriptor.sample_input,
        is_stable=descriptor.is_stable,
    )


@router.get("", response_model=dict[str, list[AlgorithmSummary]])
def list_algorithms_route() -> dict[str, list[AlgorithmSummary]]:
    """Every algorithm the lab can actually run.

    The ``items`` envelope is the one this endpoint has always had. Every entry names
    a real function in :mod:`backend.app.algorithms.reference`; a card that did not
    would be a lie the lab would only reveal on click.
    """
    return {"items": [to_summary(descriptor) for descriptor in list_algorithms()]}


@router.get("/categories", response_model=dict[str, list[AlgorithmSummary]])
def list_algorithm_categories() -> dict[str, list[AlgorithmSummary]]:
    """The same catalog, grouped by category, for the picker."""
    return {
        category: [to_summary(descriptor) for descriptor in members]
        for category, members in list_by_category().items()
    }


@router.get("/problems/{problem_slug}/algorithms", response_model=dict[str, list[AlgorithmSummary]])
def get_problem_algorithms(problem_slug: str = Path(min_length=1)) -> dict[str, list[AlgorithmSummary]]:
    """The algorithms a catalog problem names as its approach.

    This is the reuse the registry gets from the problem catalog: each descriptor
    names the problems it is the canonical answer for, so the lab can offer "watch
    the approach" from a problem page without a second mapping table that could
    disagree with the registry.
    """
    return {
        "items": [to_summary(descriptor) for descriptor in algorithms_for_problem(problem_slug)]
    }


@router.post("/compare", response_model=ComparisonResponse)
def compare_algorithms_route(
    payload: ComparisonRequestBody,
    current_user: CurrentUser,
    settings: AppSettings,
) -> ComparisonResponse:
    """Run two to four algorithms on one shared input and report each side.

    The body has one ``input`` and a list of algorithm ids, so it is structurally
    impossible to send two sides different inputs. Every requested side comes back,
    including one that failed, and a measurement that was not taken stays absent
    rather than becoming a zero.
    """
    _ = current_user
    algorithm_ids = [side.algorithm_id for side in payload.algorithms]
    try:
        outcome = comparison_service.compare_algorithms(
            algorithm_ids,
            payload.input,
            settings,
            max_frames=payload.max_frames,
            repetitions=payload.repetitions,
            wall_clock_ms=payload.wall_clock_ms,
        )
    except comparison_service.VisualizationNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except comparison_service.AlgorithmNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Algorithm not found."
        ) from error
    except comparison_service.InvalidVisualizationInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except comparison_service.ComparisonNotAllowedError as error:
        # A 422, not a best-effort response: two algorithms solving different tasks
        # cannot be compared on one input, and a response with two plausible-looking
        # columns would be worse than a refusal.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except (comparison_service.ComparisonTooSmallError, comparison_service.ComparisonTooLargeError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    return ComparisonResponse(
        input=outcome.input,
        comparison_group=outcome.group,
        algorithms=[to_summary(descriptor) for descriptor in outcome.algorithms],
        sides=[
            ComparisonSideResponse(
                algorithm=to_summary(side.algorithm),
                status=side.status,
                runtime_ms=side.runtime_ms,
                peak_memory_mb=side.peak_memory_mb,
                repetitions=side.repetitions,
                metrics=side.metrics,
                result=side.result,
                frame_count=side.frame_count,
                error=side.error,
            )
            for side in outcome.sides
        ],
        complete=outcome.complete,
    )


@router.get("/{algorithm_id}", response_model=AlgorithmDetail)
def get_algorithm_route(algorithm_id: str = Path(min_length=1)) -> AlgorithmDetail:
    """One algorithm in full, including which pairings are allowed.

    Public, and free of learner data. ``comparable_with`` is computed from the
    registry so the client can only ever offer a pairing the backend would accept.
    """
    try:
        descriptor = visualization_service.describe_algorithm(algorithm_id)
    except visualization_service.AlgorithmNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Algorithm not found."
        ) from error
    return AlgorithmDetail(
        **to_summary(descriptor).model_dump(),
        comparable_with=[other.id for other in list_comparable(descriptor.id)],
        compares_on=list(descriptor.comparison),
    )


@router.post("/{algorithm_id}/visualize", response_model=VisualizationResponse)
def visualize_algorithm_route(
    payload: VisualizationRequestBody,
    current_user: CurrentUser,
    settings: AppSettings,
    algorithm_id: str = Path(min_length=1),
) -> VisualizationResponse:
    """Run one platform algorithm over one input and return its timeline.

    The frames are the algorithm's own state transitions, produced by a generator
    that yields as it works. Nothing is reconstructed after the fact, so every frame
    is a state the algorithm was genuinely in when it reached it.

    The input is the learner's own and is never stored: it is parsed, traced, and
    discarded. ``truncated`` is the worker's word for whether the frame ceiling
    actually stopped the run, and a capped timeline is never presented as the whole
    one.
    """
    _ = current_user
    try:
        outcome = visualization_service.visualize_algorithm(
            algorithm_id,
            payload.input,
            settings,
            max_frames=payload.max_frames,
            wall_clock_ms=payload.wall_clock_ms,
        )
    except visualization_service.VisualizationNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except visualization_service.AlgorithmNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Algorithm not found."
        ) from error
    except visualization_service.InvalidVisualizationInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except visualization_service.VisualizationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    return VisualizationResponse(
        algorithm=to_summary(outcome.algorithm),
        input=outcome.input,
        frames=[
            VisualizationFrameResponse(
                step=frame.step,
                state=VisualizationStateResponse(**frame.state),
                explanation=frame.explanation,
            )
            for frame in outcome.frames
        ],
        metrics=outcome.metrics,
        result=outcome.result,
        truncated=outcome.truncated,
        duration_ms=outcome.duration_ms,
        peak_memory_mb=outcome.peak_memory_mb,
    )


__all__ = ["router", "to_summary"]
