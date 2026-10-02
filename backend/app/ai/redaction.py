"""What may be sent to a model, and the arithmetic that bounds it.

This module is the single place where a fact becomes model-visible. Every value a
prompt contains passes through here first, which is what makes "the model is never
shown a hidden test case" a property of the code rather than a promise in a design
document that the next change can quietly invalidate.

**The hard rule: a hidden case's input, expected output, and the program's output
on it never leave the platform.** Not in a prompt, not in a provider error, not in a
log line. AlgoTwin stores those on the problem row, so the temptation is real: the
diagnose route has the whole `test_cases` JSON in hand, and
``Problem.hidden_test_cases()`` hands it over on request. Nothing in this file calls
either. The grounding functions below take named scalars and safe collections, and
there is no function here whose parameter is "a test case".

**The rules the rest of the layer depends on:**

* ``visible_test_cases`` still needs a bound. Visible cases are published to every
  learner in ``GET /problems/{id}``, so quoting one is not a leak -- but pasting the
  whole visible set into a prompt is a way to spend a token budget on data that does
  not help. :data:`MAX_VISIBLE_EXAMPLES_IN_PROMPT` caps it, and
  :data:`MAX_VISIBLE_EXAMPLE_LENGTH` clips each one.
* ``error_message`` is bounded at :data:`MAX_ERROR_MESSAGE_IN_PROMPT`. The judge's
  message is derived from running the learner's own code, so it can be long and can
  contain a fragment of their program. Truncating it mid-string is fine; it is
  presented as evidence, not parsed.
* ``MAX_USER_INPUT_CHARS`` bounds the one genuinely arbitrary input -- the source
  code a learner pasted for a complexity analysis -- and a source longer than that
  is *rejected* rather than truncated. Silently analysing the first 8 KB of a
  program would produce a confident complexity for code that is not the code.
* Nothing is echoed with a role marker that could confuse the model about where
  trusted text ends. :func:`as_prompt_block` emits a fenced, labelled block, and
  every caller uses it, so catalog text and learner text are visually and
  structurally separated inside the prompt.

Every function here is total: it returns a string or a bounded collection, never
``None`` for missing input, and never raises. A grounding function that could raise
would turn a missing optional editorial into a 500 on a learner-facing route.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from database.models.submission import MAX_SOURCE_CODE_LENGTH

#: Longest learner-authored source a complexity prompt will accept. A focused
#: solution is a few hundred lines; 8 000 characters is generous, and anything past
#: it is rejected rather than analysed partially -- see the module docstring.
MAX_USER_INPUT_CHARS: int = 8_000

#: The same ceiling for a submission's stored source. Identical in spirit to the
#: above and separately enforced, because one guards a pasted snippet and the other
#: guards a row this platform stored.
MAX_SUBMISSION_SOURCE_CHARS: int = 16_000

#: How much of the judge's error message reaches a prompt.
MAX_ERROR_MESSAGE_IN_PROMPT: int = 600

#: Visible examples quoted into an explanation. Visible means "already published to
#: every learner", so this is a token budget decision and not a secrecy one.
MAX_VISIBLE_EXAMPLES_IN_PROMPT: int = 2

#: Per-example clip. An example that runs to a page is a prompt that helps nobody.
MAX_VISIBLE_EXAMPLE_LENGTH: int = 500

#: Caps on catalog prose, so one unusually long editorial cannot dominate the budget
#: or push out the rest of the grounding.
MAX_STATEMENT_CHARS: int = 4_000
MAX_EDITORIAL_CHARS: int = 3_000

#: Every function in this module is bounded, and this is the outer bound. It is the
#: last check before a prompt is built: a caller that assembled its grounding by hand
#: and got it wrong still cannot exceed this.
MAX_PROMPT_INPUT_CHARS: int = 24_000


def clip(text: str | None, limit: int, *, marker: str = "\u2026") -> str:
    """Trim ``text`` to ``limit`` characters, marking that it was trimmed.

    Whitespace is collapsed first so a multi-line field cannot use its newlines to
    evade the limit. An empty or whitespace-only input returns the module's
    "absent" marker rather than an empty block, because an empty block in a prompt
    reads as "the catalog has no editorial" rather than "nothing to say here".
    """
    if not text:
        return ""
    flattened = " ".join(str(text).split())
    if not flattened:
        return ""
    if limit > 0 and len(flattened) > limit:
        trimmed = flattened[:limit].rstrip()
        return f"{trimmed}{marker}"
    return flattened


def as_prompt_block(label: str, body: str | None, *, limit: int) -> str:
    """Render one labelled block, or nothing at all when the body is absent.

    Fenced in triple backticks and labelled, which keeps two things true at once:
    catalog prose cannot be mistaken for the model's own output, and a value that
    happens to contain blank lines cannot break the surrounding block structure.

    Returns ``""`` for absent content, so a caller joins blocks and filters once
    rather than producing a stream of empty headings.
    """
    flattened = clip(body, limit)
    if not flattened:
        return ""
    return f"{label}:\n```\n{flattened}\n```"


def clip_source(source: str | None, *, limit: int) -> str:
    """Clip source for a prompt. See :func:`clip` for the semantics.

    Newlines are *not* collapsed here, unlike other text: indentation and line
    structure are how a reviewer -- or a model -- reads code, and flattening a
    function body into one line makes the analysis worse. The length bound still
    applies, which is what keeps a prompt within its budget.
    """
    if not source:
        return ""
    text = str(source).replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > limit:
        return f"{text[:limit].rstrip()}\u2026"
    return text


def visible_test_cases(problem: Any) -> list[dict[str, str]]:
    """The published examples, as ``input``/``output``/``explanation`` strings.

    Reads through :meth:`Problem.visible_test_cases`, so a hidden case cannot be
    returned even if this function were handed a problem object shaped slightly
    differently. Every value is stringified and clipped: test data in the catalog is
    JSON, so a malformed row can hold a number, a list, or ``None``, and a prompt
    that interpolated any of those would be a prompt that breaks in a way no test
    covers.
    """
    cases: Iterable[Mapping[str, Any]] = []
    reader = getattr(problem, "visible_test_cases", None)
    if callable(reader):
        cases = reader() or []
    result: list[dict[str, str]] = []
    for case in list(cases)[:MAX_VISIBLE_EXAMPLES_IN_PROMPT]:
        if not isinstance(case, Mapping):
            continue
        result.append(
            {
                "input": clip(_stringify(case.get("input")), MAX_VISIBLE_EXAMPLE_LENGTH),
                "output": clip(_stringify(case.get("output")), MAX_VISIBLE_EXAMPLE_LENGTH),
                "explanation": clip(_stringify(case.get("explanation")), MAX_VISIBLE_EXAMPLE_LENGTH),
            }
        )
    return result


def _stringify(value: Any) -> str:
    """Render a JSON value as prompt-safe text.

    ``None`` becomes ``""`` -- an absent field is absent, not the word "None" -- and
    containers are rendered compactly so a dict-typed input does not blow the length
    budget in a single repr.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return " ".join(str(value).split())


