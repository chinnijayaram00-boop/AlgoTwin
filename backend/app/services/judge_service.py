"""Application use cases for running a learner's code against a problem.

The split between this module and :mod:`backend.app.judge` is the one the rest of
the codebase already uses between a route and a service. The judge package knows
how to start a process and decide whether an answer matched; this module knows
*which* cases a request is allowed to see, and turns a judge's report into the
shape the API publishes.

The rule this module exists to enforce is a disclosure one. Judging runs the
hidden cases -- that is the whole point of having them -- but a hidden case's
input and expected output must never leave the platform. :func:`disclose` is the
single place that decides what a run response may contain, and
`backend/tests/test_judge.py` asserts the redaction against every response shape
rather than trusting the code path that happens to be exercised.
"""

from __future__ import annotations

from typing import Any

from database.models import Problem
from database.models.submission import SubmissionStatus

from backend.app.judge import judge as judge_engine
from backend.app.judge.judge import NoTestCasesError
from backend.app.judge.languages import (
    LanguageSpec,
    LanguageUnavailableError,
    available_languages,
    get_language,
)
from backend.app.judge.limits import ExecutionLimits
from backend.app.judge.runner import RunOutcome
from backend.app.schemas.judge import (
    AdHocCaseResult,
    JudgeCaseResult,
    ProblemRunResponse,
)


class UnsupportedLanguageError(ValueError):
    """A request asked for a language this problem or this deployment cannot run.

    Distinct from a wrong answer, and reported to the caller rather than turned
    into a verdict: there is nothing here to judge.
    """


class ExecutionDisabledError(RuntimeError):
    """Execution is switched off for this deployment.

    The run routes turn this into a 503. It is not a 4xx because nothing the
    learner sent is wrong -- the server simply cannot offer the feature.
    """


def _require_execution_enabled(settings) -> None:
    if not settings.execution_enabled:
        raise ExecutionDisabledError(
            "Code execution is disabled on this deployment. Set EXECUTION_ENABLED=true "
            "to offer it."
        )


def resolve_language(problem: Problem, language_id: str, settings=None) -> LanguageSpec:
    """Resolve the language a request asked for against what the problem offers.

    Three failures are all reported the same way, as a 422 naming the problem's
    own languages:

    * an unknown language name;
    * a language the machine or the deployment cannot run;
    * a language the platform can run but this problem does not ship a starter for.

    The third is the one that mattered in practice. Four catalog entries used to
    advertise Java while the submission API accepted only Python and JavaScript,
    so a learner could fill in a Java tab and get a 422 on submit. Answering with
    the problem's real language list is the response that helps.
    """
    supported = list(problem.supported_languages or [])
    normalised = language_id.strip().lower() if isinstance(language_id, str) else ""
    if normalised not in supported:
        raise UnsupportedLanguageError(
            f"{problem.slug} supports {', '.join(supported) or 'no language yet'}."
        )
    spec = get_language(normalised, settings)
    if spec is None:
        raise UnsupportedLanguageError(
            f"{normalised} cannot be run on this deployment. "
            f"{problem.slug} supports {', '.join(supported)}."
        )
    return spec


def resolve_limits(problem: Problem, settings) -> ExecutionLimits:
    """The budget for one run of one program on this problem.

    Reads the problem's clamped limits and the deployment's request budget. The
    per-case wall clock is the problem's; the whole-run budget is the
    deployment's, and the judge stops before it is exceeded rather than after.
    """
    return ExecutionLimits.resolve(
        time_limit_ms=problem.effective_time_limit_ms,
        memory_limit_mb=problem.effective_memory_limit_mb,
        total_budget_ms=getattr(settings, "max_judge_wall_clock_ms", None),
    )


def _disclose(result: judge_engine.CaseResult) -> JudgeCaseResult:
    """Project one case result, redacting anything a hidden case must not reveal.

    A hidden case contributes its verdict, its runtime, and its position. It does
    not contribute its input or its expected output, and it does not contribute
    the program's own output either: for a hidden case, the input is the puzzle,
    and printing the program's answer next to the case number would tell a
    learner which case their solution fails on with enough detail to work out what
    the input was.
    """
    if result.is_hidden:
        return JudgeCaseResult(
            index=result.index,
            is_hidden=True,
            passed=result.passed,
            verdict=result.verdict,
            error_message=_hidden_message(result),
            duration_ms=result.duration_ms,
            case_input=None,
            expected_output=None,
            actual_output=None,
        )
    return JudgeCaseResult(
        index=result.index,
        is_hidden=False,
        passed=result.passed,
        verdict=result.verdict,
        error_message=result.error_message,
        duration_ms=result.duration_ms,
        case_input=result.case_input,
        expected_output=result.expected_output,
        actual_output=result.actual_output,
    )


