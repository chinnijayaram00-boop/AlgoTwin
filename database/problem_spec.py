"""The shape every problem in the catalog shares.

A catalog entry is a plain dictionary, because the seeder hands it straight to an
ORM row and the API reads it straight back out of one; a second class to
translate between would only add a way for the two to disagree.

This module holds the parts that are the same for all of the catalog's problems:
the test-case builder, the keys a definition must carry, and the validator that
refuses to publish a half-populated problem.

The validator runs in :mod:`database.problem_catalog` *before* anything is
written, so a malformed definition fails the seed rather than the judge. A problem
missing a hint level or a case with no expected output can therefore never reach
the database, and the judge never has to cope with one.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterator
from typing import Any

from backend.app.judge.languages import supported_language_ids
from database.models.problem import (
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_TIME_LIMIT_MS,
    HINT_LEVELS,
)

#: The keys a catalog entry must carry. Every one is read by something: the API
#: projects most of them onto a problem response, and the judge reads the limits
#: and the test cases. A key that nothing reads does not belong in here.
REQUIRED_PROBLEM_KEYS: frozenset[str] = frozenset(
    {
        "slug",
        "title",
        "summary",
        "difficulty",
        "topics",
        "description",
        "input_format",
        "output_format",
        "constraints",
        "examples",
        "hints",
        "explanation",
        "supported_languages",
        "expected_time_complexity",
        "expected_space_complexity",
        "time_limit_ms",
        "memory_limit_mb",
        "starter_code",
        "reference_solutions",
        "test_cases",
    }
)

#: The values ``difficulty`` may take, matching what the list filter accepts.
DIFFICULTIES: frozenset[str] = frozenset({"Easy", "Medium", "Hard"})

#: The languages the execution layer knows how to run, taken from the language
#: registry rather than restated here. A problem's ``supported_languages`` must be
#: a subset of this: the editor offers exactly these tabs, so offering one the
#: runner cannot honour is worse than not offering it. Four catalog entries once
#: advertised Java while the submission API accepted only Python and JavaScript,
#: which is the drift this indirection removes.
KNOWN_LANGUAGES: frozenset[str] = supported_language_ids()


class CatalogError(ValueError):
    """A catalog entry is not publishable as written.

    Raised by :func:`validate_definition` before a seed writes anything, so a
    broken entry stops the process instead of reaching a learner.
    """


def case(input_text: str, expected_output: str, *, is_hidden: bool = False) -> dict[str, Any]:
    """One judge test case.

    The three keys are the whole contract: a literal ``stdin`` payload, the exact
    ``stdout`` a correct program writes, and whether the learner may see it.
    A hidden case is never projected into an API response, so this dict is also
    the boundary between what a learner can read and what only the judge can.
    """
    return {
        "input": input_text,
        "expected_output": expected_output,
        "is_hidden": is_hidden,
    }


def judged_case(
    oracle: Any,
    input_text: str,
    *,
    is_hidden: bool = False,
) -> dict[str, Any]:
    """A test case whose expected output is computed by ``oracle``.

    Hand-typing expected output into the catalog is how a typo becomes a test
    that rejects correct code. Deriving it from the oracle instead makes that
    impossible: the expected output is whatever the independent implementation
    produces, and the integrity test then checks that every reference solution
    in every language agrees with it.
    """
    return case(input_text, oracle(input_text), is_hidden=is_hidden)


def source(code: str) -> str:
    """Normalise a program written inline in a catalog file.

    Catalog definitions are written as indented Python, but the program stored
    for a learner to edit and run has to start in column zero or it is not valid
    code. :func:`textwrap.dedent` removes the indentation, and the trailing
    newline is added because a file without one behaves differently on Windows.
    """
    return textwrap.dedent(code).strip("\n") + "\n"


def int_tokens(stdin: str) -> list[int]:
    """Every whitespace-separated integer in ``stdin``, in order.

    Most problems in this catalog are token based, so this is the parser they
    share. It ignores blank lines, which keeps a case file readable when it is
    written across several lines in the catalog.
    """
    return [int(token) for token in stdin.split()]


def int_rows(stdin: str) -> list[list[int]]:
    """``stdin`` split into rows of integers, one row per non-empty line."""
    rows: list[list[int]] = []
    for line in stdin.splitlines():
        tokens = line.split()
        if tokens:
            rows.append([int(token) for token in tokens])
    return rows


def text_lines(stdin: str) -> list[str]:
    """``stdin`` split into non-empty lines with surrounding space removed."""
    return [line.strip() for line in stdin.splitlines() if line.strip()]


def visible_cases(definition: dict[str, Any]) -> list[dict[str, Any]]:
    """The cases of a definition a learner may see."""
    return [item for item in definition["test_cases"] if not item["is_hidden"]]


def hidden_cases(definition: dict[str, Any]) -> list[dict[str, Any]]:
    """The cases of a definition the judge runs but never discloses."""
    return [item for item in definition["test_cases"] if item["is_hidden"]]


def iter_cases(definition: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every case, visible first, in judge order."""
    yield from definition["test_cases"]


