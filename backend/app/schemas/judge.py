"""Request and response contracts for running a learner's code.

Three rules are load-bearing in this module, and each one exists because of a way
the boundary could be crossed by accident:

* **A request names no user and no verdict.** `user_id`, `status`, and every
  measurement field are absent, and `extra="forbid"` turns a payload that carries
  one into a 422 rather than a silently ignored value. The learner is the bearer
  token, and the verdict is whatever the judge decided.
* **A hidden case is redacted at the schema, not at the call site.** The
  `case_input`, `expected_output` and `actual_output` fields are `None` for a
  hidden case, and that is representable here rather than being a convention the
  service has to remember. A response that could not express a leak cannot leak.
* **A run with nothing to compare has no verdict.** The ad-hoc path returns the
  program's output, `verdict` is `null`, and `cases_passed`, `cases_run` and
  `cases_total` are all zero, because no one checked the answer. A crash or a
  timeout on that path is still reported, in `ad_hoc` and `error_message`, which
  describe the run rather than grading it.

`SubmissionStatus` is the verdict vocabulary, imported from the model rather than
restated, so a status the submission table cannot store can never be published
here either.
"""

from __future__ import annotations

from typing import Literal

from database.models.problem import MAX_MEMORY_LIMIT_MB, MAX_TIME_LIMIT_MS
from database.models.submission import MAX_SOURCE_CODE_LENGTH, SubmissionStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.judge.languages import LANGUAGE_IDS
from backend.app.judge.limits import MAX_STDIN_BYTES

#: The languages a run request may name. Published in the OpenAPI schema so the
#: editor's tabs and the accepted values are the same list, and built from the
#: language registry so a language can never be added to one and not the other.
RunnableLanguage = Literal["javascript", "python"]

#: The verdict vocabulary, mirrored as a `Literal` for the same reason the
#: submission schemas mirror it. `backend/tests/test_judge.py` asserts this stays
#: in step with the model enum.
RunVerdict = Literal[
    "accepted",
    "wrong_answer",
    "runtime_error",
    "compilation_error",
    "time_limit_exceeded",
    "memory_limit_exceeded",
    "failed",
]


class CodeRunRequest(BaseModel):
    """Body for running a program against a problem.

    `stdin` is optional and its presence changes what the response means. Without
    it the program is run against the problem's visible test cases and the
    response carries a verdict. With it the program is run once on that input and
    the response carries only what it printed -- because an input with no expected
    output cannot be passed or failed.
    """

    model_config = ConfigDict(extra="forbid")

    language: RunnableLanguage = Field(description="Language the source is written in.")
    source_code: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_CODE_LENGTH,
        description="The learner's source. Executed in a separate worker process.",
    )
    stdin: str | None = Field(
        default=None,
        max_length=MAX_STDIN_BYTES,
        description="Run once on this input instead of the visible test cases. No verdict.",
    )

    @field_validator("source_code")
    @classmethod
    def reject_blank_source(cls, value: str) -> str:
        """Reject whitespace-only source.

        The same rule the submission contract applies, for the same reason: a
        blank program is not a program, and running it would produce a verdict
        about nothing.
        """
        if not value.strip():
            raise ValueError("source_code must contain the learner's code.")
        return value


class JudgeCaseResult(BaseModel):
    """One executed case, as much of it as the learner is allowed to see.

    The three optional fields are the redaction mechanism. They are populated for
    a visible case and are `None` for a hidden one, so "this case is hidden" is a
    state this shape can represent rather than something a caller must remember
    to enforce.
    """

    index: int = Field(ge=0, description="Zero-based position in the judge's case order.")
    is_hidden: bool
    passed: bool
    verdict: RunVerdict
    error_message: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    case_input: str | None = Field(default=None, description="Visible cases only.")
    expected_output: str | None = Field(default=None, description="Visible cases only.")
    actual_output: str | None = Field(default=None, description="Visible cases only.")


class AdHocCaseResult(BaseModel):
    """The one run of the learner's own input, with no comparison attached."""

    stdin: str
    stdout: str
    stderr: str
    exit_code: int | None = None
    timed_out: bool = False


class ProblemRunResponse(BaseModel):
    """The result of running a program against a problem.

    `verdict` is `None` for a run on a learner-supplied input. Nothing was
    compared against an expected output, so there is nothing to grade, and the
    field is absent rather than filled with an unearned success. `cases_run` and
    `cases_total` are both zero for the same reason: the run happened, but no case
    was executed.

    A crash or a timeout on a learner-supplied input is still reported, in
    `ad_hoc` and in `error_message`, because those describe how the run went
    rather than grading anything.
    """

    problem_id: int
    problem_slug: str
    language: str
    verdict: RunVerdict | None = Field(
        default=None,
        description="Null when there was no expected output to grade against.",
    )
    cases_run: int = Field(ge=0)
    cases_passed: int = Field(ge=0)
    cases_total: int = Field(ge=0)
    error_message: str | None = None
    total_runtime_ms: int = Field(default=0, ge=0)
    peak_memory_mb: float | None = Field(default=None, ge=0)
    #: True when the judge stopped before executing every case, either because the
    #: deployment's budget ran out or because a case could not continue. A
    #: truncated run is never `accepted`.
    truncated: bool = False
    time_limit_ms: int = Field(ge=1, le=MAX_TIME_LIMIT_MS)
    memory_limit_mb: int = Field(ge=1, le=MAX_MEMORY_LIMIT_MB)
    cases: list[JudgeCaseResult] = Field(default_factory=list)
    ad_hoc: AdHocCaseResult | None = None


class RunLanguagesResponse(BaseModel):
    """The languages this deployment can run right now."""

    items: list[dict[str, str]] = Field(default_factory=list)
    execution_enabled: bool


__all__ = [
    "LANGUAGE_IDS",
    "AdHocCaseResult",
    "CodeRunRequest",
    "JudgeCaseResult",
    "ProblemRunResponse",
    "RunLanguagesResponse",
    "RunVerdict",
    "RunnableLanguage",
    "SubmissionStatus",
]