def _hidden_message(result: judge_engine.CaseResult) -> str | None:
    """The error a hidden case is allowed to carry.

    The category, never the content: "the program ran longer than the time
    limit" is useful and safe, while the program's own stderr for a hidden case
    can quote the input that produced it.
    """
    if result.passed:
        return None
    if result.verdict is SubmissionStatus.WRONG_ANSWER:
        return "The program printed the wrong answer for this case."
    if result.verdict is SubmissionStatus.TIME_LIMIT_EXCEEDED:
        return "The program ran longer than the time limit on this case."
    if result.verdict is SubmissionStatus.MEMORY_LIMIT_EXCEEDED:
        return "The program exceeded the memory limit on this case."
    return "The program failed on this case."


def run_visible_cases(
    problem: Problem,
    language: LanguageSpec,
    source_code: str,
    settings,
) -> ProblemRunResponse:
    """Run a program against every case a learner is allowed to see.

    The hidden cases are not run. "Run test cases" in the workspace is a
    debugging aid, and a debugging aid that ran the hidden suite would hand over
    the pass/fail vector for the graded set -- which is most of the answer.

    A problem with no visible cases is a 409-style condition the caller must
    handle, not a run with nothing to show. The judge raises
    :class:`NoTestCasesError` and the route reports it, because a run that silently
    produced an empty result would look identical to a program that passed
    everything.
    """
    _require_execution_enabled(settings)
    cases = problem.visible_test_cases()
    report = judge_engine.judge(
        language=language,
        source_code=source_code,
        cases=cases,
        limits=resolve_limits(problem, settings),
    )
    return ProblemRunResponse(
        problem_id=problem.id,
        problem_slug=problem.slug,
        language=language.id,
        verdict=report.verdict,
        cases_run=report.cases_run,
        cases_passed=report.cases_passed,
        cases_total=report.cases_total,
        error_message=report.error_message,
        total_runtime_ms=report.total_runtime_ms,
        peak_memory_mb=report.peak_memory_mb,
        truncated=report.truncated,
        time_limit_ms=problem.effective_time_limit_ms,
        memory_limit_mb=problem.effective_memory_limit_mb,
        cases=[_disclose(result) for result in report.results],
    )


def run_adhoc_input(
    problem: Problem,
    language: LanguageSpec,
    source_code: str,
    stdin_text: str,
    settings,
) -> ProblemRunResponse:
    """Run a program on the learner's own input, with nothing to compare against.

    The response has no verdict and no case counts. An input with no expected
    output cannot be right or wrong, and returning ``verdict: accepted`` here would
    be the single easiest way for the platform to start telling learners their code
    passes when it has not checked anything. A run that crashed or timed out still
    says so -- through ``ad_hoc`` and ``error_message``, which describe the run
    rather than grading it -- because hiding a crash behind a null verdict would
    just be a worse lie.
    """
    _require_execution_enabled(settings)
    outcome = judge_engine.run_uncounted(
        language=language,
        source_code=source_code,
        stdin_text=stdin_text,
        limits=resolve_limits(problem, settings),
    )
    return ProblemRunResponse(
        problem_id=problem.id,
        problem_slug=problem.slug,
        language=language.id,
        verdict=None,
        cases_run=0,
        cases_passed=0,
        cases_total=0,
        error_message=judge_engine.outcome_message(outcome),
        total_runtime_ms=outcome.duration_ms,
        peak_memory_mb=outcome.peak_memory_mb,
        truncated=False,
        time_limit_ms=problem.effective_time_limit_ms,
        memory_limit_mb=problem.effective_memory_limit_mb,
        ad_hoc=AdHocCaseResult(
            stdin=stdin_text,
            stdout=judge_engine.clip_output(outcome.stdout),
            stderr=judge_engine.clip_output(outcome.stderr),
            exit_code=outcome.exit_code,
            timed_out=outcome.timed_out,
        ),
        cases=[],
    )


