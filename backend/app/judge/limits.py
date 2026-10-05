"""What one run of one program is allowed to cost.

Every number here is a ceiling, not a target, and every one of them is enforced
somewhere: the wall clock by the worker that supervises the run and again by the
parent that supervises the worker, the CPU time and the address space by POSIX
resource limits, and the output size by the drain loop that reads the program's
output.

The clamp rules are deliberately visible. A catalog row can ask for a limit the
developer's machine cannot honour, and the honest response is to run under the
smaller limit and *report* the clamped value, never to quietly grant more than
the problem asked for and never to silently drop a limit because it could not be
applied.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.models.problem import MAX_MEMORY_LIMIT_MB, MAX_TIME_LIMIT_MS

from backend.app.services.output_compare import MAX_OUTPUT_BYTES

#: The smallest wall-clock a run may be given. Below roughly this, a program
#: cannot start, let alone run, so honouring a smaller request would report every
#: submission as a timeout.
MIN_WALL_CLOCK_MS = 100

#: Grace added on top of the wall clock before the parent gives up on the worker
#: process itself. The worker normally kills the program and exits promptly; this
#: covers the case where the worker is wedged rather than the program, and is what
#: stops one request from holding a thread forever.
WORKER_GRACE_MS = 5_000

#: The most test cases a single judge run will execute. A catalog problem has
#: under ten; the ceiling exists so a hand-edited row cannot turn one request into
#: an unbounded number of process spawns.
MAX_CASES_PER_RUN = 50

#: The total wall-clock one judge run may spend across all of its cases. This is
#: the request-level budget, and it is what makes a synchronous run endpoint safe
#: to expose: the work is bounded even if every case uses its full allowance.
MAX_JUDGE_WALL_CLOCK_MS = 30_000

#: The most bytes a single case's input may carry. A catalog input is a few
#: hundred characters; this leaves room for a hand-written case without letting
#: one request ship a payload the judge would have to hold in memory.
MAX_STDIN_BYTES = 256 * 1024

#: The wall clock one compilation may take. Separate from the per-case clock
#: because compiling and running are different work with wildly different costs:
#: `javac` is itself a JVM, so a cold compile is hundreds of milliseconds of
#: start-up before it looks at a line of source. Charging that to the learner's
#: time limit would make every Java submission time out on the machine that is
#: otherwise perfectly able to run it. It is charged to the request budget
#: instead, so a slow compile still cannot hold a request open indefinitely.
DEFAULT_COMPILE_WALL_CLOCK_MS = 20_000

#: The ceiling on the compile clock. A submission that has not compiled in a
#: minute is not going to, and the parent must not wait longer than this before it
#: stops the worker.
MAX_COMPILE_WALL_CLOCK_MS = 60_000

#: The most bytes a compiler's diagnostics may produce. A real compile error is a
#: few dozen lines; the cap exists so a pathological source cannot make the
#: compile step's output the largest thing the request held.
MAX_COMPILE_OUTPUT_BYTES = 64 * 1024


@dataclass(frozen=True)
class ExecutionLimits:
    """The resolved budget for one execution of one program.

    Frozen because the limits are decided once, before anything runs, and a limit
    that could be changed mid-run would be a limit that cannot be enforced.
    """

    wall_clock_ms: int
    memory_mb: int
    cpu_seconds: int
    max_output_bytes: int = MAX_OUTPUT_BYTES
    #: The wall clock for the whole run, across every case, as opposed to
    #: :attr:`wall_clock_ms`, which is for one case. A run is only ever ``accepted``
    #: if it finished inside this, so a run that hit it is reported as truncated
    #: rather than as a pass.
    total_budget_ms: int = MAX_JUDGE_WALL_CLOCK_MS
    #: The clock for the one compilation a submission needs, when its language is
    #: a compiled one. An interpreted language never reads this, so it costs an
    #: interpreted submission nothing.
    compile_wall_clock_ms: int = DEFAULT_COMPILE_WALL_CLOCK_MS
    #: The cap on compiler diagnostics, for the same reason.
    compile_max_output_bytes: int = MAX_COMPILE_OUTPUT_BYTES

    @classmethod
    def resolve(
        cls,
        time_limit_ms: int | None,
        memory_limit_mb: int | None,
        total_budget_ms: int | None = None,
    ) -> ExecutionLimits:
        """Turn a problem's stored limits into a budget this machine will honour.

        Both problem limits are clamped into the platform-wide range, the wall
        clock is raised to :data:`MIN_WALL_CLOCK_MS` and the CPU allowance is one
        second above it, so a program cannot be killed for CPU time while it still
        had wall-clock time left to finish in.

        ``total_budget_ms`` is the deployment's request budget rather than the
        problem's, and it is clamped down to :data:`MAX_JUDGE_WALL_CLOCK_MS` so no
        configuration can turn one synchronous request into an unbounded wait. The
        per-case clock is then bounded *by* it, which is what makes the worst case
        for one request equal the budget instead of the budget multiplied by the
        number of cases.
        """
        total_budget_ms = _clamp_int(
            total_budget_ms,
            default=MAX_JUDGE_WALL_CLOCK_MS,
            low=MIN_WALL_CLOCK_MS,
            high=MAX_JUDGE_WALL_CLOCK_MS,
        )
        wall_clock_ms = _clamp_int(time_limit_ms, default=MAX_TIME_LIMIT_MS, low=1, high=MAX_TIME_LIMIT_MS)
        wall_clock_ms = max(min(wall_clock_ms, total_budget_ms), MIN_WALL_CLOCK_MS)
        memory_mb = _clamp_int(memory_limit_mb, default=MAX_MEMORY_LIMIT_MB, low=1, high=MAX_MEMORY_LIMIT_MB)
        return cls(
            wall_clock_ms=wall_clock_ms,
            memory_mb=memory_mb,
            cpu_seconds=wall_clock_ms // 1000 + 1,
            max_output_bytes=MAX_OUTPUT_BYTES,
            total_budget_ms=total_budget_ms,
            compile_wall_clock_ms=_clamp_int(
                DEFAULT_COMPILE_WALL_CLOCK_MS,
                default=DEFAULT_COMPILE_WALL_CLOCK_MS,
                low=MIN_WALL_CLOCK_MS,
                high=MAX_COMPILE_WALL_CLOCK_MS,
            ),
            compile_max_output_bytes=MAX_COMPILE_OUTPUT_BYTES,
        )


def _clamp_int(value: object, *, default: int, low: int, high: int) -> int:
    """Coerce a possibly-missing, possibly-nonsense stored limit into a range.

    A catalog row is data, not code, so a ``time_limit_ms`` of ``None``, ``"2000"``
    or ``-5`` has to be survivable. Anything unreadable falls back to the
    platform default rather than failing the run: refusing to run a problem
    because one column is odd would be a worse outcome than running it under the
    documented default.
    """
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        coerced = default
    return max(low, min(coerced, high))


__all__ = [
    "DEFAULT_COMPILE_WALL_CLOCK_MS",
    "MAX_CASES_PER_RUN",
    "MAX_COMPILE_OUTPUT_BYTES",
    "MAX_COMPILE_WALL_CLOCK_MS",
    "MAX_JUDGE_WALL_CLOCK_MS",
    "MAX_OUTPUT_BYTES",
    "MAX_STDIN_BYTES",
    "MIN_WALL_CLOCK_MS",
    "WORKER_GRACE_MS",
    "ExecutionLimits",
]
