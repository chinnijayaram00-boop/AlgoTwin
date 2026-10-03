"""The platform's own implementations of every registered algorithm.

Each function here is a **generator of real state transitions**. It is not a
scripted sequence and it does not look anything up: it performs the comparisons,
swaps, pushes, and visits that the algorithm performs, counts them as it goes, and
yields a frame at each point where the learner would want to look. Two requests
for the same algorithm on the same input produce byte-identical frames, and the
operation counters in the last frame are the operation counts of an actual run --
which is what makes them worth comparing.

The functions run in the visualization worker, never in the API process. That
boundary is not about trust, the way it is for a learner's submitted code: these
are the platform's own functions. It is about liveness. A quicksort partition that
degenerates, a breadth-first search on a large grid, or a dynamic-programming
table sized by a learner-supplied amount can each run for a very long time or
allocate without bound, and the API process has to survive that. The worker is
killed on a wall clock by its supervisor, in the same shape as
:mod:`backend.app.judge.runner`.

Every implementation follows the same three-part shape so the registry can treat
them uniformly:

1. build a :class:`~backend.app.algorithms.frames.Trace` for the layout it draws in;
2. yield a frame for the starting state;
3. yield frames as it works, then one final frame carrying ``status`` ``complete``
   and the ``result``.

The final frame's ``result`` is the only answer the module produces. There is no
second code path that computes an output without going through the animation, so
a visualization and a comparison of the same algorithm cannot disagree about what
it does.
"""

from __future__ import annotations

from typing import Iterator

from backend.app.algorithms.frames import (
    CELL_ACTIVE,
    CELL_BLOCKED,
    CELL_COMPARE,
    CELL_FRONTIER,
    CELL_IDLE,
    CELL_MATCH,
    CELL_PATH,
    CELL_PIVOT,
    CELL_SORTED,
    CELL_SWAP,
    CELL_VISITED,
    STATUS_COMPLETE,
    FrameRow,
    FrameState,
    Trace,
    format_int_list,
    grid_rows,
    make_row,
)
from backend.app.algorithms.inputs import (
    GRID_BLOCKED,
    GRID_GOAL,
    GRID_START,
    BracketSpec,
    CoinSpec,
    GridWithWord,
    IntList,
    IntListWithTarget,
    LabelledGrid,
)

#: A cell that is in its final position.
SETTLED = CELL_SORTED

#: The four orthogonal directions a grid traversal can move in, in the order they
#: are tried. The order is fixed so a traversal's frames are deterministic; it is
#: not a search-quality decision, and the algorithms that care about order
#: (``bfs_shortest_path``) do not.
_ORTHOGONAL = ((-1, 0), (0, 1), (1, 0), (0, -1))


# --------------------------------------------------------------------------- #
# Sorting
# --------------------------------------------------------------------------- #


