"""Executing one program against one input, outside the API process.

This module is the service-layer face of :mod:`backend.app.judge`. It resolves a
language name a request supplied into a runnable language, applies a problem's
stored limits, and returns what the program did. It does not decide whether the
output was correct: one execution has no answer to compare against, and the
judge -- which does hold the answers -- is the module that compares.

Three names are kept from the version of this module that shipped before any
runner existed, so callers and imports written against the stub contract keep
working:

* :class:`ExecutionRequest` is still the input, now carrying an optional
  resolved :class:`~backend.app.judge.limits.ExecutionLimits` instead of an
  unused list of test cases;
* :class:`ExecutionResult` is still the output, and is now the runner's real
  observation rather than a shape nothing could fill in;
* :class:`CodeExecutionService` is still the entry point, and it now runs code.

:class:`ExecutionNotConfiguredError` is gone rather than kept as a stub: a typed
"this is not available" error that no longer has a case to raise is the kind of
thing that reads as a live feature. The real unavailability error is
:class:`~backend.app.judge.languages.LanguageUnavailableError`, raised when this
machine has no interpreter for a language the catalog offers.

The boundary this module exists to enforce is the one in the README: untrusted
code is never executed inside the FastAPI process. Everything here delegates to
the judge package, which starts a separate worker for every run.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.judge.languages import (
    LanguageSpec,
    LanguageUnavailableError,
    get_language,
)
from backend.app.judge.limits import ExecutionLimits
from backend.app.judge.runner import ExecutionError, RunOutcome, execute

#: The execution observation, under the name this module has always exported it
#: as. It is the runner's type rather than a copy of it, so there is exactly one
#: definition of "what a program did" in the codebase.
ExecutionResult = RunOutcome

#: Raised for a language this machine cannot run. Re-exported so a caller that
#: already imports this module does not have to reach into the judge package to
#: catch it.
__all__ = [
    "ExecutionError",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionUnavailableError",
    "LanguageUnavailableError",
    "CodeExecutionService",
    "LanguageSpec",
    "ExecutionLimits",
    "get_execution_service",
]

#: Raised when the platform cannot offer execution at all, as opposed to one
#: language being missing. Distinct from :class:`LanguageUnavailableError` so a
#: deployment with no Node installed still serves Python, and so a caller can tell
#: "this language" apart from "no execution here".
ExecutionUnavailableError = LanguageUnavailableError


@dataclass(frozen=True)
class ExecutionRequest:
    """One program, one input, one budget.

    `test_cases` is deliberately gone. A list of cases is a judging concern, and
    carrying it on an execution request invited the reading that a single
    execution could produce a pass count, which it cannot.
    """

    language: str
    source_code: str
    stdin: str = ""
    limits: ExecutionLimits | None = None


class CodeExecutionService:
    """Run a learner's program once, out of process.

    The class is stateless, so the module keeps a single shared instance rather
    than building one per request. There is nothing per-run to carry between
    calls: every run gets a fresh worker process, which is the point.
    """

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Run ``request.source_code`` on ``request.stdin``.

        Raises :class:`LanguageUnavailableError` for a language this machine
        cannot run, so a caller can answer 503 for that rather than reporting a
        failure against the learner's code.
        """
        language = get_language(request.language)
        if language is None:
            raise LanguageUnavailableError(
                f"{request.language!r} is not a language the platform can run."
            )
        limits = request.limits or ExecutionLimits.resolve(time_limit_ms=None, memory_limit_mb=None)
        return execute(language, request.source_code, request.stdin, limits)


_execution_service = CodeExecutionService()


def get_execution_service() -> CodeExecutionService:
    """The shared execution service."""
    return _execution_service
