"""What one visualization or comparison run is allowed to cost.

The numbers here are ceilings, and each one is enforced somewhere specific: the
input size by the parser before anything runs, the frame count by the worker as it
collects, the wall clock twice -- once by the worker and again by the parent that
supervises the worker -- and the address space and CPU time by the worker through
POSIX resource limits.

They exist because a visualization endpoint is a synchronous request that runs
code on the learner's behalf. Without them, a large but legal-looking input could
produce a response far bigger than the JSON the browser wanted, or a single
algorithm could spend longer than the request was ever going to be held open for.

The frame ceiling is the interesting one. It is deliberately generous for the
inputs the parser allows and deliberately unforgiving past them: an interactive
timeline is something a person steps through, so a run that would produce
thousands of frames is capped and reported as ``truncated`` rather than shipped.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Grace added on top of the wall clock before the parent gives up on the worker
#: process itself. Same reasoning as the judge's: the worker's own supervision is
#: what should stop the run, and reaching the parent's budget means the worker --
#: not the algorithm -- is the thing that wedged.
WORKER_GRACE_MS = 5_000

#: The most bytes a single visualization input may carry. The parsers cap the
#: element count far below this, so this is the backstop for a hand-built request
#: with very long tokens rather than the normal limit.
MAX_INPUT_BYTES = 64 * 1024

#: The most frames one run may return. Past this the worker stops collecting and
#: marks the timeline ``truncated``.
MAX_FRAMES = 2_000

#: The smallest wall clock a run may be given, for the same reason the judge's
#: minimum exists: a worker that is killed before it starts produces an error, not
#: an animation.
MIN_WALL_CLOCK_MS = 100

#: The default wall clock for one visualization run. These are the platform's own
#: reference implementations over inputs capped at a few dozen elements, so a few
#: hundred milliseconds is generous; the interesting failure mode this defends
#: against is a bug that loops.
DEFAULT_WALL_CLOCK_MS = 3_000

#: The address space a run may use. Frames are small, so this is far more than a
#: normal run needs and is only ever reached by something wrong.
MEMORY_LIMIT_MB = 256

#: How many algorithms one comparison may put side by side. Two is the minimum that
#: makes a comparison; a handful is the most that is still readable in a row on a
#: laptop.
MIN_COMPARISON_SIDES = 2
MAX_COMPARISON_SIDES = 4

#: How many repetitions of the *same* input one side runs, for timing. A single run
#: of a reference implementation on a handful of elements is dominated by process
#: start-up, so measuring one of them and printing the number would be reporting a
#: scheduling artefact as an algorithm property. Repetitions inside one process make
#: the figure mean something, and the median is reported because the first
#: repetition pays import and allocation costs the rest do not.
MIN_REPETITIONS = 1
MAX_REPETITIONS = 25
DEFAULT_REPETITIONS = 5


@dataclass(frozen=True)
class VisualizationLimits:
    """The resolved budget for one run.

    Frozen because the limits are decided once, before anything runs, and a limit
    that could change mid-run would be a limit that cannot be enforced.
    """

    wall_clock_ms: int = DEFAULT_WALL_CLOCK_MS
    memory_mb: int = MEMORY_LIMIT_MB
    cpu_seconds: int = DEFAULT_WALL_CLOCK_MS // 1000 + 1
    max_frames: int = MAX_FRAMES
    repetitions: int = DEFAULT_REPETITIONS

    @classmethod
    def resolve(
        cls,
        wall_clock_ms: int | None = None,
        max_frames: int | None = None,
        repetitions: int | None = None,
    ) -> "VisualizationLimits":
        """Clamp whatever the caller asked for into the range this platform honours.

        Each value is clamped rather than rejected. A caller asking for fewer frames
        than the floor gets the floor, because a floor that could be violated would
        not be a floor.
        """
        clock = _clamp_int(
            wall_clock_ms, default=DEFAULT_WALL_CLOCK_MS, low=MIN_WALL_CLOCK_MS, high=30_000
        )
        return cls(
            wall_clock_ms=clock,
            memory_mb=MEMORY_LIMIT_MB,
            cpu_seconds=clock // 1000 + 1,
            max_frames=_clamp_int(max_frames, default=MAX_FRAMES, low=1, high=MAX_FRAMES),
            repetitions=_clamp_int(
                repetitions, default=DEFAULT_REPETITIONS, low=MIN_REPETITIONS, high=MAX_REPETITIONS
            ),
        )


def _clamp_int(value: object, *, default: int, low: int, high: int) -> int:
    """Coerce a possibly-missing, possibly-nonsense request value into a range.

    Same rule as the judge's: unreadable input falls back to the documented default
    rather than failing the request. Being asked to show a visualization is not the
    moment to reject a request over one odd field.
    """
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        coerced = default
    return max(low, min(coerced, high))


__all__ = [
    "DEFAULT_REPETITIONS",
    "DEFAULT_WALL_CLOCK_MS",
    "MAX_COMPARISON_SIDES",
    "MAX_FRAMES",
    "MAX_INPUT_BYTES",
    "MAX_REPETITIONS",
    "MEMORY_LIMIT_MB",
    "MIN_COMPARISON_SIDES",
    "MIN_REPETITIONS",
    "MIN_WALL_CLOCK_MS",
    "WORKER_GRACE_MS",
    "VisualizationLimits",
]