def bubble_sort(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Repeatedly walk the array, swapping neighbours that are out of order.

    Quadratic in the worst case and honest about it: the frames show the shrinking
    unsorted window, and the counter is the real number of comparisons. That is
    the whole reason to include it beside the faster sorts.
    """
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items)],
        "The whole array starts unsorted. Bubble sort will compare neighbours and "
        "swap them whenever the left one is larger.",
    )

    for end in range(size - 1, 0, -1):
        swapped = False
        for index in range(end):
            trace.count("comparisons")
            tones = [CELL_IDLE] * size
            tones[index] = CELL_COMPARE
            tones[index + 1] = CELL_COMPARE
            for settled in range(end + 1, size):
                tones[settled] = SETTLED
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"Compare the values at positions {index} and {index + 1}.",
                pointers={"i": index, "j": index + 1, "end": end},
            )
            if items[index] > items[index + 1]:
                items[index], items[index + 1] = items[index + 1], items[index]
                swapped = True
                trace.count("swaps")
                tones[index] = CELL_SWAP
                tones[index + 1] = CELL_SWAP
                yield trace.snapshot(
                    [make_row("Array", items, tones)],
                    f"{items[index + 1]} is smaller than {items[index]}, so they trade places.",
                    pointers={"i": index, "j": index + 1, "end": end},
                )
        if not swapped:
            # No swap in a whole pass means the array is already ordered. Saying so
            # is the algorithm's actual early exit, and skipping the rest of the
            # passes is what the counter above is counting.
            yield trace.snapshot(
                [make_row("Array", items, [SETTLED] * size)],
                "A whole pass made no swap, so the array is already sorted and the "
                "remaining passes are skipped.",
                status=STATUS_COMPLETE,
                result=format_int_list(items),
            )
            return

    yield trace.snapshot(
        [make_row("Array", items, [SETTLED] * size)],
        "Every pass is done. Each element is now in its final position.",
        status=STATUS_COMPLETE,
        result=format_int_list(items),
    )


def selection_sort(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Repeatedly select the smallest remaining element and swap it into place.

    Always performs the same number of comparisons; the savings are in swaps, and
    the frames make that visible because a selection sort swaps at most once per
    pass however unsorted the input was.
    """
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items)],
        "Selection sort picks the smallest remaining value for each position in turn.",
    )

    for target in range(size):
        smallest = target
        for index in range(target + 1, size):
            trace.count("comparisons")
            tones = [CELL_IDLE] * size
            tones[target] = CELL_ACTIVE
            tones[smallest] = CELL_PIVOT
            tones[index] = CELL_COMPARE
            for settled in range(target):
                tones[settled] = SETTLED
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"Position {target} needs the smallest value from {target} onwards. "
                f"Compare against the best candidate so far at {smallest}.",
                pointers={"target": target, "best": smallest, "scan": index},
            )
            if items[index] < items[smallest]:
                smallest = index
        if smallest != target:
            items[target], items[smallest] = items[smallest], items[target]
            trace.count("swaps")
            tones = [CELL_IDLE] * size
            tones[target] = CELL_SWAP
            tones[smallest] = CELL_SWAP
            for settled in range(target):
                tones[settled] = SETTLED
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"Swap the smallest remaining value into position {target}.",
                pointers={"target": target, "best": smallest},
            )

    yield trace.snapshot(
        [make_row("Array", items, [SETTLED] * size)],
        "Every position now holds the value that belongs in it.",
        status=STATUS_COMPLETE,
        result=format_int_list(items),
    )


def insertion_sort(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Grow a sorted prefix one element at a time, shifting larger values right."""
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items)],
        "Insertion sort keeps a sorted prefix on the left and inserts the next "
        "element into it.",
        pointers={"next": 0} if size else {},
    )

    for index in range(1, size):
        held = items[index]
        tones = [CELL_IDLE] * size
        for settled in range(index):
            tones[settled] = SETTLED
        tones[index] = CELL_ACTIVE
        yield trace.snapshot(
            [make_row("Array", items, tones)],
            f"Lift the value at position {index} out and look for where it belongs "
            "in the sorted prefix.",
            pointers={"hole": index},
        )
        cursor = index - 1
        while cursor >= 0 and items[cursor] > held:
            trace.count("comparisons")
            items[cursor + 1] = items[cursor]
            trace.count("writes")
            tones[cursor + 1] = CELL_SWAP
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"Shift the value at {cursor} one place right to open a gap.",
                pointers={"hole": cursor + 1, "held": index},
            )
            cursor -= 1
        if cursor >= 0:
            trace.count("comparisons")
        items[cursor + 1] = held
        trace.count("writes")
        tones = [CELL_IDLE] * size
        for settled in range(index + 1):
            tones[settled] = SETTLED
        yield trace.snapshot(
            [make_row("Array", items, tones)],
            f"The lifted value drops into position {cursor + 1}, and the prefix is "
            "sorted again.",
            pointers={"placed": cursor + 1},
        )

    yield trace.snapshot(
        [make_row("Array", items, [SETTLED] * size)],
        "The sorted prefix has grown to cover the whole array.",
        status=STATUS_COMPLETE,
        result=format_int_list(items),
    )


def merge_sort(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Split to single elements, then merge pairs back together in order.

    The auxiliary rows are the real merge buffer and the two runs being merged, so
    the linear extra space is something the learner watches being used rather
    than a claim in a complexity field.
    """
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items)],
        "Merge sort splits the array in half until every piece is a single value, "
        "then merges the pieces back together in order.",
    )
    yield from _merge_sort_pass(items, 0, size - 1, trace)
    yield trace.snapshot(
        [make_row("Array", items, [SETTLED] * size)],
        "One fully merged run remains, and it is the sorted array.",
        status=STATUS_COMPLETE,
        result=format_int_list(items),
    )


