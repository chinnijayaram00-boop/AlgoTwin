"""Prompt construction, and the cache key derived from it.

Two things live here, and they are the same thing: the rendered instructions and
the digest of those instructions. Keeping them together is deliberate. The cache
key is a hash of the exact prompt, so if the two could be produced separately then a
change to the prompt would not necessarily invalidate the cache, and the failure
would look like "the model returned a stale answer" rather than "the key was
computed over different text than the text that was sent".

Each builder returns a :class:`RenderedPrompt`, which carries the two strings, the
grounding dict that goes into the stored row, and the scope key. A caller cannot
build a prompt without also getting its key, and cannot get a key that does not
match what was sent.

**The rules stated in every system prompt**, not in one and hoped for elsewhere:

* only the content in the user message is fact;
* never state a test input, a test expected output, or a program output;
* never claim the platform ran or measured anything;
* when the grounding does not support an answer, say so.

That last one is the instruction that makes the rest of the design coherent. A
complexity analysis with no loops has no honest complexity, and a diagnosis with no
error message has no cause to report; both endpoints exist so the model can be told
"undetermined" instead of being nudged into a confident guess.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from backend.app.ai.provider import (
    KIND_CODE_COMPLEXITY,
    KIND_PROBLEM_EXPLANATION,
    KIND_SUBMISSION_DIAGNOSIS,
)

#: Every prompt begins with this, and it is stated once as a constant so a change to
#: the house rules is a visible one-line diff that applies to all three endpoints
#: rather than an edit to three separate strings that can drift.
_BASE_SYSTEM_RULES = """You are the AlgoTwin coach. You are talking to a learner who is \
practising data structures and algorithms, and you are precise rather than encouraging \
at the expense of being correct.

These rules are absolute:

1. The only facts you may use are the ones in the learner message below. Anything you \
believe you know about this problem from your own training is unverified for this \
platform's catalog and must not be asserted.
2. Never state a test case's input, a test case's expected output, or a program's output \
on a test case. None of that data is available to you and none of it may be guessed.
3. Never claim that you ran, executed, timed, or measured anything. You are reading a \
recorded verdict; the numbers in it were measured by AlgoTwin's judge, not by you.
4. If the grounding does not support an answer, say so plainly and say what is missing. \
An honest "undetermined" is more useful to a learner than a confident guess, and guessing \
is treated as an error.
5. Address the learner directly, at their level, and keep it to the point. No preamble, \
no restating the question, no closing pleasantries.
6. Use Markdown for structure: short paragraphs, `##` headings, and `backticks` for code \
and complexity notation."""

_EXPLANATION_SYSTEM = f"""{_BASE_SYSTEM_RULES}

For this request, explain a problem's intended approach. Prefer the approach the \
platform's catalog records over any approach you would have chosen yourself, and if they \
differ, say which you are explaining and why."""

_DIAGNOSIS_SYSTEM = f"""{_BASE_SYSTEM_RULES}

For this request, diagnose one recorded submission. Work only from the verdict facts \
provided. You have counts and measurements, not test data, so you can reason about *where* \
a failure is likely and *what class* of mistake it is, but you cannot know which input \
broke the program or what the expected output was. Do not pretend otherwise."""

_COMPLEXITY_SYSTEM = f"""{_BASE_SYSTEM_RULES}

For this request, analyse the time and space complexity of one program.

Reply with a single JSON object and nothing else -- no prose, no code fence, no text \
before or after it -- with exactly these keys:

  "time_complexity"  the time complexity as a string, e.g. "O(n log n)"
  "space_complexity" the space complexity as a string, e.g. "O(1)"
  "reasoning"        one or two sentences explaining how you got there