class SubmissionJudgement:
    """The verdict and measurements for one judged submission.

    This is deliberately a separate, small type from :class:`ProblemRunResponse`.
    A judged submission is persisted and shown in a learner's history, so what
    the API stores and returns here is a summary -- a verdict, a pass count, a
    runtime, a peak memory, and a safe error string. It deliberately carries no
    per-case results: the per-case detail (including anything a hidden case
    revealed) belongs to the transient Run flow, not to a durable record that a
    learner can list, filter, and revisit. The counts are enough for a history
    row; the per-case inputs and outputs are not, and a stored submission must
    never become a way to read the hidden suite.
    """

    __slots__ = (
        "verdict",
        "cases_run",
        "cases_passed",
        "cases_total",
        "total_runtime_ms",
        "peak_memory_mb",
        "error_message",
    )

    def __init__(
        self,
        verdict: SubmissionStatus,
        cases_run: int,
        cases_passed: int,
        cases_total: int,
        total_runtime_ms: int,
        peak_memory_mb: float | None,
        error_message: str | None,
    ) -> None:
        self.verdict = verdict
        self.cases_run = cases_run
        self.cases_passed = cases_passed
        self.cases_total = cases_total
        self.total_runtime_ms = total_runtime_ms
        self.peak_memory_mb = peak_memory_mb
        self.error_message = error_message

    @property
    def accepted(self) -> bool:
        """True only when the judge returned ``accepted``."""
        return self.verdict is SubmissionStatus.ACCEPTED

    @property
    def rounded_peak_memory_mb(self) -> int | None:
        """Peak memory as whole megabytes, or ``None`` where it was not measurable.

        The submission table stores ``memory_mb`` as an integer, so a platform
        that can measure fractional memory rounds it. A platform that cannot
        measure it at all reports ``None`` and stores ``None`` -- an absent
        measurement is never stored as zero, which would read as "used no
        memory" rather than "not measured".
        """
        if self.peak_memory_mb is None:
            return None
        return max(0, int(round(self.peak_memory_mb)))


def judge_submission(
    problem: Problem,
    language: LanguageSpec,
    source_code: str,
    settings,
) -> SubmissionJudgement:
    """Judge a learner's program against a problem's full case set.

    Unlike :func:`run_visible_cases`, this runs **every** case, hidden included.
    A submission is the graded act: the whole point is the pass/fail decision the
    hidden cases exist to make trustworthy, and the learner is told only whether
    it passed -- never a hidden case's input, expected output, or their own
    output. The per-case detail is used here to compute the verdict and is then
    discarded; what leaves this function is the :class:`SubmissionJudgement`
    summary with no per-case data in it.

    The verdict is whatever :func:`backend.app.judge.judge.judge` returns, which
    is already a :class:`SubmissionStatus`. It is stored verbatim: a submission
    that failed to run, timed out, or printed the wrong answer records exactly
    that, and no path here ever substitutes ``accepted``.
    """
    _require_execution_enabled(settings)
    cases = list(problem.test_cases or [])
    report = judge_engine.judge(
        language=language,
        source_code=source_code,
        cases=cases,
        limits=resolve_limits(problem, settings),
    )
    return SubmissionJudgement(
        verdict=report.verdict,
        cases_run=report.cases_run,
        cases_passed=report.cases_passed,
        cases_total=report.cases_total,
        total_runtime_ms=report.total_runtime_ms,
        peak_memory_mb=report.peak_memory_mb,
        error_message=report.error_message,
    )


def describe_languages(settings=None) -> list[dict[str, Any]]:
    """The runnable languages, for a caller that wants to render tabs.

    ``settings`` is the same request-scoped settings the routes resolved, rather
    than a second look at the process-wide configuration. Reading the global here
    would mean a language list and the toggle reported beside it could disagree
    about what this deployment has switched on.
    """
    return [{"id": spec.id, "label": spec.label} for spec in available_languages(settings)]


__all__ = [
    "ExecutionDisabledError",
    "LanguageUnavailableError",
    "NoTestCasesError",
    "RunOutcome",
    "SubmissionJudgement",
    "UnsupportedLanguageError",
    "describe_languages",
    "judge_submission",
    "resolve_language",
    "resolve_limits",
    "run_adhoc_input",
    "run_visible_cases",
]