def _merge_sort_pass(items: list[int], low: int, high: int, trace: Trace) -> Iterator[FrameState]:
    """Sort ``items[low..high]`` recursively, yielding a frame per merge."""
    if low >= high:
        return
    middle = (low + high) // 2
    yield from _merge_sort_pass(items, low, middle, trace)
    yield from _merge_sort_pass(items, middle + 1, high, trace)
    yield from _merge(items, low, middle, high, trace)


def _merge(
    items: list[int],
    low: int,
    middle: int,
    high: int,
    trace: Trace,
) -> Iterator[FrameState]:
    """Merge the sorted runs ``items[low..middle]`` and ``items[middle+1..high]``."""
    left = list(items[low : middle + 1])
    right = list(items[middle + 1 : high + 1])
    merged: list[int] = []
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        trace.count("comparisons")
        trace.count("reads")
        yield trace.snapshot(
            [make_row("Array", items)],
            f"Positions {low} to {middle} and {middle + 1} to {high} are each sorted. "
            "Take the smaller of their two front values.",
            auxiliary=[
                make_row("Merge buffer", merged + [None] * (len(left) + len(right) - len(merged))),
                make_row("Left run", left, [CELL_COMPARE] * len(left)),
                make_row("Right run", right, [CELL_COMPARE] * len(right)),
            ],
            pointers={"left": left_index, "right": right_index},
        )
        if left[left_index] <= right[right_index]:
            merged.append(left[left_index])
            left_index += 1
        else:
            merged.append(right[right_index])
            right_index += 1
        trace.count("writes")
    merged.extend(left[left_index:])
    merged.extend(right[right_index:])
    trace.count("writes", len(merged))
    items[low : high + 1] = merged
    yield trace.snapshot(
        [make_row("Array", items)],
        f"The merged run now fills positions {low} to {high}.",
        auxiliary=[make_row("Merge buffer", merged)],
        pointers={"from": low, "to": high},
    )