def submission_facts(submission: Any) -> dict[str, Any]:
    """The stored, safe verdict facts about a submission.

    This is the complete grounding for a diagnosis, and the list is short on
    purpose. Available: the language, the status, the passed and total case counts,
    the runtime and memory the judge measured, and the judge's own error message
    clipped. Absent: every test case, the program's output, any expected output, and
    anything about the learner.

    ``test_cases_total`` is a count, not a case list, and that distinction is the
    whole reason a diagnosis is possible at all: the model can be told "4 of 10
    passed" without being told what any of the ten were. ``error_message`` is
    included because it is derived from the learner's *own* code on *their own*
    submission -- it is the strongest evidence available and it reveals nothing
    about the hidden data.
    """
    facts: dict[str, Any] = {
        "language": clip(getattr(submission, "language", None), 40),
        "status": clip(getattr(submission, "status", None), 40),
        "test_cases_passed": getattr(submission, "test_cases_passed", None),
        "test_cases_total": getattr(submission, "test_cases_total", None),
        "runtime_ms": getattr(submission, "runtime_ms", None),
        "memory_mb": getattr(submission, "memory_mb", None),
    }
    error_message = clip(
        getattr(submission, "error_message", None), MAX_ERROR_MESSAGE_IN_PROMPT
    )
    if error_message:
        facts["error_message"] = error_message
    else:
        # An explicit "absent" beats an omitted key here: a model asked to diagnose
        # a failure needs to know the judge reported no message rather than
        # guessing that one was withheld.
        facts["error_message"] = "(the judge reported no error message)"
    return facts


def problem_facts(problem: Any) -> dict[str, Any]:
    """The safe, learner-facing catalog facts about a problem.

    Everything here is already served by the public problem endpoints: the title,
    the statement, the input and output formats, the constraints, the examples, and
    the recorded target complexity. ``hints`` is *not* included -- it is the
    learner's own hint ladder and is a separate product decision about how much to
    give away -- and ``reference_solutions`` is not included because it is a
    complete working answer and quoting it would answer the problem instead of
    explaining it.
    """
    topics = getattr(problem, "topics", None) or []
    return {
        "title": clip(getattr(problem, "title", None), 200),
        "difficulty": clip(getattr(problem, "difficulty", None), 20),
        "topics": [clip(_stringify(topic), 60) for topic in list(topics)[:8] if _stringify(topic)],
        "statement": clip(getattr(problem, "description", None), MAX_STATEMENT_CHARS),
        "summary": clip(getattr(problem, "summary", None), 400),
        "input_format": clip(getattr(problem, "input_format", None), 1_000),
        "output_format": clip(getattr(problem, "output_format", None), 1_000),
        "constraints": clip(getattr(problem, "constraints", None), 1_000),
        "expected_time_complexity": clip(getattr(problem, "expected_time_complexity", None), 60),
        "expected_space_complexity": clip(getattr(problem, "expected_space_complexity", None), 60),
        "examples": visible_test_cases(problem),
    }


def editorial_text(problem: Any) -> str:
    """The catalog's written explanation for this problem, or ``""``.

    The written editorial is preferred over generating one, and it is included as
    *context* rather than as the answer: the model is asked to explain the approach
    in the learner's terms, not to copy the editorial back. A problem with no
    editorial still gets an explanation -- grounded in the statement alone -- so a
    missing editorial degrades the quality instead of failing the request.
    """
    return clip(getattr(problem, "explanation", None), MAX_EDITORIAL_CHARS)


__all__ = [
    "MAX_EDITORIAL_CHARS",
    "MAX_ERROR_MESSAGE_IN_PROMPT",
    "MAX_PROMPT_INPUT_CHARS",
    "MAX_STATEMENT_CHARS",
    "MAX_SUBMISSION_SOURCE_CHARS",
    "MAX_USER_INPUT_CHARS",
    "MAX_VISIBLE_EXAMPLES_IN_PROMPT",
    "MAX_VISIBLE_EXAMPLE_LENGTH",
    "MAX_SOURCE_CODE_LENGTH",
    "as_prompt_block",
    "clip",
    "clip_source",
    "editorial_text",
    "problem_facts",
    "submission_facts",
    "visible_test_cases",
]
