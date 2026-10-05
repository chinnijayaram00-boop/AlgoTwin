"""The worker process: the only place a learner's program is ever executed.

This file is deliberately **self-contained**. It imports nothing from AlgoTwin and
nothing outside the standard library, because it is started with ``python -I``,
which puts only *this file's own directory* on ``sys.path``. A submitted program
therefore cannot import the application's settings module, read the database URL,
or reach the JWT secret, no matter what it does to the filesystem it can see.

Protocol
--------

* The parent writes one JSON job to this process's **stdin**, then that stream is
  consumed and closed. The program the worker starts gets a *different* pipe, so
  a learner's program cannot read the job, the source, or anything else the parent
  sent.
* The worker writes one JSON result to **stdout**, wrapped in a sentinel line. The
  program's own stdout and stderr are captured by the worker and never reach this
  process's stdout, so the result channel carries nothing a program can forge.
* The exit code of this process is always ``0``. The verdict lives in the result
  document; an exit code would conflate "the program failed" with "the worker
  failed", and the parent needs to tell those apart.
* Everything else -- unexpected exceptions included -- is reported as an
  ``internal_error`` result. A worker that crashed with no output would be
  indistinguishable from a worker that hung, and the parent would wait out the
  full grace period for nothing.

What the worker is told, and what it is deliberately not told
------------------------------------------------------------

The job carries the source, the case's stdin, the interpreter command line, and
the limits. It does **not** carry the expected output for the case, nor any other
case. Comparison happens in the parent process, which is the only holder of the
hidden cases and their answers, so no amount of cleverness inside the sandbox can
read what the program is supposed to print.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

#: Written on its own line before the result JSON. Parsing looks for this rather
#: than assuming the whole of stdout is the document, so a stray runtime banner
#: on this process's stdout cannot turn a run into a parse error.
RESULT_SENTINEL = "__ALGOTWIN_JUDGE_RESULT__"

#: Read granularity when draining a program's output. Small enough that the cap
#: is honoured closely, large enough not to spin.
_DRAIN_CHUNK = 64 * 1024

#: Environment variables handed to the learner's program. Everything else the
#: parent has -- including anything a developer exported for their own session --
#: is dropped, so the program cannot read configuration it was not given.
_PASSTHROUGH_ENV = ("PATH", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP", "SystemRoot", "COMSPEC", "PATHEXT")

#: A minimal `PATH` for the program itself. The interpreter is started by absolute
#: path, so this is not needed to run the program; it is here so a program that
#: shells out to something ordinary does not fail for an unrelated reason.
_MINIMAL_PATH = (
    os.pathsep.join(
        part
        for part in (
            r"C:\Windows\System32",
            r"C:\Windows",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
        )
    )
    + os.pathsep
)


def _sandbox_env(interpreter_dir: str) -> dict[str, str]:
    """The environment a submitted program is started with.

    ``SystemRoot`` is kept even though it is a Windows implementation detail: a
    great many Windows APIs refuse to initialise without it, and dropping it would
    make every program fail with a confusing error instead of a real one.
    """
    env: dict[str, str] = {}
    for name in _PASSTHROUGH_ENV:
        value = os.environ.get(name)
        if value:
            env[name] = value
    env["PATH"] = _MINIMAL_PATH + interpreter_dir
    # Bytecode writing is off for the same reason `-B` is passed to CPython, and
    # a program that prints without stopping should hit the output cap rather than
    # filling the sandbox directory first.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # `NODE_OPTIONS` is dropped deliberately rather than sanitised: it is the
    # documented way to make a Node process load arbitrary code before the
    # program's first line, and inheriting one would be a sandbox escape.
    env.pop("NODE_OPTIONS", None)
    env.pop("PYTHONSTARTUP", None)
    env.pop("PYTHONPATH", None)
    return env


def _address_space_limit(memory_mb: int, cpu_seconds: int):  # pragma: no cover - POSIX only
    """Build the ``preexec_fn`` that caps CPU, address space, and file size.

    Only ever called on POSIX. ``RLIMIT_AS`` is what turns an allocation loop
    into a ``MemoryError`` instead of a machine that stops responding, and
    ``RLIMIT_FSIZE`` is what stops a program that writes a file from filling the
    disk before the wall clock catches it. ``RLIMIT_CPU`` is the backstop for a
    program that spins without allocating, and it is passed in rather than assumed
    so that the number the parent reports as this run's CPU allowance is the
    number the kernel is actually enforcing.
    """
    import resource

    address_space = memory_mb * 1024 * 1024
    cpu_seconds = max(1, int(cpu_seconds))

    def apply_limits() -> None:  # pragma: no cover - runs in the forked child
        os.setsid()
        _set_limit(resource, resource.RLIMIT_CORE, 0)
        _set_limit(resource, resource.RLIMIT_FSIZE, 8 * 1024 * 1024)
        _set_limit(resource, resource.RLIMIT_NOFILE, 64)
        _set_limit(resource, resource.RLIMIT_AS, address_space)
        _set_limit(resource, resource.RLIMIT_CPU, cpu_seconds)

    return apply_limits


def _set_limit(resource, which: int, value: int) -> None:  # pragma: no cover - POSIX only
    """Set one soft limit, and the hard limit with it.

    Setting only the soft limit leaves a program free to raise it back up, which
    would make the cap decorative.
    """
    try:
        current_hard = resource.getrlimit(which)
        hard = value if current_hard == resource.RLIM_INFINITY else min(value, current_hard)
        resource.setrlimit(which, (value, hard))
    except (OSError, ValueError):
        # A limit the platform refuses is a limit this run does not have. The
        # wall clock and the output cap still apply, and the parent is told the
        # peak memory so the limit it asked for can be judged against reality.
        pass


def _drain(stream, cap: int, collected: dict[str, Any], key: str) -> None:
    """Read a program's output to EOF, keeping at most ``cap`` bytes.

    Draining continues past the cap on purpose. Stopping at the cap would leave
    the program blocked on a full pipe, and it would then be killed by the wall
    clock and reported as a timeout, which misattributes the failure. The bytes
    past the cap are counted and thrown away, so the worker's own memory stays
    bounded while the program still gets to finish.
    """
    total = 0
    kept = bytearray()
    try:
        while True:
            chunk = stream.read(_DRAIN_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if len(kept) < cap:
                kept.extend(chunk[: cap - len(kept)])
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass
    collected[key] = {
        "text": bytes(kept).decode("utf-8", errors="replace"),
        "total_bytes": total,
        "truncated": total > cap,
    }


def _kill_tree(process: subprocess.Popen) -> None:
    """Kill the program and anything it started.

    A submitted program is free to spawn children, and killing only the direct
    child would leave those running -- which for a fork bomb means the request
    returns and the damage continues. The process is started in its own session on
    POSIX and its own process group on Windows precisely so the whole tree can be
    signalled at once.
    """
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        # The tree may already be gone, which is the outcome we wanted.
        pass
    finally:
        try:
            process.kill()
        except OSError:
            pass


def _peak_memory_mb() -> float | None:
    """Peak resident memory of the program, in MB, or ``None`` if unknowable.

    ``getrusage(RUSAGE_CHILDREN)`` reports the high-water mark across every child
    this process has reaped. The worker starts a fresh process per case and runs
    exactly one program in it, so the reading is that program's alone. Linux
    reports kilobytes and macOS reports bytes, which is the reason for the
    platform check. Windows has no equivalent in the standard library, so the
    measurement is honestly absent rather than guessed.
    """
    if os.name == "nt":
        return None
    try:
        import resource
    except ImportError:  # pragma: no cover - POSIX always has it
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    divisor = 1 if sys.platform == "darwin" else 1024
    return round(usage / divisor, 2)


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": "internal_error",
        "exit_code": None,
        "signal": None,
        "stdout": "",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "duration_ms": 0,
        "peak_memory_mb": None,
        "error": None,
    }
    base.update(fields)
    return base


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    """Run one case of one program and describe what happened.

    This is the only function in the platform that executes learner code. It
    returns a result document; it never raises, and it never returns a verdict,
    because deciding whether the output was correct needs the expected value,
    which lives in the parent.

    A job is in one of two modes. ``run`` starts the submitted program against one
    case. ``compile`` builds it instead, for a language that has to be built before
    it can be started. The two share the whole supervision path -- the sandbox
    directory, the isolated environment, the process group, the output cap and the
    clock -- because a compiler is a program this platform is being asked to run
    on a learner's behalf, and it gets no weaker a sandbox than the submission does.
    What differs is the limits it is charged and the kind it reports.
    """
    # The language itself is not needed here: the parent has already resolved the
    # interpreter and put the command line in the job. The id travels in the job so
    # the document a worker returns can be attributed in a log.
    _ = str(job.get("language") or "")
    mode = str(job.get("mode") or "run")
    compiling = mode == "compile"
    source = str(job["source"])
    stdin_text = str(job.get("stdin") or "")
    entry_name = str(job["entry_name"])
    argv_prefix = [str(part) for part in job["argv_prefix"]]
    append_entry = bool(job.get("append_entry", True))
    # A compile is charged its own budget and its own output cap. Both exist so
    # that building a submission cannot be charged to the clock the program's own
    # execution is judged against.
    wall_clock_ms = int(job["compile_wall_clock_ms"] if compiling else job["wall_clock_ms"])
    memory_mb = int(job["memory_mb"])
    cpu_seconds = int(job.get("cpu_seconds") or 0) or wall_clock_ms // 1000 + 1
    max_output_bytes = int(job["compile_max_output_bytes"] if compiling else job["max_output_bytes"])
    enforce_address_space = bool(job.get("enforce_address_space", True))

    workdir = tempfile.mkdtemp(prefix="algotwin-judge-")
    entry_path = os.path.join(workdir, entry_name)
    try:
        with open(entry_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source)

        preexec = None
        popen_kwargs: dict[str, Any] = {}
        if os.name != "nt" and enforce_address_space:  # pragma: no cover - POSIX only
            preexec = _address_space_limit(memory_mb, cpu_seconds)
        else:
            # Without a preexec hook the process still needs its own group, so a
            # timeout can take the whole tree down rather than one process.
            popen_kwargs["creationflags" if os.name == "nt" else "start_new_session"] = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else True
            )

        started = time.perf_counter()
        process = subprocess.Popen(
            [*argv_prefix, entry_path] if append_entry else argv_prefix,
            cwd=workdir,
            env=_sandbox_env(os.path.dirname(argv_prefix[0]) if argv_prefix else ""),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=preexec,  # pragma: no cover - POSIX only
            close_fds=True,
            **popen_kwargs,
        )

        # The job stream is closed the moment it has been read, so the program
        # cannot inherit a readable handle to the job that named it.
        try:
            sys.stdin.close()
        except OSError:
            pass

        collected: dict[str, Any] = {}
        threads = [
            threading.Thread(target=_drain, args=(process.stdout, max_output_bytes, collected, "stdout"), daemon=True),
            threading.Thread(target=_drain, args=(process.stderr, max_output_bytes, collected, "stderr"), daemon=True),
        ]
        for thread in threads:
            thread.start()

        try:
            process.stdin.write(stdin_text.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            # A program that exits before reading its input is a runtime error,
            # which the exit code below reports. Not writing the input must not
            # turn into an error of its own.
            pass

        timed_out = False
        try:
            process.wait(timeout=max(wall_clock_ms, 0) / 1000)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - the tree is gone
                pass

        for thread in threads:
            thread.join(timeout=5)
        duration_ms = int((time.perf_counter() - started) * 1000)
        peak_memory_mb = _peak_memory_mb()
        stdout = collected.get("stdout", {"text": "", "total_bytes": 0, "truncated": False})
        stderr = collected.get("stderr", {"text": "", "total_bytes": 0, "truncated": False})
        exit_code = process.returncode

        if compiling:
            kind, error = _classify_compile(timed_out, exit_code, stdout, stderr, wall_clock_ms)
        else:
            kind, error = "time_limit", None
            if not timed_out:
                if exit_code is not None and exit_code < 0:
                    kind = "killed_by_signal"
                elif stdout["truncated"] or stderr["truncated"]:
                    kind = "output_limit"
                elif exit_code == 0:
                    kind = "ok"
                else:
                    kind = "nonzero_exit"

        return _result(
            kind=kind,
            exit_code=exit_code,
            signal=-exit_code if exit_code is not None and exit_code < 0 else None,
            stdout=stdout["text"],
            stderr=stderr["text"],
            stdout_truncated=bool(stdout["truncated"]),
            stderr_truncated=bool(stderr["truncated"]),
            duration_ms=duration_ms,
            peak_memory_mb=peak_memory_mb,
            error=error,
        )
    finally:
        # The sandbox directory holds the learner's source and whatever the
        # program wrote, so it goes away whether the run succeeded or not. The
        # compiled artifact does not live here -- the parent owns that directory,
        # because it has to outlive this worker to serve the remaining cases.
        _remove_tree(workdir)


def _classify_compile(
    timed_out: bool,
    exit_code: int | None,
    stdout: dict[str, Any],
    stderr: dict[str, Any],
    wall_clock_ms: int,
) -> tuple[str, str | None]:
    """How a compilation went, as one observation kind.

    Every way a build can fail is reported as ``compile_error`` rather than as the
    distinct runtime kinds, because from the learner's side they are one thing:
    the source did not become a program. The ``error`` line distinguishes them --
    a compiler that timed out, one that printed too much, and one that rejected
    the source are three different messages -- while the verdict the parent
    derives is one, which is what the submission table has a column for.
    """
    if timed_out:
        return "compile_error", f"The compiler did not finish within {wall_clock_ms} ms."
    if stdout["truncated"] or stderr["truncated"]:
        return "compile_error", "The compiler produced more output than the judge accepts."
    if exit_code == 0:
        return "ok", None
    return "compile_error", f"The compiler exited with code {exit_code}."


def _remove_tree(path: str) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    """Read one job, run it, print one result. Always exits ``0``."""
    try:
        job = json.loads(sys.stdin.read())
    except (OSError, ValueError) as error:
        _emit(_result(error=f"the worker could not read its job: {error}"))
        return 0

    try:
        outcome = run_job(job)
    except Exception as error:  # noqa: BLE001 - the worker must never raise at the parent
        outcome = _result(error=f"{type(error).__name__}: {error}")
    _emit(outcome)
    return 0


def _emit(outcome: dict[str, Any]) -> None:
    try:
        sys.stdout.write(RESULT_SENTINEL + "\n")
        sys.stdout.write(json.dumps(outcome))
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