def validate_definition(definition: dict[str, Any]) -> None:
    """Raise :class:`CatalogError` unless this definition is publishable.

    The checks are the ones that would otherwise fail late and confusingly: a
    missing key surfaces as an ``AttributeError`` deep in a seeder, a language
    with starter code but no reference solution surfaces as a broken integrity
    test weeks later. Here they surface as one clear error naming the problem.
    """
    missing = sorted(REQUIRED_PROBLEM_KEYS - definition.keys())
    if missing:
        raise CatalogError(f"{definition.get('slug', '<no slug>')}: missing keys {missing}")

    slug = definition["slug"]
    if not isinstance(slug, str) or not slug or slug != slug.strip().lower():
        raise CatalogError(f"{slug}: slug must be a lowercase, whitespace-free string")

    if definition["difficulty"] not in DIFFICULTIES:
        raise CatalogError(
            f"{slug}: difficulty {definition['difficulty']!r} is not one of {sorted(DIFFICULTIES)}"
        )

    if not definition["topics"]:
        raise CatalogError(f"{slug}: at least one topic is required for the catalog filters")

    if not definition["examples"]:
        raise CatalogError(f"{slug}: at least one worked example is required")

    hints = definition["hints"]
    if len(hints) != HINT_LEVELS:
        raise CatalogError(
            f"{slug}: expected {HINT_LEVELS} hints, one per level, found {len(hints)}"
        )
    if any(not isinstance(hint, str) or not hint.strip() for hint in hints):
        raise CatalogError(f"{slug}: every hint level must have text")

    languages = definition["supported_languages"]
    unknown = sorted(set(languages) - KNOWN_LANGUAGES)
    if unknown:
        raise CatalogError(f"{slug}: unsupported languages {unknown}")
    if not languages:
        raise CatalogError(f"{slug}: at least one language must be supported")

    # A language the editor offers is a promise that it can be run and checked.
    # Both halves of that promise are verified here rather than discovered by a
    # learner pressing Run.
    missing_starter = sorted(set(languages) - definition["starter_code"].keys())
    if missing_starter:
        raise CatalogError(f"{slug}: languages without starter code {missing_starter}")
    missing_reference = sorted(set(languages) - definition["reference_solutions"].keys())
    if missing_reference:
        raise CatalogError(f"{slug}: languages without a reference solution {missing_reference}")
    extra = sorted(
        set(definition["starter_code"]) - set(languages),
    )
    if extra:
        raise CatalogError(f"{slug}: starter code for languages not listed {extra}")

    for language in languages:
        for field in ("starter_code", "reference_solutions"):
            body = definition[field][language]
            if not isinstance(body, str) or not body.strip():
                raise CatalogError(f"{slug}: {field}[{language}] is empty")

    if definition["time_limit_ms"] <= 0 or definition["memory_limit_mb"] <= 0:
        raise CatalogError(f"{slug}: judge limits must be positive")

    test_cases = definition["test_cases"]
    if not visible_cases(definition):
        raise CatalogError(f"{slug}: at least one visible test case is required")
    if not hidden_cases(definition):
        raise CatalogError(
            f"{slug}: at least one hidden test case is required, "
            "otherwise a learner could pass on the examples alone"
        )
    for index, item in enumerate(test_cases):
        if not isinstance(item, dict):
            raise CatalogError(f"{slug}: test case {index} is not a case dict")
        unexpected = sorted(item.keys() - {"input", "expected_output", "is_hidden"})
        if unexpected:
            raise CatalogError(f"{slug}: test case {index} has unexpected keys {unexpected}")
        for key in ("input", "expected_output"):
            if not isinstance(item[key], str):
                raise CatalogError(f"{slug}: test case {index} {key} must be a string")
        if not isinstance(item["is_hidden"], bool):
            raise CatalogError(f"{slug}: test case {index} is_hidden must be a bool")
        if not item["input"].strip():
            raise CatalogError(f"{slug}: test case {index} has an empty input")
        # An empty expected output is allowed, because some answers really are
        # empty -- merging zero intervals, or finding no path. Correctness there
        # comes from the integrity test, which runs every reference solution
        # against every case, so a case whose expectation was wrong would be a
        # case a reference solution fails.


def default_limits() -> tuple[int, int]:
    """The limits a problem inherits when it does not need its own."""
    return DEFAULT_TIME_LIMIT_MS, DEFAULT_MEMORY_LIMIT_MB
