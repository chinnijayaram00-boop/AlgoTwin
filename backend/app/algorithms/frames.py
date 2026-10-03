"""The normalized shape of one visualization frame.

A frame is what the timeline UI renders, and it has to be renderable without the
UI knowing which algorithm produced it. Every algorithm in
:mod:`backend.app.algorithms.reference` therefore emits the *same* structure: a
primary set of rows, an optional set of auxiliary rows, named pointers into the
primary row, a set of operation counters, a status, and the answer once there is
one. The frontend has one renderer rather than thirteen.

Two properties are load-bearing:

* **Determinism.** The same algorithm on the same input produces byte-identical
  frames. Pointer names are sorted and counters are sorted before a state is
  built, and the worker serializes with ``sort_keys=True``, so a dictionary's
  insertion order can never leak into the response. A timeline that reorders
  itself between two identical requests cannot be scrubbed reliably.
* **Honesty about completeness.** ``status`` distinguishes a run that finished
  from one the frame budget cut short. A truncated timeline is still shown -- it
  is real execution, just capped -- but it is never presented as the whole run.
  A missing counter is absent rather than zero, because "this algorithm never
  compared anything" and "we did not count comparisons" are different claims and
  only the first is a measurement.

Cells carry a ``tone`` from a closed vocabulary rather than a colour. The palette
is the frontend's business, and a tone the frontend does not recognise degrades to
the idle appearance instead of rendering as broken markup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------- #
# The closed vocabularies
# --------------------------------------------------------------------------- #

#: Nothing is happening to this element at this step.
CELL_IDLE = "idle"
#: The element the algorithm is currently looking at.
CELL_ACTIVE = "active"
#: Two elements being compared against each other right now.
CELL_COMPARE = "compare"
#: The pivot, or the element playing the pivot's role.
CELL_PIVOT = "pivot"
#: These two elements were just exchanged.
CELL_SWAP = "swap"
#: The element is in its final position and will not move again.
CELL_SORTED = "sorted"
#: The element is part of the answer.
CELL_MATCH = "match"
#: The element has been reached and expanded.
CELL_VISITED = "visited"
#: The element is queued but not yet expanded.
CELL_FRONTIER = "frontier"
#: The element is on the current candidate path.
CELL_PATH = "path"
#: The element cannot be entered.
CELL_BLOCKED = "blocked"

CELL_TONES: tuple[str, ...] = (
    CELL_IDLE,
    CELL_ACTIVE,
    CELL_COMPARE,
    CELL_PIVOT,
    CELL_SWAP,
    CELL_SORTED,
    CELL_MATCH,
    CELL_VISITED,
    CELL_FRONTIER,
    CELL_PATH,
    CELL_BLOCKED,
)

#: One row per element, drawn left to right as bars. Sorting and searching use
#: this, because the height is the value.
STATE_KIND_BAR_ARRAY = "bar_array"
#: One row per element, drawn left to right as labelled boxes. Pointers, stacks,
#: and dynamic-programming tables use this, where position and label matter more
#: than magnitude.
STATE_KIND_ARRAY = "array"
#: Several rows of equal width. Graph traversals use this.
STATE_KIND_GRID = "grid"
#: One row of characters. Strings use this.
STATE_KIND_TEXT = "text"

STATE_KINDS: tuple[str, ...] = (
    STATE_KIND_ARRAY,
    STATE_KIND_BAR_ARRAY,
    STATE_KIND_GRID,
    STATE_KIND_TEXT,
)

#: The algorithm is still working.
STATUS_RUNNING = "running"
#: The algorithm reached its answer; the last frame carries it.
STATUS_COMPLETE = "complete"
#: The frame budget ran out before the algorithm finished. Real execution, capped.
STATUS_TRUNCATED = "truncated"

STATUSES: tuple[str, ...] = (STATUS_RUNNING, STATUS_COMPLETE, STATUS_TRUNCATED)

#: How many states a single frame may carry. An interactive visualization with
#: more cells than this is a table, not a picture, and the response stops being
#: something a browser can hold.
MAX_CELLS_PER_FRAME = 512


@dataclass(frozen=True)
class FrameCell:
    """One element of a row.

    ``label`` is what the learner reads and is always a string, because the same
    renderer draws an ``int``, a ``str`` bracket, and a grid character. ``detail``
    is the optional secondary annotation -- the value a hash map remembers for an
    index, say -- and is absent rather than empty when there is nothing to say.
    """

    label: str
    tone: str = CELL_IDLE
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "tone": self.tone, "detail": self.detail}


@dataclass(frozen=True)
class FrameRow:
    """A labelled row of cells: the array, or one auxiliary structure."""

    label: str
    cells: tuple[FrameCell, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "cells": [cell.to_dict() for cell in self.cells]}


@dataclass(frozen=True)
class FrameState:
    """Everything the renderer needs for one step, plus the step's own sentence.

    ``explanation`` is written by the algorithm at the moment it takes the step,
    not derived afterwards from the state. That is deliberate: the algorithm knows
    why it swapped two elements, and a state diff can say that a swap happened
    without being able to say which comparison caused it.
    """

    kind: str
    explanation: str
    rows: tuple[FrameRow, ...] = ()
    auxiliary: tuple[FrameRow, ...] = ()
    #: Named positions into the *first* row, e.g. ``{"i": 3, "j": 7}``. A pointer
    #: whose index is outside the row is dropped by the builder rather than sent,
    #: because a pointer pointing at nothing would render as a dangling mark.
    pointers: dict[str, int] = field(default_factory=dict)
    #: Real operation counters. Only the operations an algorithm actually performs
    #: are present, so an absent key means "not counted", never "zero of them".
    metrics: dict[str, int] = field(default_factory=dict)
    status: str = STATUS_RUNNING
    #: The algorithm's answer, on the final frame only.
    result: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "explanation": self.explanation,
            "rows": [row.to_dict() for row in self.rows],
            "auxiliary": [row.to_dict() for row in self.auxiliary],
            "pointers": dict(self.pointers),
            "metrics": dict(self.metrics),
            "status": self.status,
            "result": self.result,
        }


def cell(label: object, tone: str = CELL_IDLE, detail: str | None = None) -> FrameCell:
    """One cell from any label type.

    ``bool`` is checked before ``int`` deliberately: ``True`` renders as ``"1"``
    otherwise, which would draw a grid of ones and zeros where the algorithm
    meant open and blocked cells.
    """
    if tone not in CELL_TONES:
        raise ValueError(f"{tone!r} is not a cell tone this platform publishes.")
    if isinstance(label, bool):
        text = "true" if label else "false"
    elif isinstance(label, str):
        text = label
    else:
        text = str(label)
    return FrameCell(label=text, tone=tone, detail=detail)


def make_row(
    label: str,
    labels: Iterable[object],
    tones: Sequence[str] | None = None,
    details: Sequence[str | None] | None = None,
) -> FrameRow:
    """Build one row, applying a tone (and an optional detail) per position.

    ``tones`` shorter than ``labels`` leaves the remaining cells idle, which is
    what every algorithm wants: it paints the two cells it cares about and does
    not have to restate the rest.
    """
    values = list(labels)
    painted = list(tones) if tones is not None else []
    annotated = list(details) if details is not None else []
    cells = tuple(
        cell(
            value,
            painted[position] if position < len(painted) else CELL_IDLE,
            annotated[position] if position < len(annotated) else None,
        )
        for position, value in enumerate(values)
    )
    if len(cells) > MAX_CELLS_PER_FRAME:
        raise ValueError(f"A frame row may carry at most {MAX_CELLS_PER_FRAME} cells.")
    return FrameRow(label=label, cells=cells)


def grid_rows(
    grid: Sequence[Sequence[str]],
    tones: dict[tuple[int, int], str] | None = None,
    row_label: str = "Grid",
) -> tuple[FrameRow, ...]:
    """Build the rows of a grid state.

    ``grid`` is indexed ``[row][column]``, and ``tones`` uses the same coordinate
    pair, so an algorithm paints ``tones[(r, c)] = CELL_VISITED`` without
    counting positions off by one.
    """
    painted = tones or {}
    rows: list[FrameRow] = []
    for row_index, row_values in enumerate(grid):
        tone_row = [painted.get((row_index, column), CELL_IDLE) for column in range(len(row_values))]
        rows.append(make_row(f"{row_label} row {row_index + 1}", row_values, tone_row))
    return tuple(rows)


def format_int_list(values: Sequence[int]) -> str:
    """Render an integer sequence the way the problem catalog renders one."""
    return " ".join(str(value) for value in values)


class Trace:
    """The counters and the frame factory one reference algorithm writes through.

    Algorithms are generators: they count a real operation with :meth:`count` and
    then yield whatever :meth:`snapshot` returns at that instant. Nothing is
    recorded after the fact and no state is reconstructed, so every frame in a
    timeline is a state the algorithm was genuinely in.

    Counters live here rather than in the generator so that a comparison run,
    which consumes the frames and throws them away, still reports the same real
    operation counts as a visualization run. The count is a property of the
    algorithm, not of whether anybody is watching.
    """

    def __init__(self, kind: str, explanation: str = "") -> None:
        if kind not in STATE_KINDS:
            raise ValueError(f"{kind!r} is not a state kind this platform publishes.")
        self.kind = kind
        self._default_explanation = explanation
        self._metrics: dict[str, int] = {}

    def count(self, name: str, amount: int = 1) -> None:
        """Record ``amount`` real occurrences of an operation."""
        if amount:
            self._metrics[name] = self._metrics.get(name, 0) + amount

    @property
    def metrics(self) -> dict[str, int]:
        """The counters so far, sorted so the serialized form is stable."""
        return dict(sorted(self._metrics.items()))

    def snapshot(
        self,
        rows: Sequence[FrameRow],
        explanation: str | None = None,
        *,
        auxiliary: Sequence[FrameRow] = (),
        pointers: dict[str, int] | None = None,
        status: str = STATUS_RUNNING,
        result: str | None = None,
    ) -> FrameState:
        """One frame, as the algorithm sees its own state right now."""
        if status not in STATUSES:
            raise ValueError(f"{status!r} is not a frame status this platform publishes.")
        return FrameState(
            kind=self.kind,
            explanation=explanation or self._default_explanation,
            rows=tuple(rows),
            auxiliary=tuple(auxiliary),
            pointers=dict(sorted((pointers or {}).items())),
            metrics=self.metrics,
            status=status,
            result=result,
        )


__all__ = [
    "CELL_ACTIVE",
    "CELL_BLOCKED",
    "CELL_COMPARE",
    "CELL_FRONTIER",
    "CELL_IDLE",
    "CELL_MATCH",
    "CELL_PATH",
    "CELL_PIVOT",
    "CELL_SORTED",
    "CELL_SWAP",
    "CELL_TONES",
    "CELL_VISITED",
    "MAX_CELLS_PER_FRAME",
    "STATE_KIND_ARRAY",
    "STATE_KIND_BAR_ARRAY",
    "STATE_KIND_GRID",
    "STATE_KIND_TEXT",
    "STATE_KINDS",
    "STATUS_COMPLETE",
    "STATUS_RUNNING",
    "STATUS_TRUNCATED",
    "STATUSES",
    "FrameCell",
    "FrameRow",
    "FrameState",
    "Trace",
    "cell",
    "format_int_list",
    "grid_rows",
    "make_row",
]