If the program has no loops, no recursion, and no data-dependent iteration, use \
"time_complexity": "undetermined" and say so in the reasoning rather than guessing a \
bound from the input size."""

_FOCUS_NOTES: dict[str, str] = {
    "approach": (
        "Focus on the approach: how a correct solution is structured, why this structure "
        "fits the problem, and what makes it correct. Do not give a full implementation."
    ),
    "correctness": (
        "Focus on correctness: what invariant the solution maintains, why it holds after "
        "each step, and why the algorithm terminates with the required output."
    ),
}


@dataclass(frozen=True)
class RenderedPrompt:
    """A fully rendered prompt plus everything the stored row needs.

    ``grounding`` is what was actually put in front of the model, in the same shape
    it was put there. It is stored on the insight row so that "what was this
    generated from?" is answerable from the record, without re-deriving a prompt that
    may since have changed.

    ``scope_key`` is the digest of ``(provider, model, kind, system, user)``. It
    deliberately excludes the user id, because the uniqueness constraint is
    ``(user_id, scope_key)`` -- two learners asking the identical question get two
    rows rather than sharing one, and neither can read the other's.
    """

    kind: str
    system: str
    user: str
    grounding: dict[str, Any] = field(default_factory=dict)
    scope_key: str = ""


def compute_scope_key(
    *, provider: str, model: str, kind: str, system: str, user: str
) -> str:
    """The cache key for one exact request.

    SHA-256 over a length-delimited join of the five parts. The delimiters matter:
    concatenating them without lengths would let a crafted prompt shift text across a
    field boundary and collide with a different request's key, and a cache that
    returns another request's answer to a learner is worse than no cache.

    One-way by construction, which matters because ``user`` contains the learner's
    source code: the digest of a prompt is stored on the row, and it must not be
    possible to recover the source from it.
    """
    parts = [provider, model, kind, system, user]
    payload = "\x00".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finalise(
    rendered: RenderedPrompt, provider: str, model: str
) -> RenderedPrompt:
    """Attach the scope key to a rendered prompt.

    Every builder goes through here, so the key can only ever be computed over the
    strings that are actually being sent. :func:`compute_scope_key` is public for
    tests, but nothing in the request path calls it directly.
    """
    return RenderedPrompt(
        kind=rendered.kind,
        system=rendered.system,
        user=rendered.user,
        grounding=rendered.grounding,
        scope_key=compute_scope_key(
            provider=provider,
            model=model,
            kind=rendered.kind,
            system=rendered.system,
            user=rendered.user,
        ),
    )


def render_explanation_prompt(
    *,
    facts: dict[str, Any],
    editorial: str,
    focus: str | None,
    provider: str,
    model: str,
) -> RenderedPrompt:
    """The prompt for a problem explanation.

    The catalog's written explanation is passed as *context for the coach*, and the
    learner message says so explicitly. A model that reads "the platform's notes on
    this problem" will explain that approach; a model that reads unattributed prose
    is more likely to blend it with its own, which is the failure this labelling
    prevents.

    ``focus`` selects an emphasis and cannot add content: it selects one of two
    fixed notes in :data:`_FOCUS_NOTES`, and an unrecognised value falls back to
    the whole approach rather than being interpolated into the prompt.
    """
    lines: list[str] = [
        f"Problem: {facts.get('title') or '(untitled)'}",
        f"Difficulty: {facts.get('difficulty') or 'unknown'}"
        + (f" | Topics: {', '.join(facts['topics'])}" if facts.get("topics") else ""),
        "",
        "PROBLEM STATEMENT",
        facts.get("statement") or facts.get("summary") or "(none recorded)",
    ]
    if facts.get("input_format"):
        lines += ["", "INPUT FORMAT", facts["input_format"]]
    if facts.get("output_format"):
        lines += ["", "OUTPUT FORMAT", facts["output_format"]]
    if facts.get("constraints"):
        lines += ["", "CONSTRAINTS", facts["constraints"]]

    examples = facts.get("examples") or []
    if examples:
        lines += ["", "PUBLISHED EXAMPLES"]
        for index, example in enumerate(examples, start=1):
            lines.append(f"Example {index}")
            lines.append(f"  input:  {example.get('input')}")
            lines.append(f"  output: {example.get('output')}")
            if example.get("explanation"):
                lines.append(f"  why:    {example['explanation']}")

    if facts.get("expected_time_complexity"):
        lines += [
            "",
            "TARGET COMPLEXITY THE CATALOG RECORDS FOR THIS PROBLEM",
            f"  time:  {facts['expected_time_complexity']}",
            f"  space: {facts.get('expected_space_complexity') or 'not recorded'}",
            "Treat this as the catalog's stated target, not as something you measured.",
        ]

    if editorial:
        lines += [
            "",
            "THE PLATFORM'S WRITTEN NOTES ON THIS PROBLEM (context for you, not an answer to copy)",
            editorial,
        ]

    note = _FOCUS_NOTES.get(focus or "", "")
    if note:
        lines += ["", "WHAT TO EMPHASISE", note]

    lines += [
        "",
        "Explain this problem's intended approach to the learner.",
    ]

    grounding = {key: value for key, value in facts.items()}
    grounding["editorial_provided"] = bool(editorial)
    grounding["focus"] = focus

    return _finalise(
        RenderedPrompt(
            kind=KIND_PROBLEM_EXPLANATION,
            system=_EXPLANATION_SYSTEM,
            user="\n".join(lines),
            grounding=grounding,
        ),
        provider,
        model,
    )


def render_diagnosis_prompt(
    *,
    submission_facts: dict[str, Any],
    problem_title: str,
    language: str,
    provider: str,
    model: str,
) -> RenderedPrompt:
    """The prompt for a submission diagnosis.

    The verdict facts are the whole grounding. The learner's source code is
    deliberately absent: including it would let a model "diagnose" by pattern
    matching a diff it can see, and would put a learner's unsent code into an
    external provider for a request where the recorded verdict is what is actually
    being asked about.

    The learner message states the count-based reasoning explicitly -- it has counts,
    not cases -- so a model that would otherwise try to name a failing input
    discovers that it is being told it cannot.
    """
    facts = submission_facts
    lines: list[str] = [
        f"Problem: {problem_title or '(untitled)'}",
        f"Language: {language}",
        "",
        "WHAT THE JUDGE RECORDED FOR THIS SUBMISSION",
        f"  status:            {facts.get('status') or 'unknown'}",
        f"  test cases passed: {facts.get('test_cases_passed') if facts.get('test_cases_passed') is not None else 'not recorded'}",
        f"  test cases run:    {facts.get('test_cases_total') if facts.get('test_cases_total') is not None else 'not recorded'}",
        f"  runtime:           {_measurement(facts.get('runtime_ms'), 'ms')}",
        f"  memory:            {_measurement(facts.get('memory_mb'), 'MB')}",
        f"  judge message:     {facts.get('error_message') or 'none'}",
        "",
        "WHAT YOU DO NOT HAVE, AND MUST NOT INVENT",
        "- No test case inputs, expected outputs, or program output. You have counts and "
        "measurements only, so you can reason about how far the submission got and what "
        "class of mistake explains that, but you cannot say which input broke it.",
        "- The learner's source code. You do not have it, so do not describe specific lines "
        "as if you had read them.",
        "- Anything about this problem from your own training. If the verdict alone is not "
        "enough to identify a cause, say what would be needed instead of asserting one.",
        "",
        "Diagnose this recorded submission for the learner.",
    ]

    grounding = {
        "problem_title": problem_title,
        "language": language,
        **{key: value for key, value in facts.items()},
        "source_code_included": False,
    }

    return _finalise(
        RenderedPrompt(
            kind=KIND_SUBMISSION_DIAGNOSIS,
            system=_DIAGNOSIS_SYSTEM,
            user="\n".join(lines),
            grounding=grounding,
        ),
        provider,
        model,
    )


def render_complexity_prompt(
    *,
    source_code: str,
    language: str,
    expected_time_complexity: str | None,
    expected_space_complexity: str | None,
    provider: str,
    model: str,
) -> RenderedPrompt:
    """The prompt for a complexity analysis.

    This is the one endpoint where the learner *wants* their code in the prompt --
    there is nothing to analyse otherwise. It is still bounded, still fenced, and
    still the only code that reaches a provider from this route.

    The catalog's target complexity is included when there is one, as a comparison
    point rather than as the expected answer, because the useful output is "here is
    your complexity, and here is the one this problem is looking for". A learner
    whose O(n log n) matches the target should be told so.
    """
    lines: list[str] = [
        f"Language: {language}",
        "",
        "ANALYSE THIS PROGRAM'S TIME AND SPACE COMPLEXITY",
        "```",
        source_code,
        "```",
    ]
    if expected_time_complexity or expected_space_complexity:
        lines += [
            "",
            "FOR REFERENCE, THE CATALOG RECORDS THIS TARGET FOR THIS PROBLEM",
            f"  time:  {expected_time_complexity or 'not recorded'}",
            f"  space: {expected_space_complexity or 'not recorded'}",
            "Compare your analysis against it if the program is a solution to this "
            "problem. State the target as the catalog's claim, not as your measurement.",
        ]
    lines += [
        "",
        "Reply with the JSON object described in your instructions, and nothing else.",
    ]

    grounding = {
        "language": language,
        "source_length_chars": len(source_code),
        "expected_time_complexity": expected_time_complexity,
        "expected_space_complexity": expected_space_complexity,
    }

    return _finalise(
        RenderedPrompt(
            kind=KIND_CODE_COMPLEXITY,
            system=_COMPLEXITY_SYSTEM,
            user="\n".join(lines),
            grounding=grounding,
        ),
        provider,
        model,
    )


def _measurement(value: Any, unit: str) -> str:
    """Render an optional measurement, distinguishing "absent" from zero."""
    if value is None:
        return "not measured"
    return f"{value} {unit}"


__all__ = [
    "RenderedPrompt",
    "compute_scope_key",
    "render_complexity_prompt",
    "render_diagnosis_prompt",
    "render_explanation_prompt",
]
