"""Parent-side supervision of one sandboxed run.

This module is the boundary the rest of the application talks to. It never
imports a learner's program and never runs one itself: it starts a worker
process, hands it one case, supervises it, and parses the result document back.

The worker is given its own wall clock to kill the program, and this module is
given a *second, larger* one to kill the worker. Both are needed. A single
supervisor is not enough because the failure being defended against is not only
"the program loops forever" -- it is also "the worker itself wedges", which is
what a request that never returns looks like from the outside.

Nothing here trusts the worker's result beyond its shape. A result document is
parsed defensively and a document that cannot be read becomes an
``internal_error`` rather than a pass.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.judge.languages import LanguageSpec, LanguageUnavailableError
from backend.app.judge.limits import WORKER_GRACE_MS, ExecutionLimits
from backend.app.judge.worker import RESULT_SENTINEL, WORKER_PASSTHROUGH_ENV

#: The worker script, invoked by path. It is deliberately *not* started as
#: ``-m backend.app.judge.worker``: that would require the repository on the
#: worker's import path, and the whole point of ``python -I`` is that the
#: repository is not importable from inside a run.
WORKER_PATH = Path(__file__).with_name("worker.py")


class ExecutionError(RuntimeError):
    """A run could not be completed or its result could not be read.

    Distinct from a program that ran and answered wrongly: this is the platform
    failing, and callers must not report it as the learner's mistake.
    """


@dataclass(frozen=True)
class RunOutcome:
    """What one execution of one program did.

    ``kind`` is the raw observation, deliberately not a verdict:
    ``ok``, ``nonzero_exit``, ``time_limit``, ``output_limit``,
    ``killed_by_signal``, ``compile_error`` or ``internal_error``. Turning an
    observation into a verdict is :mod:`backend.app.judge.judge`'s job, because
    only the judge knows the expected output. ``compile_error`` is the one kind
    that describes building a program rather than running one; it is what a
    compiled language's build step reports, and the judge maps it to the same
    verdict an interpreter's refusal of the source already produced.
    """

    kind: str
    exit_code: int | None
    signal: int | None
    stdout: str
    stderr: str
    duration_ms: int
    peak_memory_mb: float | None
    error: str | None = None

    @property
    def ran_cleanly(self) -> bool:
        """Whether the program started, finished, and exited zero."""
        return self.kind == "ok"

    @property
    def timed_out(self) -> bool:
        return self.kind == "time_limit"


def _worker_argv() -> list[str]:
    """The command line that starts a worker.

    ``-I`` is isolated mode and ``-B`` suppresses bytecode writes. Isolated mode
    is the load-bearing one: it ignores ``PYTHONPATH``, ``PYTHONHOME`` and the
    user site directory, so the only importable thing is the standard library.
    """
    if not WORKER_PATH.is_file():  # pragma: no cover - only if the package is broken
        raise ExecutionError("The judge worker script is missing from the installation.")
    return [sys.executable, "-I", "-B", str(WORKER_PATH)]


def _worker_env() -> dict[str, str]:
    """The environment the worker process itself is started with.

    This is an allow-list, never ``os.environ.copy()``, because the worker is one
    hop from a submitted program: whatever is put here is read back out by
    :func:`backend.app.judge.worker._sandbox_env` and handed to the learner's
    code. ``JWT_SECRET_KEY``, ``DATABASE_URL`` and the rest of the deployment's
    configuration are therefore absent by construction rather than by a filter
    somebody has to remember to keep.

    The list is the worker's own :data:`WORKER_PASSTHROUGH_ENV`, imported rather
    than repeated, so the parent cannot hand down a variable the worker will not
    forward -- and, more importantly, the worker can no longer fail to *see* one
    it promises to forward. The previous two-variable environment
    (``PATH``/``SYSTEMROOT``) meant ``TEMP`` and ``TMP`` were absent from every
    worker on Windows, so the sandboxed program ran with no temp directory at
    all: ``java.io.tmpdir`` fell back to ``C:\\Windows\\`` and every JVM start --
    each case's run *and* every ``javac`` -- spent about 1.4 seconds in directory
    and access checks before the program's first line. That single missing pair
    of variables was most of the cost of judging a Java submission.

    ``PATH`` and ``SystemRoot`` are guaranteed rather than merely inherited: a
    worker with no ``PATH`` cannot start an interpreter that is found by name,
    and Windows refuses to initialise a great many APIs without ``SystemRoot``.
    """
    env: dict[str, str] = {}
    for name in WORKER_PASSTHROUGH_ENV:
        value = os.environ.get(name)
        if value:
            env[name] = value
    env.setdefault("PATH", os.environ.get("PATH", ""))
    if not any(key.lower() == "systemroot" for key in env):
        # Last resort rather than a plausible-looking guess: an empty SystemRoot
        # is worse than none, because Windows then reports a confusing failure
        # instead of one that names the variable.
        fallback = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT")
        if not fallback and os.name == "nt":  # pragma: no cover - Windows fallback
            fallback = r"C:\Windows"
        if fallback:
            env["SystemRoot"] = fallback
    return env


def _build_job(
    language: LanguageSpec,
    source_code: str,
    stdin_text: str,
    limits: ExecutionLimits,
    *,
    mode: str,
    argv_prefix: list[str],
    append_entry: bool,
) -> dict[str, Any]:
    """Describe one job to the worker.

    Note what is absent: the expected output, and every other case. The worker
    cannot compare, and cannot be told the answer, because it is never given it.

    Both compile budgets travel in every job, whichever mode it is, so the worker
    reads one shape and never has to know which limits apply. ``append_entry`` is
    the other field that keeps the worker ignorant of languages: it says whether
    the source path belongs at the end of this command line, which is a question
    about the language that the language registry has already answered.
    """
    return {
        "language": language.id,
        "mode": mode,
        "source": source_code,
        "stdin": stdin_text,
        "entry_name": language.entry_name(),
        "argv_prefix": argv_prefix,
        "append_entry": append_entry,
        "wall_clock_ms": limits.wall_clock_ms,
        "memory_mb": limits.memory_mb,
        "cpu_seconds": limits.cpu_seconds,
        "max_output_bytes": limits.max_output_bytes,
        "compile_wall_clock_ms": limits.compile_wall_clock_ms,
        "compile_max_output_bytes": limits.compile_max_output_bytes,
        "enforce_address_space": language.enforce_address_space,
    }


def _parse_result(stdout: str) -> dict[str, Any] | None:
    """Read the result document out of the worker's stdout.

    Returns ``None`` when there is no readable document, which the caller turns
    into an ``internal_error``. A missing result is never treated as success: the
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


