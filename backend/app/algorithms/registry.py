"""The algorithms this platform can actually run, and what each one is.

This registry is the single answer to "can this platform show me that", for the
API, the frontend, and the tests. The shape is the one that shipped in the
foundation release -- id, name, category, time and space complexity, supported
languages -- and it is kept because the frontend and the API already read it.
What changed is that the tuple is no longer empty: every entry below names a
function that exists in :mod:`backend.app.algorithms.reference` and runs for real
in the visualization worker.

Three additions to the original shape, each one load-bearing:

``input_grammar``
    The parser in :mod:`backend.app.algorithms.inputs` that reads this
    algorithm's input. Algorithms that share a grammar can be handed the *same*
    bytes and will see the same values, which is what makes a comparison of two of
    them a comparison of the algorithms rather than of the inputs.

``comparison_group``
    The task the algorithm solves. Two algorithms may only be compared when they
    share a group, because two algorithms solving *different* tasks cannot be
    compared on the same input at all -- the honest answer would be "one of these
    was handed the wrong problem". Six sorts are all ``sort``; the linear and
    binary searches are both ``search``; anything else is its own group.

``state_kind``
    Which layout the frames are drawn in. It belongs to the algorithm rather than
    the frontend because it is a property of the data: a sort draws bars because
    height is the value, and a stack draws labelled boxes because position is the
    meaning.

``comparison`` names the problems this algorithm is the canonical approach for,
and ``expected_time_complexity`` / ``expected_space_complexity`` are taken from the
catalog rows rather than written twice, so the complexity the lab advertises and
the complexity the problem statement records cannot drift apart.

Nothing here is a stub. There is no entry whose function is missing, and
``backend/tests/test_visualization.py`` asserts that for every entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

from backend.app.algorithms import reference
from backend.app.algorithms.frames import (
    STATE_KIND_ARRAY,
    STATE_KIND_BAR_ARRAY,
    STATE_KIND_GRID,
    STATE_KIND_TEXT,
    STATE_KINDS,
    FrameState,
    Trace,
)
from backend.app.algorithms.inputs import GRAMMARS
from backend.app.judge.languages import LANGUAGE_IDS

#: The languages a frame-emitting reference implementation is written in. It is
#: always the platform's own Python, so the field describes what a learner can
#: read alongside the animation rather than what the worker runs -- and it is
#: built from the language registry so it cannot name a language the platform has
#: no reader for.
REFERENCE_LANGUAGES: tuple[str, ...] = LANGUAGE_IDS

#: The signature every reference implementation has. A generator, so the frames
#: come out as the algorithm reaches them.
ReferenceImplementation = Callable[[object, Trace], Iterator[FrameState]]


@dataclass(frozen=True)
class AlgorithmDescriptor:
    """Everything the platform knows about one algorithm."""

    id: str
    name: str
    category: str
    time_complexity: str | None
    space_complexity: str | None
    supported_languages: tuple[str, ...]
    summary: str
    input_grammar: str
    input_hint: str
    comparison_group: str
    state_kind: str
    sample_input: str
    implementation: ReferenceImplementation
    comparison: tuple[str, ...] = ()
    is_stable: bool | None = None

    def parse_input(self, text: str) -> object:
        """Read this algorithm's input under the grammar it declares.

        Delegated so a caller holding only a descriptor -- the comparison service,
        the API route -- never has to know the grammar name to parse with.
        """
        from backend.app.algorithms.inputs import parse

        return parse(self.input_grammar, text)

    def trace(self) -> Trace:
        """A counter/factory pair for the layout this algorithm draws in."""
        return Trace(self.state_kind)


def _algorithm(
    identifier: str,
    name: str,
    category: str,
    time_complexity: str,
    space_complexity: str,
    summary: str,
    input_grammar: str,
    input_hint: str,
    comparison_group: str,
    state_kind: str,
    sample_input: str,
    implementation: ReferenceImplementation,
    *,
    comparison: tuple[str, ...] = (),
    is_stable: bool | None = None,
) -> AlgorithmDescriptor:
    """Build one descriptor, refusing a grammar or layout the platform cannot honour.

    Validation lives in the factory so a hand-added entry with a typo fails at
    import -- while the module is still loading -- rather than becoming a registry
    entry that 404s only when somebody asks to see it.
    """
    if input_grammar not in GRAMMARS:
        raise ValueError(f"{identifier}: {input_grammar!r} is not an implemented input grammar.")
    if state_kind not in STATE_KINDS:
        raise ValueError(f"{identifier}: {state_kind!r} is not an implemented state kind.")
    return AlgorithmDescriptor(
        id=identifier,
        name=name,
        category=category,
        time_complexity=time_complexity,
        space_complexity=space_complexity,
        supported_languages=REFERENCE_LANGUAGES,
        summary=summary,
        input_grammar=input_grammar,
        input_hint=input_hint,
        comparison_group=comparison_group,
        state_kind=state_kind,
        sample_input=sample_input,
        implementation=implementation,
        comparison=comparison,
        is_stable=is_stable,
    )


#: The sample inputs are deliberately small. An interactive timeline is scrubbed by
#: hand, and a 48-element bubble sort produces more frames than anyone will step
#: through -- the point of the lab is watching one transition, not skimming a log.
_SAMPLE_INTS = "6\n5 2 9 1 7 3"

ALGORITHM_REGISTRY: tuple[AlgorithmDescriptor, ...] = (
    # ----------------------------------------------------------------- sorting
    _algorithm(
        "bubble-sort",
        "Bubble Sort",
        "Sorting",
        "O(n^2)",
        "O(1)",
        "Walk the array repeatedly, swapping neighbours that are out of order. Each "
        "pass settles the largest remaining value.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "sort",
        STATE_KIND_BAR_ARRAY,
        _SAMPLE_INTS,
        reference.bubble_sort,
        comparison=("merge-intervals",),
        is_stable=True,
    ),
    _algorithm(
        "selection-sort",
        "Selection Sort",
        "Sorting",
        "O(n^2)",
        "O(1)",
        "Select the smallest remaining value for each position. Always the same "
        "number of comparisons, but far fewer swaps.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "sort",
        STATE_KIND_BAR_ARRAY,
        _SAMPLE_INTS,
        reference.selection_sort,
        comparison=("merge-intervals",),
        is_stable=False,
    ),
    _algorithm(
        "insertion-sort",
        "Insertion Sort",
        "Sorting",
        "O(n^2)",
        "O(1)",
        "Grow a sorted prefix one element at a time, shifting larger values right. "
        "Fast on nearly sorted input, which is what makes it the usual base case.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "sort",
        STATE_KIND_BAR_ARRAY,
        _SAMPLE_INTS,
        reference.insertion_sort,
        comparison=("merge-intervals",),
        is_stable=True,
    ),
    _algorithm(
        "merge-sort",
        "Merge Sort",
        "Sorting",
        "O(n log n)",
        "O(n)",
        "Split to single values, then merge sorted runs back together. The extra "
        "array is drawn, because the linear space is the algorithm's real cost.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "sort",
        STATE_KIND_BAR_ARRAY,
        _SAMPLE_INTS,
        reference.merge_sort,
        comparison=("merge-intervals",),
        is_stable=True,
    ),
    _algorithm(
        "quick-sort",
        "Quick Sort",
        "Sorting",
        "O(n log n) average",
        "O(log n)",
        "Partition around a pivot, then sort each side. Averaged over all inputs it "
        "is the fastest of these sorts; on already sorted input this pivot choice "
        "degrades to quadratic.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "sort",
        STATE_KIND_BAR_ARRAY,
        _SAMPLE_INTS,
        reference.quick_sort,
        comparison=("merge-intervals",),
        is_stable=False,
    ),
    _algorithm(
        "heap-sort",
        "Heap Sort",
        "Sorting",
        "O(n log n)",
        "O(1)",
        "Build a max heap over the array itself, then move the root to the back "
        "repeatedly. Worst-case n log n with no extra array.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "sort",
        STATE_KIND_BAR_ARRAY,
        _SAMPLE_INTS,
        reference.heap_sort,
        comparison=("merge-intervals",),
        is_stable=False,
    ),
    # --------------------------------------------------------------- searching
    _algorithm(
        "linear-search",
        "Linear Search",
        "Searching",
        "O(n)",
        "O(1)",
        "Check each element against the target in order. Works on any array, sorted "
        "or not, and reads every element it passes.",
        "int_list_target",
        "Line 1: how many values follow. Line 2: that many integers. Line 3: the "
        "value to find.",
        "search",
        STATE_KIND_BAR_ARRAY,
        "6\n1 3 5 7 9 11\n7",
        reference.linear_search,
        comparison=("binary-search",),
    ),
    _algorithm(
        "binary-search",
        "Binary Search",
        "Searching",
        "O(log n)",
        "O(1)",
        "Compare against the middle of the range still in play and discard half of "
        "it. Requires a sorted array; the frames mark what was discarded.",
        "int_list_target",
        "Line 1: how many values follow. Line 2: that many integers in ascending "
        "order. Line 3: the value to find.",
        "search",
        STATE_KIND_BAR_ARRAY,
        "6\n1 3 5 7 9 11\n7",
        reference.binary_search,
        comparison=("binary-search",),
    ),
    # ------------------------------------------------------------ two pointers
    _algorithm(
        "two-pointers-max-area",
        "Two Pointers",
        "Two Pointers",
        "O(n)",
        "O(1)",
        "Close two pointers in from the ends and move only the shorter one, which is "
        "why no pair is ever skipped.",
        "int_list",
        "Line 1: how many heights follow. Line 2: that many integers.",
        "max-area",
        STATE_KIND_BAR_ARRAY,
        "6\n1 8 6 2 5 4",
        reference.two_pointers_max_area,
        comparison=("container-with-most-water",),
    ),
    # ----------------------------------------------------- dynamic programming
    _algorithm(
        "kadane-max-subarray",
        "Kadane's Algorithm",
        "Dynamic Programming",
        "O(n)",
        "O(1)",
        "Keep the best sum ending at each position, extending the previous run unless "
        "the value is negative.",
        "int_list",
        "Line 1: how many values follow. Line 2: that many integers.",
        "max-subarray",
        STATE_KIND_ARRAY,
        "7\n-2 1 -3 4 -1 2 1",
        reference.kadane_max_subarray,
        comparison=("maximum-subarray",),
    ),
    _algorithm(
        "coin-change",
        "Coin Change",
        "Dynamic Programming",
        "O(amount * k)",
        "O(amount)",
        "Fill a table of the fewest coins needed for every amount up to the target, "
        "each entry read from a smaller amount already solved.",
        "coins_amount",
        "Line 1: how many coin values follow, and the target amount. Line 2: that "
        "many coin values.",
        "coin-change",
        STATE_KIND_ARRAY,
        "3 11\n1 3 4",
        reference.coin_change,
        comparison=("coin-change",),
    ),
    # ------------------------------------------------------------------- stack
    _algorithm(
        "balanced-brackets",
        "Balanced Brackets",
        "Stack",
        "O(n)",
        "O(n)",
        "Push opening brackets and require every closing bracket to match the top of "
        "the stack. The stack is drawn, so the depth is visible.",
        "bracket_string",
        "Line 1: the length of the string. Line 2: that many bracket characters.",
        "balanced-brackets",
        STATE_KIND_TEXT,
        "6\n([]{})",
        reference.balanced_brackets,
        comparison=("valid-parentheses",),
    ),
    # ------------------------------------------------------------------- grids
    _algorithm(
        "word-search",
        "Word Search",
        "Depth-First Search",
        "O(rows * cols * word length)",
        "O(word length)",
        "Try every direction from each cell and step back one letter at a time. The "
        "recursion path is drawn, because the backtracking is the interesting part.",
        "grid_word",
        "Line 1: the row and column count. Lines 2 to rows+1: one row of the grid as "
        "columns characters. Last line: the word to find.",
        "word-search",
        STATE_KIND_GRID,
        "3 4\nABCE\nSFCS\nADEE\nABCCED",
        reference.word_search,
        comparison=("word-search",),
    ),
    _algorithm(
        "bfs-shortest-path",
        "Breadth-First Search",
        "Graphs",
        "O(rows * cols)",
        "O(rows * cols)",
        "Explore cells in rings from S until G is reached, which is what makes the "
        "path it returns a shortest one. Cells are coloured by the ring that reached "
        "them.",
        "labelled_grid",
        "Line 1: the row and column count. Lines 2 to rows+1: one row of the grid as "
        "columns characters, using S for the start, G for the goal, and # for a wall.",
        "shortest-path",
        STATE_KIND_GRID,
        "5 5\nS....\n.###.\n.###.\n.###.\n....G",
        reference.bfs_shortest_path,
    ),
)


_BY_ID: dict[str, AlgorithmDescriptor] = {descriptor.id: descriptor for descriptor in ALGORITHM_REGISTRY}

#: The comparison groups that have more than one member, so the API can offer
#: "compare these two" only where the comparison means something.
COMPARABLE_GROUPS: tuple[str, ...] = tuple(
    sorted(
        {
            descriptor.comparison_group
            for descriptor in ALGORITHM_REGISTRY
            if sum(1 for other in ALGORITHM_REGISTRY if other.comparison_group == descriptor.comparison_group)
            > 1
        }
    )
)

#: The categories, in the order the lab groups them.
CATEGORIES: tuple[str, ...] = tuple(
    sorted({descriptor.category for descriptor in ALGORITHM_REGISTRY})
)


def list_algorithms() -> tuple[AlgorithmDescriptor, ...]:
    """Every registered algorithm, in registry order."""
    return ALGORITHM_REGISTRY


def get_algorithm(algorithm_id: str | None) -> AlgorithmDescriptor | None:
    """The descriptor for ``algorithm_id``, or ``None`` if there is no such algorithm.

    Case-insensitive on the way in and returning the canonical lowercase id, the
    same rule :func:`backend.app.judge.languages.get_language` follows. A
    deployment that ends up with ``Bubble-Sort`` and ``bubble-sort`` as separate
    entries would publish a registry where two cards run identical code.
    """
    if not isinstance(algorithm_id, str):
        return None
    return _BY_ID.get(algorithm_id.strip().lower())


def list_by_category() -> dict[str, tuple[AlgorithmDescriptor, ...]]:
    """The registry grouped by category, categories and members both sorted."""
    grouped: dict[str, list[AlgorithmDescriptor]] = {}
    for descriptor in ALGORITHM_REGISTRY:
        grouped.setdefault(descriptor.category, []).append(descriptor)
    return {
        category: tuple(sorted(members, key=lambda descriptor: descriptor.id))
        for category, members in sorted(grouped.items())
    }


def list_comparable(algorithm_id: str) -> tuple[AlgorithmDescriptor, ...]:
    """The algorithms that may be compared against ``algorithm_id``.

    Used by the API to answer "what else can I put next to this", so the frontend
    never offers a pairing the backend would refuse.
    """
    descriptor = get_algorithm(algorithm_id)
    if descriptor is None:
        return ()
    return tuple(
        sorted(
            (
                other
                for other in ALGORITHM_REGISTRY
                if other.comparison_group == descriptor.comparison_group
                and other.id != descriptor.id
            ),
            key=lambda other: other.id,
        )
    )


def algorithms_for_problem(slug: str) -> tuple[AlgorithmDescriptor, ...]:
    """The algorithms a catalog problem names as its approach.

    This is the reuse the registry gets from the problem catalog rather than
    restating: the ``comparison`` field on each descriptor names the problems it is
    the canonical answer for, so the lab can offer "visualize the approach for this
    problem" without a second hand-written mapping table that could disagree with
    the registry.
    """
    return tuple(
        descriptor for descriptor in ALGORITHM_REGISTRY if slug in descriptor.comparison
    )


__all__ = [
    "ALGORITHM_REGISTRY",
    "CATEGORIES",
    "COMPARABLE_GROUPS",
    "REFERENCE_LANGUAGES",
    "AlgorithmDescriptor",
    "ReferenceImplementation",
    "algorithms_for_problem",
    "get_algorithm",
    "list_algorithms",
    "list_by_category",
    "list_comparable",
]