def quick_sort(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Partition around a pivot, then recurse into both sides.

    The pivot is always the **last** element, chosen so the frames are
    deterministic. That is also the pivot that degrades to quadratic on already
    sorted input, which is a real property of the algorithm and is exactly why
    ``heap_sort`` sits next to it in the registry.
    """
    items = list(case.values)
    yield trace.snapshot(
        [make_row("Array", items)],
        "Quick sort partitions around a pivot and then sorts each side of it. "
        "The pivot here is the last element of each range.",
    )
    yield from _quick_sort_pass(items, 0, len(items) - 1, trace)
    yield trace.snapshot(
        [make_row("Array", items, [SETTLED] * len(items))],
        "Every range has been reduced to one element, so the array is sorted.",
        status=STATUS_COMPLETE,
        result=format_int_list(items),
    )


def _quick_sort_pass(items: list[int], low: int, high: int, trace: Trace) -> Iterator[FrameState]:
    """The recursive partition-and-recurse step."""
    if low > high:
        return
    if low == high:
        trace.count("comparisons")
        tones = [SETTLED if index <= high else CELL_IDLE for index in range(len(items))]
        yield trace.snapshot(
            [make_row("Array", items, tones)],
            f"Position {low} is alone in its range, so it is already in place.",
            pointers={"low": low},
        )
        return

    pivot_value = items[high]
    boundary = low
    for scan in range(low, high):
        trace.count("comparisons")
        tones = [CELL_IDLE] * len(items)
        tones[high] = CELL_PIVOT
        tones[boundary] = CELL_ACTIVE
        tones[scan] = CELL_COMPARE
        yield trace.snapshot(
            [make_row("Array", items, tones)],
            f"Compare position {scan} against the pivot {pivot_value}.",
            pointers={"scan": scan, "boundary": boundary, "pivot": high},
        )
        if items[scan] <= pivot_value:
            if scan != boundary:
                items[scan], items[boundary] = items[boundary], items[scan]
                trace.count("swaps")
                yield trace.snapshot(
                    [make_row("Array", items, tones)],
                    f"Move the value that belongs on the pivot's side into position "
                    f"{boundary}.",
                    pointers={"scan": scan, "boundary": boundary, "pivot": high},
                )
            boundary += 1

    items[boundary], items[high] = items[high], items[boundary]
    trace.count("swaps")
    tones = [CELL_IDLE] * len(items)
    tones[boundary] = CELL_MATCH
    tones[high] = CELL_PIVOT
    yield trace.snapshot(
        [make_row("Array", items, tones)],
        f"Swap the pivot into position {boundary}. Everything left of it is at most "
        f"{pivot_value} and everything right of it is larger.",
        pointers={"pivot": boundary},
    )
    yield from _quick_sort_pass(items, low, boundary - 1, trace)
    yield from _quick_sort_pass(items, boundary + 1, high, trace)


def heap_sort(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Build a max heap, then repeatedly move the root to the back of the heap.

    The auxiliary row is the heap's own array. Keeping it visible is the point:
    the algorithm's space is not extra here, it reuses the array it is sorting,
    and the frames show exactly that.
    """
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items), make_row("Heap", items)],
        "Heap sort treats the array as a binary heap: the largest value sits at the "
        "root and every parent is at least as large as its children.",
    )

    def heap_row(prefix: int, highlight: set[int]) -> FrameRow:
        return make_row(
            "Heap",
            items[:prefix] + [None] * (size - prefix),
            [CELL_ACTIVE if index in highlight else CELL_IDLE for index in range(size)],
        )

    def sift_down(root: int, limit: int) -> Iterator[FrameState]:
        while True:
            largest = root
            left = 2 * root + 1
            right = 2 * root + 2
            for candidate in (left, right):
                if candidate < limit:
                    trace.count("comparisons")
            yield trace.snapshot(
                [make_row("Array", items), heap_row(size, {root})],
                f"Sift the value at heap position {root} down, keeping the largest "
                "of it and its children at the root.",
                auxiliary=[heap_row(size, {root})],
                pointers={"root": root, "limit": limit},
            )
            if left < limit and items[left] > items[largest]:
                largest = left
            if right < limit and items[right] > items[largest]:
                largest = right
            if largest == root:
                return
            items[root], items[largest] = items[largest], items[root]
            trace.count("swaps")
            yield trace.snapshot(
                [make_row("Array", items), heap_row(size, {root, largest})],
                f"Swap heap positions {root} and {largest} to restore the heap order.",
                auxiliary=[heap_row(size, {root, largest})],
                pointers={"root": root, "child": largest},
            )
            root = largest

    for start in range(size // 2 - 1, -1, -1):
        yield from sift_down(start, size)

    for end in range(size - 1, 0, -1):
        items[0], items[end] = items[end], items[0]
        trace.count("swaps")
        tones = [CELL_IDLE] * size
        tones[0] = CELL_PIVOT
        tones[end] = SETTLED
        yield trace.snapshot(
            [make_row("Array", items, tones), heap_row(end, {0})],
            f"Move the largest remaining value to position {end}, which is now final.",
            pointers={"root": 0, "end": end},
        )
        yield from sift_down(0, end)

    yield trace.snapshot(
        [make_row("Array", items, [SETTLED] * size)],
        "The heap is empty, so every value has been placed in its final position.",
        status=STATUS_COMPLETE,
        result=format_int_list(items),
    )


# --------------------------------------------------------------------------- #
# Searching
# --------------------------------------------------------------------------- #


def linear_search(case: IntListWithTarget, trace: Trace) -> Iterator[FrameState]:
    """Walk the array left to right until the target turns up."""
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items)],
        f"Linear search checks each element against {case.target} in turn, so it "
        "always reads the array in order.",
        pointers={"target": 0} if size else {},
    )

    for index, value in enumerate(items):
        trace.count("comparisons")
        found = value == case.target
        tones = [CELL_VISITED] * size
        tones[index] = CELL_MATCH if found else CELL_ACTIVE
        yield trace.snapshot(
            [make_row("Array", items, tones)],
            (
                f"The value at position {index} is {case.target}, so the search stops "
                f"at index {index}."
                if found
                else f"The value at position {index} is not {case.target}, so keep going."
            ),
            pointers={"scan": index},
        )
        if found:
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"Found {case.target} at index {index}.",
                status=STATUS_COMPLETE,
                result=str(index),
            )
            return

    yield trace.snapshot(
        [make_row("Array", items, [CELL_VISITED] * size)],
        f"Every element was checked and none was {case.target}.",
        status=STATUS_COMPLETE,
        result="-1",
    )


