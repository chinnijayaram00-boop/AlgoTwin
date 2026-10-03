"""The service behind the comparison view.

One rule shapes this whole module: **every side gets the same input.** Two
algorithms can only be compared if they were handed the same bytes and solved the
same task, and both of those are enforced here rather than trusted to the client.

*Same task* comes from the registry's ``comparison_group``. Bubble sort and quicksort
share one, so they can be compared. Bubble sort and Kadane's do not, and asking for
that pairing is refused outright rather than answered with two columns of numbers
that look like a result and are not -- the fastest way to sort five numbers and the
fastest way to find a subarray's sum are not competing on anything.

*Same input* is enforced structurally. The request body has one ``input`` field and
the sides carry only an algorithm id, so there is no way to express "these two got
different inputs" even by accident. Each side is then run in its own worker with that
one input, and the response echoes the input back as the evidence.

What this module will not do is hide a failure. A side that could not run still
appears, with ``status`` saying so and its measurements absent. Dropping it would
turn "three algorithms, two of which produced a number" into a two-way comparison
that looks complete, and a comparison whose failure is invisible is worse than no
comparison at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.algorithms.registry import AlgorithmDescriptor
from backend.app.services import visualization_service
from backend.app.services.visualization_service import (
    AlgorithmNotFoundError,
    InvalidVisualizationInputError,
    VisualizationNotConfiguredError,
    VisualizationUnavailableError,
)
from backend.app.visualization.limits import (
    MAX_COMPARISON_SIDES,
    MIN_COMPARISON_SIDES,
)
from backend.app.visualization.runner import RunOutcome, VisualizationError

#: A side that produced a real, measured result.
SIDE_OK = "ok"
#: A side the platform knows about but could not run: the input did not fit its
#: grammar, or the run hit a limit.
SIDE_FAILED = "failed"
#: A side whose algorithm id is not in the registry at all. Distinct from ``failed``
#: because "we do not have this algorithm" and "this algorithm could not run on this
#: input" are different facts and the UI should say which happened.
SIDE_UNAVAILABLE = "unavailable"


class ComparisonNotAllowedError(ValueError):
    """The requested algorithms do not solve the same task.

    Refusing is the only honest answer. Running them over one input anyway would
    produce two columns of numbers, and a learner would reasonably read the faster
    one as the better algorithm -- which is a false claim, not an imprecise one.
    """

    def __init__(self, group: str, names: list[str]) -> None:
        super().__init__(
            f"These algorithms do not solve the same task, so they cannot be compared on one "
            f"input: {', '.join(names)}. Pick algorithms that all belong to the same group."
        )
        self.group = group
        self.names = names


class ComparisonTooSmallError(ValueError):
    """Fewer than two algorithms were requested.

    A one-sided "comparison" has nothing to compare against, so it is a request the
    service declines rather than one it satisfies with an empty result.
    """


class ComparisonTooLargeError(ValueError):
    """More algorithms were requested than the platform will put side by side."""


@dataclass(frozen=True)
class ComparisonSide:
    """One algorithm's outcome, measured or not."""

    algorithm: AlgorithmDescriptor
    status: str
    runtime_ms: float | None
    peak_memory_mb: float | None
    repetitions: int | None
    metrics: dict[str, int]
    result: str | None
    frame_count: int | None
    error: str | None

    @property
    def produced_a_measurement(self) -> bool:
        return self.status == SIDE_OK


@dataclass(frozen=True)
class ComparisonResult:
    """A whole comparison."""

    input: str
    group: str
    algorithms: tuple[AlgorithmDescriptor, ...]
    sides: tuple[ComparisonSide, ...]

    @property
    def complete(self) -> bool:
        """Whether every side produced a result.

        False means at least one side did not, and the response has to say so -- a
        comparison missing a column is a different claim from one where that column
        happened to be slow.
        """
        return all(side.status == SIDE_OK for side in self.sides)


def _resolve_sides(algorithm_ids: list[str]) -> tuple[AlgorithmDescriptor, ...]:
    """Resolve every requested id, or refuse.

    All or nothing, and the reason is the same as for a group mismatch: a comparison
    silently missing one of the three algorithms the learner asked about is a
    different result from the one they requested.
    """
    if len(algorithm_ids) < MIN_COMPARISON_SIDES:
        raise ComparisonTooSmallError(
            f"Pick at least {MIN_COMPARISON_SIDES} algorithms to compare."
        )
    if len(algorithm_ids) > MAX_COMPARISON_SIDES:
        raise ComparisonTooLargeError(
            f"At most {MAX_COMPARISON_SIDES} algorithms can be compared side by side."
        )
    # A repeated id would compare an algorithm with itself and produce two identical
    # columns, which looks like a result and informs nothing.
    unique_ids = list(dict.fromkeys(identifier.strip().lower() for identifier in algorithm_ids))
    if len(unique_ids) != len(algorithm_ids):
        raise ComparisonTooSmallError("The same algorithm was listed twice.")

    return tuple(visualization_service.describe_algorithm(identifier) for identifier in unique_ids)


