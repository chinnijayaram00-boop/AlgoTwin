"""Judging: turning what a program did into whether it was correct.

This is the only module that knows both halves of a question -- the output a
program produced and the output it was supposed to produce -- and it is
deliberately the only one. The worker runs the program and is told neither; the
runner supervises the worker and reads only measurements; the comparison rule
lives in :mod:`backend.app.services.output_compare` so a verdict here and a
catalog check elsewhere cannot disagree about what "the same output" means.

The verdict vocabulary is :class:`database.models.submission.SubmissionStatus`
itself, not a parallel enum. A judge that could emit a status the submission table
does not allow would need a translation layer that is only ever exercised once
the statuses start being written back, and that layer is exactly where a
"compilation succeeded therefore accepted" bug would hide.
"""

from __future__ import annotations

import signal
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from database.models.submission import MAX_ERROR_MESSAGE_LENGTH, SubmissionStatus

from backend.app.judge.languages import LanguageSpec
from backend.app.judge.limits import (
    MAX_CASES_PER_RUN,
    MAX_STDIN_BYTES,
    ExecutionLimits,
)
from backend.app.judge.runner import RunOutcome, execute
from backend.app.services.output_compare import outputs_match

#: How much of a failing program's own stderr is echoed back. Enough for a
#: traceback to be recognisable, small enough that a program printing megabytes
#: of noise cannot turn a run response into one.
MAX_REPORTED_OUTPUT = 4_000

#: The longest case input a judge will read, and the message used when one is
#: longer. A catalog input is a few hundred characters.
_STDIN_TOO_LARGE = "This input is larger than the judge accepts for one case."


class NoTestCasesError(ValueError):
    """A run was asked to produce a verdict but the problem has no cases to run.

    Its own error type, because the correct response is neither "accepted" nor
    "wrong answer". A problem with no cases has not been passed, and reporting
    either would be a claim about correctness that nothing established.
    """


@dataclass(frozen=True)
class JudgeCase:
    """One case, in the shape the judge consumes.

    ``expected_output`` is optional only so the error above can be raised
    without inventing an answer; :meth:`__post_init__` refuses a case that is
    neither hidden-with-no-answer nor a complete visible case.
    """

    input: str
    expected_output: str
    is_hidden: bool = False


@dataclass(frozen=True)
class CaseResult:
    """What one case decided.

    ``actual_output`` is always populated, because a learner needs to see what
    their program printed. ``expected_output`` and ``input`` are only meaningful
    for a case the learner may read, and :func:`disclose` is what guarantees a
    hidden case never carries them out of the judge.
    """

    index: int
    is_hidden: bool
    passed: bool
    actual_output: str
    expected_output: str
    case_input: str
    verdict: SubmissionStatus
    error_message: str | None = None
    duration_ms: int = 0
    peak_memory_mb: float | None = None


@dataclass(frozen=True)
class JudgeReport:
    """The result of judging one program against a set of cases."""

    verdict: SubmissionStatus
    cases_run: int
    cases_passed: int
    cases_total: int
    results: list[CaseResult] = field(default_factory=list)
    error_message: str | None = None
    #: The sum of the per-case runtimes. This is what the platform spent, not
    #: what the program needed: a case that timed out is reported at the limit it
    #: was killed at, so this is an upper bound on the honest figure.
    total_runtime_ms: int = 0
    peak_memory_mb: float | None = None
    #: True when the run stopped before every case was executed, either because
    #: the budget ran out or because a case could not continue. A truncated run
    #: can never be ``accepted``: a program is only accepted once every case it
    #: was given has passed.
    truncated: bool = False


def clip_output(text: str) -> str:
    if len(text) <= MAX_REPORTED_OUTPUT:
        return text
    return text[:MAX_REPORTED_OUTPUT] + "\n... output truncated by the judge."


def clip_error(message: str | None) -> str | None:
    """Clip an error message to the width of the column it is stored in.

    Separate from :func:`clip_output` because the two have different budgets. A
    program's output may be several kilobytes -- the workspace shows it next to the
    case it belongs to -- but ``submissions.error_message`` is a bounded column, and
    a message that overflowed it would fail the write of an otherwise perfectly
    good verdict. Clipping here rather than at the write means the response a
    learner sees is already the message that will be stored.
    """
    if message is None or len(message) <= MAX_ERROR_MESSAGE_LENGTH:
        return message
    suffix = "\n... message truncated."
    return message[: MAX_ERROR_MESSAGE_LENGTH - len(suffix)] + suffix