def _coerce_result(document: dict[str, Any]) -> RunOutcome:
    """Read a result document defensively.

    The worker is trusted, but a partially written or truncated document is still
    possible, and reading a field that is not there must not become a 500 on the
    learner's request.
    """
    def text(name: str) -> str:
        value = document.get(name)
        return value if isinstance(value, str) else ""

    def number(name: str) -> int | None:
        value = document.get(name)
        return value if isinstance(value, int) else None

    def measurement(name: str) -> float | None:
        value = document.get(name)
        return float(value) if isinstance(value, (int, float)) else None

    error = document.get("error")
    return RunOutcome(
        kind=str(document.get("kind") or "internal_error"),
        exit_code=number("exit_code"),
        signal=number("signal"),
        stdout=text("stdout"),
        stderr=text("stderr"),
        duration_ms=number("duration_ms") or 0,
        peak_memory_mb=measurement("peak_memory_mb"),
        error=error if isinstance(error, str) else None,
    )


def _drain(stream, sink: list[bytes], cap: int) -> None:
    """Read a pipe to EOF, keeping at most ``cap`` bytes.

    The worker's stdout is the result channel, so it is normally a single short
    document. The cap is here for the case where it is not: a worker that
    misbehaves must not be able to exhaust the API process's memory.
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


def execute(
    language: LanguageSpec,
    source_code: str,
    stdin_text: str,
    limits: ExecutionLimits,
    *,
    classpath: str | None = None,
) -> RunOutcome:
    """Run one program against one input, out of process, and report what happened.

    ``classpath`` is the directory a previous :func:`compile_source` filled. It is
    ignored by an interpreted language, and required by a compiled one, which has
    nothing to start from without it.

    Raises :class:`LanguageUnavailableError` when the machine has no interpreter
    for the language, because that is a deployment problem the caller should turn
    into a 503 rather than into a verdict about the learner's code.
    """
    if not language.available:
        raise LanguageUnavailableError(language.id)

    job = _build_job(
        language,
        source_code,
        stdin_text,
        limits,
        mode="run",
        argv_prefix=language.run_command(classpath),
        append_entry=language.appends_entry_path,
    )
    return _run_worker(job, parent_budget_ms=limits.wall_clock_ms)


def compile_source(
    language: LanguageSpec,
    source_code: str,
    limits: ExecutionLimits,
    output_dir: str,
) -> RunOutcome:
    """Build one submission into ``output_dir``.

    Separate from :func:`execute` because the cost is different in kind, not just
    in size: this runs once per submission and its clock is
    :attr:`~backend.app.judge.limits.ExecutionLimits.compile_wall_clock_ms`, so a
    JVM's start-up is never charged to the per-case time limit the program is
    judged against. ``output_dir`` is created and removed by the caller, which is
    what lets one build serve every case of a submission.
    """
    if not language.available or not language.needs_compile:
        raise LanguageUnavailableError(language.id)

    job = _build_job(
        language,
        source_code,
        "",
        limits,
        mode="compile",
        argv_prefix=language.compile_command(output_dir),
        append_entry=True,
    )
    return _run_worker(job, parent_budget_ms=limits.compile_wall_clock_ms)


def execute_once(
    language: LanguageSpec,
    source_code: str,
    stdin_text: str,
    limits: ExecutionLimits,
) -> RunOutcome:
    """Run one program once, compiling it first if its language needs that.

    The single-run paths -- the ad-hoc "try my own input" and the run-only
    endpoint -- have exactly one execution to pay for, so the build is created and
    discarded around it here. The judge does not use this: it has many cases per
    submission and must compile once for all of them.
    """
    if not language.available:
        raise LanguageUnavailableError(language.id)
    if not language.needs_compile:
        return execute(language, source_code, stdin_text, limits)

    build_dir = tempfile.mkdtemp(prefix="algotwin-build-")
    try:
        outcome = compile_source(language, source_code, limits, build_dir)
        if outcome.kind != "ok":
            return outcome
        return execute(language, source_code, stdin_text, limits, classpath=build_dir)
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def _run_worker(job: dict[str, Any], *, parent_budget_ms: int) -> RunOutcome:
    """Hand one job to a fresh worker and read its result document back.

    ``parent_budget_ms`` is the clock this process is given to kill the *worker*,
    and it is passed separately from the job's own limit because the two differ
    for a compile: the worker is told to stop a long compilation at the compile
    clock, while this process waits slightly longer than that before concluding
    the worker itself is wedged.
    """
    process: subprocess.Popen
    try:
        process = subprocess.Popen(
            _worker_argv(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=_worker_env(),
            close_fds=True,
            **_new_process_group(),
        )
    except OSError as error:
        raise ExecutionError(f"Could not start the judge worker: {error}") from error

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    readers = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_chunks, 8 * 1024 * 1024), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr_chunks, 256 * 1024), daemon=True),
    ]
    for reader in readers:
        reader.start()

    try:
        process.stdin.write(json.dumps(job).encode("utf-8"))
        process.stdin.close()
    except (BrokenPipeError, OSError, ValueError) as error:
        _terminate(process)
        raise ExecutionError(f"Could not hand the case to the judge worker: {error}") from error

    budget = (parent_budget_ms + WORKER_GRACE_MS) / 1000
    try:
        process.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        # The worker did not come back inside its own budget plus the grace
        # period. Its own supervision is what should have killed the program, so
        # reaching here means the worker, not the program, is the problem.
        _terminate(process)
        for reader in readers:
            reader.join(timeout=5)
        return RunOutcome(
            kind="internal_error",
            exit_code=None,
            signal=None,
            stdout="",
            stderr="",
            duration_ms=int(budget * 1000),
            peak_memory_mb=None,
            error="The judge worker did not respond and was stopped.",
        )

    for reader in readers:
        reader.join(timeout=5)

    document = _parse_result(b"".join(stdout_chunks).decode("utf-8", errors="replace"))
    if document is None:
        diagnostics = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
        return RunOutcome(
            kind="internal_error",
            exit_code=process.returncode,
            signal=None,
            stdout="",
            stderr=diagnostics[:2000],
            duration_ms=0,
            peak_memory_mb=None,
            error="The judge worker produced no readable result.",
        )
    return _coerce_result(document)


def _new_process_group() -> dict[str, Any]:
    """Put the worker in its own process group or session.

    Without this, stopping the worker leaves the program it started running, and
    one abandoned run becomes a process nobody is supervising.
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


__all__ = [
    "ExecutionError",
    "RunOutcome",
    "WORKER_PATH",
    "compile_source",
    "execute",
    "execute_once",
]