def _check_group(algorithms: tuple[AlgorithmDescriptor, ...]) -> str:
    """Every algorithm must be in the same comparison group.

    The group is taken from the first algorithm rather than compared pairwise
    because grouping is a partition: if all share one group, all pairs do.
    """
    group = algorithms[0].comparison_group
    outsiders = [
        algorithm.name for algorithm in algorithms if algorithm.comparison_group != group
    ]
    if outsiders:
        raise ComparisonNotAllowedError(group, [algorithms[0].name, *outsiders])
    return group


def _side_from_outcome(algorithm: AlgorithmDescriptor, outcome: RunOutcome) -> ComparisonSide:
    """Turn one worker's outcome into a side.

    Every measurement is copied through *as it came*, including its absence. A side
    that ran but could not be timed keeps ``runtime_ms`` as ``None`` rather than as
    ``0.0``, because the frontend renders an absent measurement as "Not measured" and
    would render a zero as "faster than everything".
    """
    if outcome.succeeded:
        return ComparisonSide(
            algorithm=algorithm,
            status=SIDE_OK,
            runtime_ms=outcome.runtime_ms,
            peak_memory_mb=outcome.peak_memory_mb,
            repetitions=outcome.repetitions,
            metrics=outcome.metrics,
            result=outcome.result,
            frame_count=outcome.frame_count,
            error=None,
        )
    return ComparisonSide(
        algorithm=algorithm,
        status=SIDE_FAILED,
        runtime_ms=None,
        peak_memory_mb=outcome.peak_memory_mb,
        repetitions=outcome.repetitions,
        metrics=outcome.metrics,
        result=None,
        frame_count=outcome.frame_count,
        # The worker's own words, so a failure names its cause -- a grammar mismatch
        # reads differently from a wall-clock limit and the learner can act on one
        # and not the other.
        error=outcome.error or "The algorithm could not be run on this input.",
    )


def compare_algorithms(
    algorithm_ids: list[str],
    input_text: str,
    settings: object,
    *,
    max_frames: int | None = None,
    repetitions: int | None = None,
    wall_clock_ms: int | None = None,
) -> ComparisonResult:
    """Run two or more algorithms on one input and report each side.

    Sides run one after another rather than concurrently. A comparison is a small,
    bounded amount of work -- at most four short traced runs -- and running them
    serially means the runtime figures are not contaminated by two processes
    competing for the same cores, which for a measurement in the sub-millisecond
    range is the difference between a figure and a coin toss.
    """
    visualization_service.require_enabled(settings)
    algorithms = _resolve_sides(algorithm_ids)
    group = _check_group(algorithms)

    # The input is validated once, against the shared grammar, before any worker
    # starts. All the sides share a group and therefore a grammar, so one check
    # covers them all -- and a grammar mismatch is a 422 for the whole request rather
    # than a failure repeated in every column.
    visualization_service.validate_input(algorithms[0], input_text)

    sides: list[ComparisonSide] = []
    for algorithm in algorithms:
        try:
            outcome = visualization_service.run_outcome(
                algorithm,
                input_text,
                settings,
                mode="measure",
                max_frames=max_frames,
                wall_clock_ms=wall_clock_ms,
                repetitions=repetitions,
            )
        except VisualizationError as error:
            # The worker could not even be started. That is a side that failed, not a
            # request that failed: the other sides are still real and still meaningful.
            sides.append(
                ComparisonSide(
                    algorithm=algorithm,
                    status=SIDE_FAILED,
                    runtime_ms=None,
                    peak_memory_mb=None,
                    repetitions=None,
                    metrics={},
                    result=None,
                    frame_count=None,
                    error=str(error),
                )
            )
            continue
        sides.append(_side_from_outcome(algorithm, outcome))

    return ComparisonResult(
        input=input_text,
        group=group,
        algorithms=algorithms,
        sides=tuple(sides),
    )


__all__ = [
    "SIDE_FAILED",
    "SIDE_OK",
    "SIDE_UNAVAILABLE",
    "ComparisonNotAllowedError",
    "ComparisonResult",
    "ComparisonSide",
    "ComparisonTooLargeError",
    "ComparisonTooSmallError",
    "AlgorithmNotFoundError",
    "InvalidVisualizationInputError",
    "VisualizationNotConfiguredError",
    "VisualizationUnavailableError",
    "compare_algorithms",
]
