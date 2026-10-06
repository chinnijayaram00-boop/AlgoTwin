"""The problem catalog, and the one path that writes it to the database.

`database/problem_defs/` holds the definitions; this module collects them, refuses
to publish one that is incomplete, and reconciles the set with the ``problems``
table. It exists as a separate module from `database.seed` because the catalog is
a first-class thing with a validator, not a side effect of demo seeding: a
deployment that sets ``SEED_DEMO_DATA=false`` still needs its catalog.

Two properties the rest of the platform depends on are established here:

* **Validation happens before the first write.** Every definition is checked by
  :func:`database.problem_spec.validate_definition` while the session is still
  empty, so a malformed entry fails the seed instead of producing a published
  problem that a judge would later choke on.
* **Reconciliation never deletes and never renumbers.** A problem already in the
  table is matched by slug and has its catalog columns rewritten in place, keeping
  its primary key. That matters because ``progress`` and ``submissions`` reference
  ``problem_id``: re-inserting a problem to refresh it would orphan every record
  a learner had for it.

Nothing here executes code. The reference solutions in a definition are stored so
:mod:`backend.tests.test_judge` can check the catalog against them offline; the API
never runs them.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Problem
from database.problem_defs.arrays import ARRAYS_PROBLEMS
from database.problem_defs.binary_search import BINARY_SEARCH_PROBLEMS
from database.problem_defs.dynamic_programming import DYNAMIC_PROGRAMMING_PROBLEMS
from database.problem_defs.graphs import GRAPHS_PROBLEMS
from database.problem_defs.greedy import GREEDY_PROBLEMS
from database.problem_defs.heaps import HEAPS_PROBLEMS
from database.problem_defs.linked_lists import LINKED_LISTS_PROBLEMS
from database.problem_defs.math_and_bits import MATH_AND_BITS_PROBLEMS
from database.problem_defs.searching_and_dp import SEARCHING_AND_DP_PROBLEMS
from database.problem_defs.sorting import SORTING_PROBLEMS
from database.problem_defs.strings_and_stacks import STRINGS_AND_STACKS_PROBLEMS
from database.problem_defs.trees import TREES_PROBLEMS
from database.problem_spec import CatalogError, validate_definition, visible_cases

#: Every catalog definition, in the order they are seeded. The order is stable so
#: a fresh database gets the same problem ids every time, which keeps a migration
#: or a support conversation reproducible.
#:
#: Modules are listed alphabetically, which also preserves the relative order of
#: the six that were seeded first: a deployment that already has rows keeps every
#: existing id, because reconciliation matches on slug and never renumbers. Six
#: modules -- binary search, dynamic programming, greedy, heaps, maths and bits,
#: sorting -- were committed with their definitions but never listed here, so
#: twenty publishable problems existed on disk and reached no learner. Listing
#: them is what turns those files from source into catalog.
CATALOG: list[dict[str, Any]] = [
    *ARRAYS_PROBLEMS,
    *BINARY_SEARCH_PROBLEMS,
    *DYNAMIC_PROGRAMMING_PROBLEMS,
    *GRAPHS_PROBLEMS,
    *GREEDY_PROBLEMS,
    *HEAPS_PROBLEMS,
    *LINKED_LISTS_PROBLEMS,
    *MATH_AND_BITS_PROBLEMS,
    *SEARCHING_AND_DP_PROBLEMS,
    *SORTING_PROBLEMS,
    *STRINGS_AND_STACKS_PROBLEMS,
    *TREES_PROBLEMS,
]

#: The columns a definition owns. Everything else on a problem row -- its id, when
#: it was created, and whether it is published -- belongs to the application or to
#: an administrator, so reconciliation leaves it alone.
CATALOG_COLUMNS: tuple[str, ...] = (
    "title",
    "summary",
    "difficulty",
    "topics",
    "examples",
    "constraints",
    "starter_code",
    "description",
    "input_format",
    "output_format",
    "hints",
    "explanation",
    "supported_languages",
    "expected_time_complexity",
    "expected_space_complexity",
    "time_limit_ms",
    "memory_limit_mb",
    "test_cases",
    "reference_solutions",
)


def validate_catalog(definitions: list[dict[str, Any]] | None = None) -> None:
    """Raise :class:`CatalogError` unless the whole catalog is publishable.

    Called by the seeder before anything is written, and by the catalog integrity
    test. The duplicate-slug check lives here rather than in
    :func:`~database.problem_spec.validate_definition` because a single definition
    cannot know about its neighbours, and two definitions sharing a slug would
    otherwise seed into one row with the second silently overwriting the first.
    """
    candidates = CATALOG if definitions is None else definitions
    seen: set[str] = set()
    for definition in candidates:
        validate_definition(definition)
        slug = definition["slug"]
        if slug in seen:
            raise CatalogError(f"{slug}: the catalog defines this slug more than once")
        seen.add(slug)


def _apply(problem: Problem, definition: dict[str, Any]) -> None:
    """Copy a definition's columns onto an existing row."""
    for column in CATALOG_COLUMNS:
        setattr(problem, column, definition[column])


def sync_catalog(session: Session, definitions: list[dict[str, Any]] | None = None) -> list[Problem]:
    """Reconcile the ``problems`` table with the catalog and return every row.

    New definitions are inserted and published, because an unpublished catalog
    entry is not reachable through the public problem endpoints and a learner
    would have no way to find it. An existing problem keeps its ``is_published``
    value: reconciliation is here to keep catalog data current, and silently
    unpublishing -- or publishing -- a problem somebody has already been working
    on is a decision that belongs to whoever owns the deployment.
    """
    validate_catalog(definitions)
    candidates = CATALOG if definitions is None else definitions

    existing = {problem.slug: problem for problem in session.scalars(select(Problem)).all()}

    created: list[Problem] = []
    for definition in candidates:
        problem = existing.get(definition["slug"])
        if problem is None:
            problem = Problem(slug=definition["slug"], is_published=True)
            session.add(problem)
            created.append(problem)
        _apply(problem, definition)

    session.commit()

    # Read back rather than returning the in-memory objects: a caller that reports
    # "N problems" should be reporting what the database now holds.
    return list(session.scalars(select(Problem).order_by(Problem.id)).all())


def describe_catalog() -> str:
    """A one-line summary for a log or a test failure message."""
    cases = sum(len(definition["test_cases"]) for definition in CATALOG)
    visible = sum(len(visible_cases(definition)) for definition in CATALOG)
    return (
        f"{len(CATALOG)} problems, {cases} cases "
        f"({visible} visible, {cases - visible} hidden)"
    )


__all__ = [
    "CATALOG",
    "CATALOG_COLUMNS",
    "describe_catalog",
    "sync_catalog",
    "validate_catalog",
]
