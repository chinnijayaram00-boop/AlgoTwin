"""The service behind the algorithm lab.

Two public operations, one boundary. :func:`describe_algorithm` answers questions
about the registry and starts no process; :func:`visualize_algorithm` hands one
input to the worker in :mod:`backend.app.visualization.runner` and turns the frames
that come back into a timeline.

Three rules are enforced here rather than in the route, because they are rules about
the platform's behaviour and not about HTTP:

* A visualization is capped, and a capped run says so. ``truncated`` is computed by
  the worker from whether the frame ceiling actually stopped the algorithm, not from
  whether the response looks long.
* The last frame's counters are not the whole run's counters when the run was cut
  short, so the run-level metrics are reported separately from the frames.
* Nothing is inferred. No complexity is computed from the measured time, no counter
  is back-filled from a frame, and an unmeasurable figure stays absent.

The module keeps the dataclasses the foundation release published
(:class:`VisualizationRequest`, :class:`VisualizationFrame`,
:class:`VisualizationService`) so anything already importing them still works. They
are now thin wrappers over the same registry and runner rather than a stub that
raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.algorithms.frames import STATUS_TRUNCATED
from backend.app.algorithms.inputs import InvalidInputError
from backend.app.algorithms.registry import (
    AlgorithmDescriptor,
    algorithms_for_problem,
    get_algorithm,
    list_algorithms,
    list_by_category,
    list_comparable,
)
from backend.app.visualization.limits import MAX_INPUT_BYTES, VisualizationLimits
from backend.app.visualization.runner import RunOutcome, VisualizationError, execute


class VisualizationNotConfiguredError(RuntimeError):
    """The deployment has the algorithm lab switched off.

    A 503 rather than a 404. The feature exists and is registered; this host has
    chosen not to run it, which is a different fact from "there is no such
    algorithm".
    """


class AlgorithmNotFoundError(LookupError):
    """No registered algorithm has this id.

    A 404 with the same message every other unknown-resource route gives, so a
    request for an algorithm that does not exist is indistinguishable from a request
    for anything else that does not exist.
    """


class InvalidVisualizationInputError(ValueError):
    """The input does not parse under the algorithm's own grammar.

    A 422, and the message names the grammar the caller should check rather than
    showing them a stack trace. This is the input being wrong, not the platform.
    """


class VisualizationUnavailableError(RuntimeError):
    """The worker could not produce a timeline.

    A 502 by way of 500: the run was attempted and the platform could not complete
    it. It must never be reported as a pass, a failure, or an empty-but-successful
    visualization.
    """


@dataclass(frozen=True)
class VisualizationRequest:
    algorithm_id: str
    input: str


@dataclass(frozen=True)
class VisualizationFrame:
    step: int
    state: dict[str, object]
    explanation: str


@dataclass(frozen=True)
class VisualizationResult:
    """One run's timeline, before it becomes HTTP."""

    algorithm: AlgorithmDescriptor
    input: str
    frames: tuple[VisualizationFrame, ...]
    metrics: dict[str, int]
    result: str | None
    truncated: bool
    duration_ms: float | None
    peak_memory_mb: float | None

    @property
    def step_count(self) -> int:
        return len(self.frames)


def _limits(
    settings: object,
    max_frames: int | None,
    wall_clock_ms: int | None,
    repetitions: int | None,
) -> VisualizationLimits:
    """Resolve the run budget from deployment settings and the request.

    The request can only *lower* a ceiling, never raise it. A caller asking for
    20,000 frames on a deployment configured for 2,000 gets the deployment's number:
    the configured limit is the limit, and a request parameter is not a way around it.
    """
    defaults = VisualizationLimits()
    configured_frames = int(getattr(settings, "visualization_max_frames", defaults.max_frames))
    configured_clock = int(getattr(settings, "visualization_wall_clock_ms", defaults.wall_clock_ms))
    configured_repeats = int(getattr(settings, "visualization_repetitions", defaults.repetitions))
    frames = min(max_frames, configured_frames) if max_frames is not None else configured_frames
    clock = min(wall_clock_ms, configured_clock) if wall_clock_ms is not None else configured_clock
    repeats = (
        min(repetitions, configured_repeats) if repetitions is not None else configured_repeats
    )
    return VisualizationLimits.resolve(
        wall_clock_ms=clock, max_frames=frames, repetitions=repeats
    )


def require_enabled(settings: object) -> None:
    """Refuse to start a worker when the lab is switched off.

    Checked before anything is spawned rather than inside the worker, so a disabled
    deployment starts no process at all -- the same rule the judge's
    ``execution_enabled`` kill switch follows.
    """
    if not bool(getattr(settings, "visualization_enabled", True)):
        raise VisualizationNotConfiguredError("Algorithm visualization is not enabled on this deployment.")


def describe_algorithm(algorithm_id: str) -> AlgorithmDescriptor:
    """The descriptor for one algorithm, or :class:`AlgorithmNotFoundError`."""
    descriptor = get_algorithm(algorithm_id)
    if descriptor is None:
        raise AlgorithmNotFoundError(f"No algorithm named {algorithm_id!r} is registered.")
    return descriptor


def validate_input(descriptor: AlgorithmDescriptor, input_text: str) -> None:
    """Check an input against the grammar without running anything.

    Parsing twice is cheaper than running twice and much cheaper than answering a
    bad request with a worker spawn, and the error it raises is the one worth
    showing: it names the format.
    """
    if len(input_text.encode("utf-8")) > MAX_INPUT_BYTES:
        raise InvalidVisualizationInputError("That input is larger than this platform accepts.")
    if not input_text.strip():
        raise InvalidVisualizationInputError("Enter an input to visualize.")
    try:
        descriptor.parse_input(input_text)
    except InvalidInputError as error:
        raise InvalidVisualizationInputError(str(error)) from error