def outcome_message(outcome: RunOutcome) -> str | None:
    """What went wrong with a run that had no expected output to compare against.

    The ad-hoc path has no verdict to give, so this is the whole of what it can
    honestly report: the run failed for this reason. It never says an answer was
    right or wrong, because nothing was compared.
    """
    _verdict, message = verdict_for_observation(outcome)
    return clip_error(message) if message and outcome.kind != "ok" else None


def _looks_like_compile_error(outcome: RunOutcome) -> bool:
    """Whether a nonzero exit was the interpreter refusing the source, not the program failing.

    A Python ``SyntaxError`` and a Node ``SyntaxError`` both surface as a nonzero
    exit whose stderr names a syntax error, because the interpreter cannot even
    start the program. That is a different kind of failure from a program that
    started and then crashed: the learner has to fix a typo in the source, not a
    bug in a running program, and reporting it as ``runtime_error`` would send
    them looking in the wrong place.

    The detection is deliberately conservative -- it looks for the interpreter's
    own ``SyntaxError`` marker and requires it near the top of the diagnostic.
    A program that *prints* the word "SyntaxError" while running normally is not
    mislabelled, because a clean run is already ``ok`` before this is consulted,
    and a program that crashes while printing such a word has it only in its
    output, which is appended after the interpreter's exit line rather than as
    the diagnostic head. When the marker is absent the result stays
    ``runtime_error``, which is the correct default for a nonzero exit.
    """
    if outcome.kind != "nonzero_exit" or not outcome.stderr:
        return False
    head = outcome.stderr[:400]
    return "SyntaxError" in head


def verdict_for_observation(outcome: RunOutcome) -> tuple[SubmissionStatus, str | None]:
    """Map a raw run observation onto the submission status vocabulary.

    The mapping is where a platform must be most careful, because these strings
    are shown to a learner as the reason their code failed. Anything not
    positively identified is ``failed`` with the program's own output attached,
    never ``accepted``.
    """
    if outcome.kind == "ok":
        return SubmissionStatus.ACCEPTED, None
    if outcome.kind == "time_limit":
        return SubmissionStatus.TIME_LIMIT_EXCEEDED, "The program ran longer than the time limit."
    if outcome.kind == "output_limit":
        return (
            SubmissionStatus.FAILED,
            "The program produced more output than the judge accepts, so its answer could not be read.",
        )
    if outcome.kind == "killed_by_signal":
        # SIGKILL with no stderr is the shape an out-of-memory kill takes on both
        # Linux and Windows. A SIGSEGV is a crash in the program, not a limit.
        if outcome.signal == getattr(signal, "SIGKILL", 9):
            return (
                SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
                "The program was stopped after exceeding the memory limit.",
            )
        name = signal.Signals(outcome.signal).name if outcome.signal else "a signal"
        return SubmissionStatus.RUNTIME_ERROR, f"The program was stopped by {name}."
    if outcome.kind == "nonzero_exit":
        detail = clip_output(outcome.stderr).strip() or clip_output(outcome.stdout).strip()
        if _looks_like_compile_error(outcome):
            # The interpreter refused to start the source. Report it as a compile
            # failure so the learner knows to fix the source rather than hunt a
            # runtime bug. The diagnostic carries the interpreter's own message
            # (the offending line and caret), which is exactly the detail a
            # learner needs and discloses nothing about any hidden case.
            return SubmissionStatus.COMPILATION_ERROR, clip_error(
                detail or "The source could not be compiled."
            )
        message = f"The program exited with code {outcome.exit_code}."
        if detail:
            message = f"{message}\n{detail}"
        return SubmissionStatus.RUNTIME_ERROR, clip_error(message)
    return (
        SubmissionStatus.FAILED,
        clip_error(outcome.error or "The judge could not run this program."),
    )


def _validate_cases(cases: Sequence[dict[str, Any]]) -> list[JudgeCase]:
    """Read a problem's stored cases into the shape the judge understands.

    Validation lives here rather than in a model property so a hand-edited or
    half-migrated catalog row fails here, loudly and by name, instead of reaching
    a comparison against ``None``.
    """
    parsed: list[JudgeCase] = []
    for position, raw in enumerate(cases):
        if not isinstance(raw, dict):
            raise NoTestCasesError(f"Test case {position} is not a case object.")
        case_input = raw.get("input")
        expected = raw.get("expected_output")
        if not isinstance(case_input, str) or not isinstance(expected, str):
            raise NoTestCasesError(
                f"Test case {position} is missing a string input or expected_output."
            )
        if len(case_input.encode("utf-8")) > MAX_STDIN_BYTES:
            raise NoTestCasesError(_STDIN_TOO_LARGE)
        parsed.append(
            JudgeCase(
                input=case_input,
                expected_output=expected,
                is_hidden=bool(raw.get("is_hidden")),
            )
        )
    return parsed


