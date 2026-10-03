"""Child-side execution of one platform reference implementation.

Started by :mod:`backend.app.visualization.runner`, never imported by the API
process. It reads one job document from stdin, runs one of the platform's own
frame-emitting algorithms, and writes one result document to stdout.

This is trusted code -- unlike :mod:`backend.app.judge.worker`, the algorithm is
the platform's, not a learner's -- so it *does* import the registry rather than
being isolated to the standard library. It is still a separate process for the two
reasons that matter:

* A frame-emitting algorithm is a generator. If one of them has a bug and loops,
  the loop happens in a process the parent can kill, and the API process keeps
  serving requests.
* The parent measures wall clock and peak memory around the whole run. Measuring
  the API process would report the memory of the whole web server, which is not a
  property of the algorithm.

Two different jobs share this worker because both need the same supervision and
the same counters:

``run``
    Collect the frames and stop at the frame ceiling, so a visualization gets a
    timeline.
``measure``
    Discard the frames and time repeated runs in-process, so a comparison reports a
    figure that is about the algorithm rather than about process start-up.

Both report ``peak_memory_mb`` only when they can actually measure it. On Windows
``getrusage`` is not available, so the field is absent rather than ``0`` -- and an
absent measurement is rendered as "Not measured", not as zero bytes.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

#: The worker is started by path, so ``sys.path[0]`` is this file's directory and
#: the repository root is not importable. Put it back explicitly: this process runs
#: the platform's own algorithms, so unlike the judge worker it *wants* them.
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Marks the start of the result document on stdout, so a stray ``print`` from any
#: imported module cannot be mistaken for the answer.
RESULT_SENTINEL = "@@ALGOTWIN_VISUALIZATION@@"


class _JobError(Exception):
    """The job document was unusable, so there is nothing to run.

    Reported as its own outcome kind rather than as a crash: "you asked to
    visualize an algorithm this platform does not have" is a fact about the
    request, not a malfunction.
    """


def _load_registry() -> Any:
    from backend.app.algorithms.registry import get_algorithm

    return get_algorithm


def _apply_limits(job: dict[str, Any]) -> None:  # pragma: no cover - POSIX only
    """Cap this process's CPU time and address space before running anything.

    ``resource`` is imported inside the function because it does not exist on
    Windows, and a visualization must work there too. Where the limits cannot be
    set the run proceeds: the parent's wall clock is a second, independent guard,
    which is the entire reason there are two.
    """
    try:
        import resource
    except ImportError:
        return
    cpu_seconds = int(job.get("cpu_seconds") or 0)
    memory_mb = int(job.get("memory_mb") or 0)
    if cpu_seconds > 0:
        _set_limit(resource, resource.RLIMIT_CPU, cpu_seconds)
    if memory_mb > 0:
        _set_limit(resource, resource.RLIMIT_AS, memory_mb * 1024 * 1024)


def _set_limit(resource: Any, which: int, value: int) -> None:  # pragma: no cover - POSIX only
    """Set one soft limit, and the hard limit with it.

    Setting only the soft limit leaves the process free to raise it back up, which
    would make the cap decorative.
    """
    try:
        current_hard = resource.getrlimit(which)[1]
        hard = value if current_hard == resource.RLIM_INFINITY else min(value, current_hard)
        resource.setrlimit(which, (value, hard))
    except (OSError, ValueError):
        pass


def _measure_peak_memory_mb() -> float | None:
    """The peak resident memory of this process, or ``None`` where unavailable.

    ``getrusage``'s ``ru_maxrss`` is kilobytes on Linux and *bytes* on macOS, so
    the unit is normalised by platform rather than assumed. Windows has no
    ``getrusage`` at all, and the honest answer there is "we did not measure it" --
    which the frontend renders as "Not measured" rather than as zero.
    """
    try:
        import resource
    except ImportError:
        return None
    try:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (OSError, ValueError):
        return None
    divisor = (1024 * 1024) if sys.platform == "darwin" else 1024
    return round(peak / divisor, 3)


def _resolve(job: dict[str, Any]) -> tuple[Any, Any]:
    """Look up the algorithm and read its input.

    Raises :class:`_JobError` for anything the caller got wrong -- unknown
    algorithm, oversized input, input the grammar rejects -- so the parent can
    report it as a 404 or a 422 instead of a 500.
    """
    from backend.app.algorithms.inputs import InvalidInputError

    algorithm_id = job.get("algorithm_id")
    if not isinstance(algorithm_id, str) or not algorithm_id:
        raise _JobError("No algorithm was named.")
    descriptor = _load_registry()(algorithm_id)
    if descriptor is None:
        raise _JobError(f"{algorithm_id!r} is not an algorithm this platform can run.")

    raw_input = job.get("input")
    if not isinstance(raw_input, str):
        raise _JobError("No input was supplied.")
    if len(raw_input.encode("utf-8")) > int(job.get("max_input_bytes") or 0):
        raise _JobError("The input is larger than this platform accepts for a visualization.")
    try:
        case = descriptor.parse_input(raw_input)
    except InvalidInputError as error:
        raise _JobError(str(error)) from error
    return descriptor, case


def _frames_for(descriptor: Any, case: Any, max_frames: int) -> tuple[list[dict[str, Any]], bool, str | None, dict[str, int]]:
    """Collect the frames of one run, stopping at the ceiling.

    Returns the collected states, whether the ceiling cut the run short, the final
    result, and the counters. The counters come from the :class:`Trace`, which the
    algorithm wrote them into as it went, so they are the real operations performed
    rather than anything inferred from the frames.

    The ceiling is applied by stopping iteration rather than by discarding frames
    afterwards, and the last kept frame is re-emitted with ``truncated`` status.
    That last frame is still a state the algorithm was really in -- the only thing
    changed is that the platform is saying "and then we stopped looking".
    """
    from backend.app.algorithms.frames import STATUS_TRUNCATED

    trace = descriptor.trace()
    collected: list[dict[str, Any]] = []
    truncated = False
    result: str | None = None
    generator = descriptor.implementation(case, trace)
    while True:
        try:
            state = next(generator)
        except StopIteration:
            break
        if len(collected) >= max_frames:
            truncated = True
            generator.close()
            break
        collected.append(state.to_dict())
        result = state.result or result
    if truncated and collected:
        last = dict(collected[-1])
        last["status"] = STATUS_TRUNCATED
        collected[-1] = last
    return collected, truncated, result, trace.metrics


def _job_run(descriptor: Any, case: Any, job: dict[str, Any]) -> dict[str, Any]:
    max_frames = max(1, int(job.get("max_frames") or 1))
    states, truncated, result, metrics = _frames_for(descriptor, case, max_frames)
    return {
        "frames": states,
        "metrics": metrics,
        "result": result,
        "truncated": truncated,
    }


def _job_measure(descriptor: Any, case: Any, job: dict[str, Any]) -> dict[str, Any]:
    """Time repeated runs of the same input, in this process.

    Deliberately times the same work the visualization performs, with the frames
    consumed and discarded, and reports the *median* of the repetitions. The first
    repetition pays for allocations and branch-prediction warm-up that the rest do
    not, and a comparison that reports the first repetition is reporting the
    measurement apparatus rather than the algorithm.

    Timing is ``perf_counter`` around the run, which is the only figure here that is
    genuinely measured. No operation counts are synthesised from it, and no
    complexity is inferred: the asymptotic claims on a card come from the registry,
    where a human put them.
    """
    repetitions = max(1, int(job.get("repetitions") or 1))
    samples_ms: list[float] = []
    frame_count: int | None = None
    metrics: dict[str, int] = {}
    result: str | None = None
    max_frames = max(1, int(job.get("max_frames") or 1))

    for _ in range(repetitions):
        started = time.perf_counter()
        states, truncated, outcome, counted = _frames_for(descriptor, case, max_frames)
        samples_ms.append((time.perf_counter() - started) * 1000)
        if frame_count is None:
            frame_count = len(states)
        metrics = counted
        result = outcome if outcome is not None else result
        del states, truncated

    samples_ms.sort()
    middle = len(samples_ms) // 2
    median_ms = (
        samples_ms[middle]
        if len(samples_ms) % 2
        else (samples_ms[middle - 1] + samples_ms[middle]) / 2
    )
    return {
        "runtime_ms": round(median_ms, 4),
        "repetitions": repetitions,
        "samples_ms": [round(sample, 4) for sample in samples_ms],
        "frame_count": frame_count,
        "metrics": metrics,
        "result": result,
    }


def main() -> int:
    """Read one job, run it, and write exactly one result document."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return 1
    try:
        job = json.loads(raw) if raw.strip() else {}
    except ValueError:
        job = {}

    started = time.perf_counter()
    try:
        if not isinstance(job, dict):
            raise _JobError("The job document was not an object.")
        mode = job.get("mode", "run")
        if mode not in {"run", "measure"}:
            raise _JobError(f"{mode!r} is not a visualization mode.")
        _apply_limits(job)
        descriptor, case = _resolve(job)
        payload = _job_run(descriptor, case, job) if mode == "run" else _job_measure(descriptor, case, job)
        document: dict[str, Any] = {"kind": "ok", **payload}
    except _JobError as error:
        document = {"kind": "invalid_request", "error": str(error)}
    except RecursionError:
        # A grid or a string large enough to exhaust the stack is a real possibility
        # once inputs are user-supplied, and the useful answer names the cause rather
        # than dumping a traceback at a learner.
        document = {"kind": "resource_limit", "error": "This input is too large to trace."}
    except MemoryError:
        document = {"kind": "resource_limit", "error": "This input needs more memory than a run may use."}
    except Exception as error:  # noqa: BLE001 - the parent turns this into a 500, not a verdict
        document = {"kind": "internal_error", "error": f"{type(error).__name__}: {error}"}

    document["duration_ms"] = round((time.perf_counter() - started) * 1000, 4)
    document["peak_memory_mb"] = _measure_peak_memory_mb()
    sys.stdout.write(RESULT_SENTINEL + json.dumps(document, sort_keys=True))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RESULT_SENTINEL", "main"]