def run_outcome(
    descriptor: AlgorithmDescriptor,
    input_text: str,
    settings: object,
    *,
    mode: str = "run",
    max_frames: int | None = None,
    wall_clock_ms: int | None = None,
    repetitions: int | None = None,
) -> RunOutcome:
    """Hand one job to the worker and return what it reported.

    The outcome is returned rather than a raised error because a comparison needs to
    keep going after one side fails; the single-visualization path turns a bad
    outcome into :class:`VisualizationUnavailableError`.
    """
    return execute(descriptor.id, input_text, _limits(settings, max_frames, wall_clock_ms, repetitions), mode)


def visualize_algorithm(
    algorithm_id: str,
    input_text: str,
    settings: object,
    *,
    max_frames: int | None = None,
    wall_clock_ms: int | None = None,
) -> VisualizationResult:
    """Produce a timeline for one algorithm on one input.

    The order is deliberate. The feature switch is checked, then the algorithm is
    resolved, then the input is parsed, and only then is a process started. Each step
    can fail with a distinct, actionable answer, and the one that must not happen --
    spawning a worker to discover the input was malformed -- cannot.
    """
    require_enabled(settings)
    descriptor = describe_algorithm(algorithm_id)
    validate_input(descriptor, input_text)

    try:
        outcome = run_outcome(
            descriptor, input_text, settings, max_frames=max_frames, wall_clock_ms=wall_clock_ms
        )
    except VisualizationError as error:
        raise VisualizationUnavailableError(str(error)) from error

    if outcome.kind == "invalid_request":
        # The worker re-parsed the same input the service already validated, so
        # reaching here means the two disagree about the grammar -- a platform fault,
        # reported as one rather than blamed on the caller's input.
        raise VisualizationUnavailableError(outcome.error or "The run was rejected.")
    if not outcome.succeeded:
        raise VisualizationUnavailableError(
            outcome.error or "The algorithm could not be traced."
        )
    if not outcome.frames:
        raise VisualizationUnavailableError("The algorithm produced no frames.")

    frames = tuple(
        VisualizationFrame(step=index, state=dict(state), explanation=str(state.get("explanation") or ""))
        for index, state in enumerate(outcome.frames)
    )
    # The status on the last frame is the worker's own word for whether the run
    # finished; the flag on the result is whether the *ceiling* stopped it. They can
    # disagree in one direction only -- a run that finished early is never called
    # truncated -- so the response is truncated if either says so.
    truncated = outcome.truncated or frames[-1].state.get("status") == STATUS_TRUNCATED
    return VisualizationResult(
        algorithm=descriptor,
        input=input_text,
        frames=frames,
        metrics=outcome.metrics,
        result=outcome.result,
        truncated=truncated,
        duration_ms=outcome.duration_ms or None,
        peak_memory_mb=outcome.peak_memory_mb,
    )


def describe_all() -> tuple[AlgorithmDescriptor, ...]:
    """Every registered algorithm."""
    return list_algorithms()


def describe_comparables(algorithm_id: str) -> tuple[AlgorithmDescriptor, ...]:
    """The algorithms this one may be compared against."""
    return list_comparable(algorithm_id)


def describe_problem_algorithms(slug: str) -> tuple[AlgorithmDescriptor, ...]:
    """The algorithms a catalog problem names as its approach."""
    return algorithms_for_problem(slug)


def describe_by_category() -> dict[str, tuple[AlgorithmDescriptor, ...]]:
    """The registry grouped by category."""
    return list_by_category()


def input_grammar_hint() -> dict[str, str]:
    """One worked example per grammar, for the UI's help text.

    Taken from the registry rather than written again here. The hint a learner reads
    next to the input box and the hint the tests assert on must be the same string,
    and the only way to keep them the same is to have one of them.
    """
    return {descriptor.input_grammar: descriptor.input_hint for descriptor in list_algorithms()}


class VisualizationService:
    """The foundation release's entry point, now backed by the registry.

    Kept so existing callers and the service-level tests keep working. The facade
    delegates to the module functions rather than reimplementing them, so there is
    one implementation of "what does a frame mean" in the platform.
    """

    def generate_frames(self, request: VisualizationRequest) -> tuple[VisualizationFrame, ...]:
        """The timeline for one request.

        This entry point takes no settings because the dataclass predates the
        deployment switches; it uses the documented defaults, and callers that need a
        configured deployment should call :func:`visualize_algorithm` directly.
        """
        limits = VisualizationLimits.resolve()
        outcome = execute(request.algorithm_id, request.input, limits, "run")
        if not outcome.succeeded:
            raise VisualizationNotConfiguredError(
                outcome.error or "Algorithm execution did not complete."
            )
        return tuple(
            VisualizationFrame(step=index, state=dict(state), explanation=str(state.get("explanation") or ""))
            for index, state in enumerate(outcome.frames)
        )


__all__ = [
    "AlgorithmNotFoundError",
    "InvalidVisualizationInputError",
    "VisualizationFrame",
    "VisualizationNotConfiguredError",
    "VisualizationRequest",
    "VisualizationResult",
    "VisualizationService",
    "VisualizationUnavailableError",
    "describe_all",
    "describe_algorithm",
    "describe_by_category",
    "describe_comparables",
    "describe_problem_algorithms",
    "input_grammar_hint",
    "require_enabled",
    "run_outcome",
    "validate_input",
    "visualize_algorithm",
]