def binary_search(case: IntListWithTarget, trace: Trace) -> Iterator[FrameState]:
    """Halve the range on every comparison, which needs a sorted array.

    The range markers are painted as well as pointed at, because what binary
    search actually discards is the half it ruled out. A learner watching only the
    midpoint would not see that.
    """
    items = list(case.values)
    size = len(items)
    yield trace.snapshot(
        [make_row("Array", items)],
        f"Binary search assumes the array is sorted. It compares against the middle "
        f"of the range still in play, looking for {case.target}.",
    )

    low = 0
    high = size - 1
    while low <= high:
        middle = (low + high) // 2
        trace.count("comparisons")
        tones = [CELL_IDLE] * size
        for index in range(size):
            if index < low or index > high:
                tones[index] = CELL_BLOCKED
        tones[middle] = CELL_COMPARE
        yield trace.snapshot(
            [make_row("Array", items, tones)],
            f"The range is {low} to {high}, so the middle is {middle}. Compare "
            f"{items[middle]} with {case.target}.",
            pointers={"low": low, "middle": middle, "high": high},
        )
        if items[middle] == case.target:
            found = [CELL_IDLE] * size
            found[middle] = CELL_MATCH
            yield trace.snapshot(
                [make_row("Array", items, found)],
                f"Found {case.target} at index {middle}.",
                status=STATUS_COMPLETE,
                result=str(middle),
            )
            return
        if items[middle] < case.target:
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"{items[middle]} is smaller than {case.target}, so everything up to "
                f"{middle} is too small and is discarded.",
                pointers={"low": middle + 1, "middle": middle, "high": high},
            )
            low = middle + 1
        else:
            yield trace.snapshot(
                [make_row("Array", items, tones)],
                f"{items[middle]} is larger than {case.target}, so everything from "
                f"{middle} onwards is too large and is discarded.",
                pointers={"low": low, "middle": middle, "high": middle - 1},
            )
            high = middle - 1

    yield trace.snapshot(
        [make_row("Array", items, [CELL_BLOCKED] * size)],
        f"The range emptied without finding {case.target}.",
        status=STATUS_COMPLETE,
        result="-1",
    )


# --------------------------------------------------------------------------- #
# Two pointers
# --------------------------------------------------------------------------- #