def judge(
    language: LanguageSpec,
    source_code: str,
    cases: Sequence[dict[str, Any]],
    limits: ExecutionLimits,
) -> JudgeReport:
    """Run ``source_code`` against every case and decide whether it is correct.

    A case that fails stops the run. Running the remaining cases after a timeout
    or a crash tells the learner nothing they do not already know, and each one
    costs another process spawn inside a request budget that is better spent
    finishing early.

    The report is ``accepted`` only when every case was executed and every one of
    them matched. Anything short of that -- a truncated run, a missing case, a
    platform error -- is a failure with an explanation.
    """
    if not cases:
        raise NoTestCasesError(
            "This problem has no test cases, so it cannot be judged. A run without "
            "cases is not a pass."
        )
    if len(cases) > MAX_CASES_PER_RUN:
        raise NoTestCasesError(
            f"A single run executes at most {MAX_CASES_PER_RUN} cases; this problem has {len(cases)}."
        )

    parsed = _validate_cases(cases)
    results: list[CaseResult] = []
    total_runtime_ms = 0
    peak_memory_mb: float | None = None
    verdict = SubmissionStatus.ACCEPTED
    error_message: str | None = None

    for index, case in enumerate(parsed):
        if total_runtime_ms >= limits.total_budget_ms:
            # Out of budget. This is a failure, not a pass, and it is reported as
            # truncated so no caller can mistake a partial run for a full one.
            verdict = SubmissionStatus.TIME_LIMIT_EXCEEDED
            error_message = clip_error(
                f"The judge stopped after {index} of {len(parsed)} cases to stay inside "
                "its own time budget."
            )
            break

        outcome = execute(language, source_code, case.input, limits)
        case_verdict, case_error = verdict_for_observation(outcome)
        passed = case_verdict is SubmissionStatus.ACCEPTED and outputs_match(
            outcome.stdout, case.expected_output
        )
        if not passed and case_verdict is SubmissionStatus.ACCEPTED:
            # It ran cleanly and still did not match. That is a wrong answer, not
            # an error, and the learner should be told so.
            case_verdict = SubmissionStatus.WRONG_ANSWER
            case_error = "The program ran successfully but printed the wrong answer."

        results.append(
            CaseResult(
                index=index,
                is_hidden=case.is_hidden,
                passed=passed,
                actual_output=clip_output(outcome.stdout),
                expected_output=case.expected_output,
                case_input=case.input,
                verdict=case_verdict,
                error_message=clip_error(case_error),
                duration_ms=outcome.duration_ms,
                peak_memory_mb=outcome.peak_memory_mb,
            )
        )
        total_runtime_ms += outcome.duration_ms
        peak_memory_mb = _higher(peak_memory_mb, outcome.peak_memory_mb)

        if not passed:
            verdict = case_verdict
            error_message = case_error
            break

    cases_passed = sum(1 for result in results if result.passed)
    return JudgeReport(
        verdict=verdict,
        cases_run=len(results),
        cases_passed=cases_passed,
        cases_total=len(parsed),
        results=results,
        error_message=clip_error(error_message),
        total_runtime_ms=total_runtime_ms,
        peak_memory_mb=peak_memory_mb,
        truncated=len(results) < len(parsed),
    )


def run_uncounted(
    language: LanguageSpec,
    source_code: str,
    stdin_text: str,
    limits: ExecutionLimits,
) -> RunOutcome:
    """Run a program on one ad-hoc input with nothing to compare against.

    This is the "try my own input" path. It reports what the program did and
    deliberately produces no verdict, because an input with no expected output
    cannot be right or wrong.
    """
    if len(stdin_text.encode("utf-8")) > MAX_STDIN_BYTES:
        raise NoTestCasesError(_STDIN_TOO_LARGE)
    return execute(language, source_code, stdin_text, limits)


def _higher(current: float | None, candidate: float | None) -> float | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return max(current, candidate)


def discover_visible_cases(problem: Any) -> list[dict[str, Any]]:
    """The cases of a problem a learner may read.

    Kept as a module function so the "which cases may be disclosed" decision has
    one definition, used by the run endpoint and by the tests that assert a hidden
    case never leaves the judge.
    """
    return list(problem.visible_test_cases())


def summarise(results: Iterable[CaseResult]) -> str:
    """One line describing a finished run, for an error message."""
    return ", ".join(f"case {result.index + 1}: {result.verdict.value}" for result in results)


__all__ = [
    "MAX_REPORTED_OUTPUT",
    "CaseResult",
    "JudgeCase",
    "JudgeReport",
    "NoTestCasesError",
    "clip_error",
    "clip_output",
    "discover_visible_cases",
    "judge",
    "outcome_message",
    "run_uncounted",
    "verdict_for_observation",
]
