"""Parent-side supervision of one visualization or comparison run.

This module is the boundary the rest of the application talks to. It never imports
a frame-emitting algorithm and never runs one itself: it starts a worker process,
hands it one job, supervises it, and parses the result document back.

The shape deliberately mirrors :mod:`backend.app.judge.runner`, because it solves
the same problem for the same reason. A reference algorithm is a generator, and a
generator with a bug in it will loop forever inside the API process. So the worker
gets its own wall clock, and this module gets a *second, larger* one to kill the
worker -- the failure being defended against is not only "the algorithm loops" but
also "the worker itself wedges", which is what a request that never returns looks
like from the outside.

Nothing here trusts the worker's result beyond its shape. A result document is
parsed defensively, and a document that cannot be read becomes an ``internal_error``
rather than a run with zero frames.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.visualization.limits import MAX_INPUT_BYTES, WORKER_GRACE_MS, VisualizationLimits
from backend.app.visualization.worker import RESULT_SENTINEL

#: The worker script, invoked by path.
WORKER_PATH = Path(__file__).with_name("worker.py")


class VisualizationError(RuntimeError):
    """A run could not be completed or its result could not be read.

    Distinct from an algorithm that ran and finished badly: this is the platform
    failing, and callers must not report it as a problem with the learner's input.
    """


@dataclass(frozen=True)
class RunOutcome:
    """What one execution of one reference implementation did.

    ``kind`` is the raw observation, never a verdict: ``ok``, ``invalid_request``,
    ``resource_limit``, ``time_limit`` or ``internal_error``. ``metrics`` are the
    operation counts the algorithm itself recorded, so they describe the work done
    whether or not anybody is watching.
    """

    kind: str
    frames: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, int] = field(default_factory=dict)
    result: str | None = None
    truncated: bool = False
    #: The median of the in-process repetitions, when this was a measurement run.
    runtime_ms: float | None = None
    repetitions: int | None = None
    samples_ms: tuple[float, ...] = ()
    frame_count: int | None = None
    duration_ms: float = 0.0
    #: ``None`` where the platform cannot measure it, which the frontend renders as
    #: "Not measured" rather than as zero.
    peak_memory_mb: float | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Whether the algorithm ran and produced frames."""
        return self.kind == "ok"

    @property
    def was_measured(self) -> bool:
        """Whether a real runtime figure came back, as opposed to no figure at all."""
        return self.runtime_ms is not None


def _worker_argv() -> list[str]:
    """The command line that starts a worker.

    Unlike the judge worker this one is *not* started with ``-I``: it needs to import
    the platform's own reference implementations, which is the whole point of it.
    ``-B`` still suppresses bytecode writes so a run leaves no ``__pycache__``
    behind, and ``-E`` drops inherited environment settings so a stray
    ``PYTHONOPTIMIZE`` in the operator's shell cannot change how an algorithm is
    measured.
    """
    if not WORKER_PATH.is_file():  # pragma: no cover - only if the package is broken
        raise VisualizationError("The visualization worker script is missing from the installation.")
    return [sys.executable, "-E", "-B", str(WORKER_PATH)]


def _build_job(
    algorithm_id: str,
    input_text: str,
    limits: VisualizationLimits,
    mode: str,
) -> dict[str, Any]:
    """Describe one job to the worker.

    Note what is absent: any other algorithm, any other input, and any expected
    answer. A comparison gets one worker per side, each handed only that side's own
    identifier and the *same* input bytes, so a side cannot accidentally be given a
    different problem or told what the answer should be.
    """
    return {
        "mode": mode,
        "algorithm_id": algorithm_id,
        "input": input_text,
        "max_frames": limits.max_frames,
        "max_input_bytes": MAX_INPUT_BYTES,
        "wall_clock_ms": limits.wall_clock_ms,
        "memory_mb": limits.memory_mb,
        "cpu_seconds": limits.cpu_seconds,
        "repetitions": limits.repetitions,
    }


def _parse_result(stdout: str) -> dict[str, Any] | None:
    """Read the result document out of the worker's stdout.

    Returns ``None`` when there is no readable document, which the caller turns into
    an ``internal_error``. A missing result is never treated as an empty run: the
    only honest answer to "the worker said nothing" is that the platform does not
    know.
    """
    marker = stdout.rfind(RESULT_SENTINEL)
    if marker == -1:
        return None
    try:
        document = json.loads(stdout[marker + len(RESULT_SENTINEL) :])
    except ValueError:
        return None
    if not isinstance(document, dict) or "kind" not in document:
        return None
    return document


def _text(document: dict[str, Any], name: str) -> str:
    value = document.get(name)
    return value if isinstance(value, str) else ""