def two_pointers_max_area(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Move the shorter of two inward-moving ends, the container-area trick.

    This is the ``container-with-most-water`` shape from the catalog: two pointers
    close in from the ends, and the answer is the widest rectangle found on the way.
    """
    heights = list(case.values)
    size = len(heights)
    yield trace.snapshot(
        [make_row("Heights", heights)],
        "Two pointers start at the ends. At each step the area is the width times "
        "the shorter height, and only the shorter pointer moves.",
    )

    left = 0
    right = size - 1
    best = 0
    best_pair = (0, size - 1)
    while left < right:
        area = (right - left) * min(heights[left], heights[right])
        trace.count("comparisons")
        if area > best:
            best = area
            best_pair = (left, right)
        tones = [CELL_IDLE] * size
        tones[left] = CELL_ACTIVE
        tones[right] = CELL_ACTIVE
        for index in range(left, right + 1):
            if heights[index] > min(heights[left], heights[right]):
                tones[index] = CELL_IDLE
        yield trace.snapshot(
            [make_row("Heights", heights, tones)],
            f"Between positions {left} and {right} the widest container holds "
            f"{area} units.",
            pointers={"left": left, "right": right},
        )
        if heights[left] <= heights[right]:
            yield trace.snapshot(
                [make_row("Heights", heights, tones)],
                f"The left height {heights[left]} is the shorter one, so it is the "
                "only move that can improve the area.",
                pointers={"left": left, "right": right, "move": left},
            )
            left += 1
        else:
            yield trace.snapshot(
                [make_row("Heights", heights, tones)],
                f"The right height {heights[right]} is the shorter one, so it is the "
                "only move that can improve the area.",
                pointers={"left": left, "right": right, "move": right},
            )
            right -= 1

    best_tones = [CELL_IDLE] * size
    if size:
        best_tones[best_pair[0]] = CELL_MATCH
        best_tones[best_pair[1]] = CELL_MATCH
    yield trace.snapshot(
        [make_row("Heights", heights, best_tones)],
        f"The pointers met. The largest container holds {best} units.",
        status=STATUS_COMPLETE,
        result=str(best),
    )


# --------------------------------------------------------------------------- #
# Dynamic programming
# --------------------------------------------------------------------------- #


def kadane_max_subarray(case: IntList, trace: Trace) -> Iterator[FrameState]:
    """Track the best sum ending at each position, extending or restarting.

    The auxiliary row is the running "best ending here" table. Seeing it climb and
    restart is the whole argument for why Kadane's algorithm is linear.
    """
    items = list(case.values)
    size = len(items)
    best_ending = 0
    best_sum = None
    best_start = 0
    best_end = 0
    start = 0
    yield trace.snapshot(
        [make_row("Array", items)],
        "Kadane's algorithm keeps the best sum that ends at each position, and "
        "extends the previous one unless the value is negative.",
    )

    for index, value in enumerate(items):
        trace.count("comparisons")
        if best_ending + value < value:
            best_ending = value
            start = index
            yield trace.snapshot(
                [make_row("Array", items)],
                f"Starting again at {index}: a sum of {best_ending + value} would be "
                f"worse than the single value {value}.",
                pointers={"index": index, "start": start},
            )
        else:
            best_ending += value
            yield trace.snapshot(
                [make_row("Array", items)],
                f"Extending the run that ends at {index - 1} gives {best_ending}.",
                pointers={"index": index, "start": start},
            )
        if best_sum is None or best_ending > best_sum:
            best_sum = best_ending
            best_start = start
            best_end = index

    tones = [CELL_IDLE] * size
    for index in range(best_start, best_end + 1):
        tones[index] = CELL_MATCH
    yield trace.snapshot(
        [make_row("Array", items, tones)],
        f"The best run is positions {best_start} to {best_end}, summing to {best_sum}.",
        status=STATUS_COMPLETE,
        result=str(best_sum),
    )


def coin_change(case: CoinSpec, trace: Trace) -> Iterator[FrameState]:
    """Fill a table of the fewest coins needed for every amount up to the target."""
    amount = case.amount
    coins = list(case.coins)
    fewest: list[int | None] = [0] + [None] * amount
    yield trace.snapshot(
        [make_row("Coins", coins)],
        f"Coin change asks for the fewest coins summing to {amount} drawn from "
        f"{format_int_list(coins)}.",
    )

    def table_row(current: int) -> FrameRow:
        labels = ["" if value is None else str(value) for value in fewest]
        tones = [CELL_ACTIVE if index == current else CELL_IDLE for index in range(amount + 1)]
        return make_row("Fewest coins", labels, tones)

    for current in range(1, amount + 1):
        for coin in coins:
            trace.count("comparisons")
            if coin <= current and fewest[current - coin] is not None:
                candidate = fewest[current - coin] + 1
                trace.count("writes")
                if fewest[current] is None or candidate < fewest[current]:
                    fewest[current] = candidate
        reachable = fewest[current] is not None
        yield trace.snapshot(
            [make_row("Amount", list(range(amount + 1)))],
            (
                f"Amount {current} takes {fewest[current]} coins."
                if reachable
                else f"Amount {current} cannot be made from these coins."
            ),
            auxiliary=[table_row(current)],
            pointers={"amount": current},
        )

    answer = fewest[amount]
    yield trace.snapshot(
        [make_row("Coins", coins), make_row("Amount", list(range(amount + 1)))],
        (
            f"The table reaches {amount}, which takes {answer} coins."
            if answer is not None
            else f"The table is full and no combination of these coins reaches {amount}."
        ),
        auxiliary=[table_row(amount)],
        status=STATUS_COMPLETE,
        result="-1" if answer is None else str(answer),
    )


# --------------------------------------------------------------------------- #
# Stack
# --------------------------------------------------------------------------- #

#: The bracket pairs the algorithm matches, and the order a push renders in.
_BRACKET_PAIRS = {")": "(", "]": "[", "}": "{"}
_OPENING = {value: key for key, value in _BRACKET_PAIRS.items()}


def balanced_brackets(case: BracketSpec, trace: Trace) -> Iterator[FrameState]:
    """Push opening brackets, and require each closing bracket to match the top."""
    text = case.text
    size = len(text)
    stack: list[str] = []
    yield trace.snapshot(
        [make_row("Input", list(text))],
        "The stack holds the opening brackets that are still waiting to be closed. "
        "A closing bracket must match the bracket on top of it.",
    )

    for index, symbol in enumerate(text):
        trace.count("comparisons")
        if symbol in _OPENING:
            stack.append(symbol)
            trace.count("stack_pushes")
            tones = [CELL_VISITED] * size
            tones[index] = CELL_ACTIVE
            yield trace.snapshot(
                [make_row("Input", list(text), tones)],
                f"Push {symbol}. There are now {len(stack)} unclosed brackets.",
                auxiliary=[make_row("Stack", list(reversed(stack)), [CELL_FRONTIER] * len(stack))],
                pointers={"scan": index, "depth": len(stack) - 1},
            )
            continue

        matched = bool(stack) and stack[-1] == _BRACKET_PAIRS.get(symbol, "")
        tones = [CELL_VISITED] * size
        tones[index] = CELL_MATCH if matched else CELL_BLOCKED
        if matched:
            popped = stack.pop()
            trace.count("stack_pops")
            yield trace.snapshot(
                [make_row("Input", list(text), tones)],
                f"{symbol} closes the {popped} on top of the stack, so pop it. "
                f"{len(stack)} brackets remain open.",
                auxiliary=[make_row("Stack", list(reversed(stack)), [CELL_FRONTIER] * len(stack))],
                pointers={"scan": index, "depth": len(stack)},
            )
        else:
            yield trace.snapshot(
                [make_row("Input", list(text), tones)],
                f"{symbol} cannot close anything: the stack is "
                + ("empty" if not stack else f"topped by {stack[-1]}")
                + ".",
                auxiliary=[make_row("Stack", list(reversed(stack)), [CELL_FRONTIER] * len(stack))],
                pointers={"scan": index},
                status=STATUS_COMPLETE,
                result="unbalanced",
            )
            return

    balanced = not stack
    yield trace.snapshot(
        [make_row("Input", list(text), [CELL_MATCH if balanced else CELL_BLOCKED] * size)],
        (
            "The input ended with an empty stack, so every bracket was closed."
            if balanced
            else f"The input ended with {len(stack)} brackets still open."
        ),
        auxiliary=[make_row("Stack", list(reversed(stack)), [CELL_FRONTIER] * len(stack))],
        status=STATUS_COMPLETE,
        result="balanced" if balanced else "unbalanced",
    )


# --------------------------------------------------------------------------- #
# Grid traversals
# --------------------------------------------------------------------------- #


def _neighbours(rows: int, cols: int, row: int, col: int):
    """The in-bounds orthogonal neighbours of a cell, in the fixed order."""
    for row_step, col_step in _ORTHOGONAL:
        next_row = row + row_step
        next_col = col + col_step
        if 0 <= next_row < rows and 0 <= next_col < cols:
            yield next_row, next_col


def word_search(case: GridWithWord, trace: Trace) -> Iterator[FrameState]:
    """Depth-first search with backtracking, looking for a word in a grid.

    The same shape as the catalog's ``word-search`` problem, in the same input
    format. The recursion path is drawn as well as the visited set, because the
    backtracking -- the part that makes this exponential -- only becomes visible
    when the learner can see where the search currently is.
    """
    grid = [list(row) for row in case.grid]
    rows = case.rows
    cols = case.cols
    word = case.word
    yield trace.snapshot(
        grid_rows(grid),
        f"Depth-first search tries every direction from each cell, stepping back "
        f"one letter at a time, looking for {word}.",
    )

    visited: set[tuple[int, int]] = set()

    def search(row: int, col: int, matched: int, path: list[tuple[int, int]]) -> Iterator[FrameState]:
        trace.count("reads")
        if matched == len(word):
            return True
        for next_row, next_col in _neighbours(rows, cols, row, col):
            trace.count("comparisons")
            if (next_row, next_col) in path:
                continue
            if grid[next_row][next_col].upper() != word[matched].upper():
                continue
            path.append((next_row, next_col))
            visited.add((next_row, next_col))
            tones = {(r, c): CELL_VISITED for r, c in visited}
            for r, c in path:
                tones[(r, c)] = CELL_PATH
            yield trace.snapshot(
                grid_rows(grid, tones),
                f"Match {word[matched]!r} at row {next_row + 1}, column {next_col + 1}.",
                pointers={"row": next_row, "col": next_col, "depth": matched},
            )
            deeper = yield from search(next_row, next_col, matched + 1, path)
            if deeper:
                return True
            path.pop()
            yield trace.snapshot(
                grid_rows(grid, tones),
                f"No word starts with the match at row {next_row + 1}, column "
                f"{next_col + 1}, so back up.",
                pointers={"row": row, "col": col, "depth": matched},
            )
        return False

    found = False
    for row in range(rows):
        for col in range(cols):
            if grid[row][col].upper() != word[0].upper():
                continue
            visited.add((row, col))
            found = yield from search(row, col, 1, [(row, col)])
            if found:
                break
        if found:
            break

    tones = {(r, c): CELL_VISITED for r, c in visited}
    if found:
        # Paint the word's own letters over the visited set so the answer is
        # readable rather than merely inferable from which cells were touched.
        for row in range(rows):
            for col in range(cols):
                if grid[row][col].upper() == word[0].upper():
                    tones[(row, col)] = CELL_MATCH
        yield trace.snapshot(
            grid_rows(grid, tones),
            f"The search matched every letter of {word}, so the word is in the grid.",
            status=STATUS_COMPLETE,
            result="found",
        )
    else:
        yield trace.snapshot(
            grid_rows(grid, tones),
            f"Every cell has been tried and {word} is not in the grid.",
            status=STATUS_COMPLETE,
            result="not found",
        )


def bfs_shortest_path(case: LabelledGrid, trace: Trace) -> Iterator[FrameState]:
    """Breadth-first search from ``S`` to ``G``, which finds the shortest path.

    Cells are coloured by *when* the search reached them -- discovered, queued,
    expanded -- rather than merely visited or not, because the layer structure is
    the entire reason breadth-first search returns a shortest path.
    """
    grid = [list(row) for row in case.grid]
    rows = case.rows
    cols = case.cols
    start: tuple[int, int] | None = None
    goal: tuple[int, int] | None = None
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == GRID_START:
                start = (row, col)
            elif grid[row][col] == GRID_GOAL:
                goal = (row, col)
    if start is None or goal is None:
        raise ValueError("A grid needs exactly one S and one G for a shortest-path search.")

    blocked = {
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if grid[row][col] == GRID_BLOCKED
    }
    yield trace.snapshot(
        grid_rows(grid, {(r, c): CELL_BLOCKED for r, c in blocked}),
        "Breadth-first search explores cells in rings: everything one step from S "
        "before anything two steps away.",
        pointers={"row": start[0], "col": start[1]},
    )

    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue: list[tuple[int, int]] = [start]
    reached_goal = False
    while queue:
        current = queue.pop(0)
        row, col = current
        tones = {coordinate: CELL_VISITED for coordinate in came_from}
        for queued in queue:
            tones[queued] = CELL_FRONTIER
        for blocked_cell in blocked:
            tones[blocked_cell] = CELL_BLOCKED
        tones[current] = CELL_ACTIVE
        yield trace.snapshot(
            grid_rows(grid, tones),
            f"Expand row {row + 1}, column {col + 1}. The queue holds {len(queue)} "
            "cells still to expand.",
            pointers={"row": row, "col": col},
        )
        if current == goal:
            reached_goal = True
            break
        for next_row, next_col in _neighbours(rows, cols, row, col):
            if (next_row, next_col) in blocked or (next_row, next_col) in came_from:
                continue
            trace.count("writes")
            came_from[(next_row, next_col)] = current
            queue.append((next_row, next_col))
            yield trace.snapshot(
                grid_rows(grid, tones),
                f"Row {next_row + 1}, column {next_col + 1} is newly reachable, so it "
                "joins the back of the queue.",
                pointers={"row": next_row, "col": next_col},
            )

    path: list[tuple[int, int]] = []
    if reached_goal:
        cursor: tuple[int, int] | None = goal
        while cursor is not None:
            path.append(cursor)
            cursor = came_from.get(cursor)
        path.reverse()

    tones = {(r, c): CELL_VISITED for r, c in came_from}
    for r, c in blocked:
        tones[(r, c)] = CELL_BLOCKED
    for r, c in path:
        tones[(r, c)] = CELL_MATCH
    yield trace.snapshot(
        grid_rows(grid, tones),
        (
            f"The goal was reached in {len(path) - 1} steps, which is the fewest "
            "possible."
            if reached_goal
            else "The queue emptied without reaching the goal, so no path exists."
        ),
        status=STATUS_COMPLETE,
        result=(
            "no path"
            if not reached_goal
            else " -> ".join(f"({row + 1},{col + 1})" for row, col in path)
        ),
    )


__all__ = [
    "GRID_BLOCKED",
    "GRID_GOAL",
    "GRID_START",
    "balanced_brackets",
    "binary_search",
    "bfs_shortest_path",
    "bubble_sort",
    "coin_change",
    "heap_sort",
    "insertion_sort",
    "kadane_max_subarray",
    "linear_search",
    "merge_sort",
    "quick_sort",
    "selection_sort",
    "two_pointers_max_area",
    "word_search",
]