def _number(document: dict[str, Any], name: str) -> float | None:
    value = document.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _frames(document: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Read the collected frames defensively, keeping only well-formed states.

    The worker is trusted, but a truncated or hand-edited document must not become a
    500 on somebody's request, and a frame without a layout kind is not something
    the renderer can draw.
    """
    raw = document.get("frames")
    if not isinstance(raw, list):
        return ()
    kept: list[dict[str, Any]] = []
    for state in raw:
        if isinstance(state, dict) and isinstance(state.get("kind"), str):
            kept.append(state)
    return tuple(kept)


def _metrics(document: dict[str, Any]) -> dict[str, int]:
    """Read the operation counters defensively."""
    raw = document.get("metrics")
    if not isinstance(raw, dict):
        return {}
    return {
        str(name): int(value)
        for name, value in raw.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def _count(document: dict[str, Any], name: str) -> int | None:
    """Read one optional integer count, or ``None`` if it is absent or nonsense."""
    value = _number(document, name)
    return None if value is None else int(value)


def _coerce(document: dict[str, Any]) -> RunOutcome:
    """Turn a result document into a :class:`RunOutcome`."""
    error = document.get("error")
    return RunOutcome(
        kind=_text(document, "kind") or "internal_error",
        frames=_frames(document),
        metrics=_metrics(document),
        result=_text(document, "result") or None,
        truncated=bool(document.get("truncated")),
        runtime_ms=_number(document, "runtime_ms"),
        repetitions=_count(document, "repetitions"),
        samples_ms=tuple(
            float(sample)
            for sample in (document.get("samples_ms") or [])
            if isinstance(sample, (int, float)) and not isinstance(sample, bool)
        ),
        frame_count=_count(document, "frame_count"),
        duration_ms=_number(document, "duration_ms") or 0.0,
        peak_memory_mb=_number(document, "peak_memory_mb"),
        error=error if isinstance(error, str) else None,
    )


def _drain(stream: Any, sink: list[bytes], cap: int) -> None:
    """Read a pipe to EOF, keeping at most ``cap`` bytes.

    The cap is here for the case where the payload is not the single short document
    it should be: a worker that misbehaves must not be able to exhaust the API
    process's memory.
    """
    total = 0
    try:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total <= cap:
                sink.append(chunk)
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _new_process_group() -> dict[str, Any]:
    """Put the worker in its own process group or session.

    Without this, stopping the worker leaves the algorithm it was running behind,
    and one abandoned run becomes a process nobody is supervising.
    """
    if os.name == "nt":  # pragma: no cover - Windows-specific
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}  # pragma: no cover - POSIX-specific


def _terminate(process: subprocess.Popen) -> None:
    """Stop a worker and everything below it."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":  # pragma: no cover - Windows-specific
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        else:
            import signal

            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            process.kill()
        except OSError:
            pass


def execute(
    algorithm_id: str,
    input_text: str,
    limits: VisualizationLimits,
    mode: str = "run",
) -> RunOutcome:
    """Run one reference implementation over one input, out of process.

    ``mode`` is ``run`` for a timeline or ``measure`` for a timed comparison side.
    Both are the same supervision; the difference is only whether the frames are
    kept or discarded, which is a question the worker answers, not this one.
    """
    if mode not in {"run", "measure"}:
        raise VisualizationError(f"{mode!r} is not a visualization mode.")

    job = _build_job(algorithm_id, input_text, limits, mode)
    try:
        process = subprocess.Popen(
            _worker_argv(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env={
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            },
            close_fds=True,
            **_new_process_group(),
        )
    except OSError as error:
        raise VisualizationError(f"Could not start the visualization worker: {error}") from error

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    readers = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_chunks, 16 * 1024 * 1024), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr_chunks, 256 * 1024), daemon=True),
    ]
    for reader in readers:
        reader.start()

    try:
        process.stdin.write(json.dumps(job).encode("utf-8"))
        process.stdin.close()
    except (BrokenPipeError, OSError, ValueError) as error:
        _terminate(process)
        raise VisualizationError(f"Could not hand the job to the visualization worker: {error}") from error

    budget = (limits.wall_clock_ms + WORKER_GRACE_MS) / 1000
    try:
        process.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        # The worker did not come back inside its own budget plus the grace period.
        # Its own supervision is what should have stopped the algorithm, so reaching
        # here means the worker, not the algorithm, is the problem.
        _terminate(process)
        for reader in readers:
            reader.join(timeout=5)
        return RunOutcome(
            kind="internal_error",
            duration_ms=budget * 1000,
            error="The visualization worker did not respond and was stopped.",
        )

    for reader in readers:
        reader.join(timeout=5)

    document = _parse_result(b"".join(stdout_chunks).decode("utf-8", errors="replace"))
    if document is None:
        # The worker's diagnostics are more useful than the generic message when it
        # printed some, so they ride along on the error rather than being dropped.
        diagnostics = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
        return RunOutcome(
            kind="internal_error",
            error=diagnostics[:500] or "The visualization worker produced no readable result.",
        )
    return _coerce(document)


__all__ = [
    "WORKER_PATH",
    "RunOutcome",
    "VisualizationError",
    "execute",
]
