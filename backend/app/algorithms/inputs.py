"""Reading a visualization request's text into the values an algorithm operates on.

Every algorithm declares an ``input_grammar`` in
:mod:`backend.app.algorithms.registry`, and this module is the only thing that
knows what any of those names mean. Two reasons it is a closed set rather than
something each algorithm parses for itself:

* **Comparisons have to be exact.** Two algorithms in the same comparison group are
  handed the *same* text and parsed by the *same* function, so there is no way for
  the two sides of a comparison to end up looking at different values from
  identical bytes. A comparison whose inputs have silently diverged would show two
  algorithms winning on two different problems.
* **A grammar the catalog already publishes is reused, not reinvented.** The
  integer-list, coin, bracket-string, and grid shapes below are the formats
  ``database/problem_defs`` already uses for the matching problem, so the input a
  learner copies out of a problem statement works here unchanged.

Parsing failures raise :class:`InvalidInputError` with a message naming what was
expected. That error is carried back out of the worker and becomes a 422, so a
learner who mistypes an input is told what the format is rather than shown an
empty timeline.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidInputError(ValueError):
    """The text a learner supplied is not in the grammar this algorithm declares."""


#: The most elements one input may carry. A visualization is a picture of an
#: algorithm working; past this the picture stops being legible and the frame
#: count stops being bounded in any useful way.
MAX_INPUT_ITEMS = 48

#: The most grid rows, and the most columns in one grid row.
MAX_GRID_ROWS = 12
MAX_GRID_COLUMNS = 12

#: The ceiling on an amount in a coin-change request, so a dynamic-programming
#: table cannot be asked for an allocation the worker cannot survive.
MAX_AMOUNT = 2_000

# --------------------------------------------------------------------------- #
# The path-grid alphabet
#
# These live here rather than beside the traversal that reads them, because the
# alphabet is part of the *input format*: it is what a learner has to type. The
# traversal imports them so the character it walks through and the character it
# draws cannot drift apart, but the rules belong to the grammar.
# --------------------------------------------------------------------------- #

#: Where the traversal begins.
GRID_START = "S"
#: Where it is trying to reach. Optional -- a grid with no reachable goal is a valid
#: input whose honest answer is "no path", and refusing it would remove a case worth
#: watching.
GRID_GOAL = "G"
#: A wall. Cannot be entered.
GRID_BLOCKED = "#"
#: Open ground.
GRID_OPEN = "."

GRID_ALPHABET: frozenset[str] = frozenset({GRID_OPEN, GRID_BLOCKED, GRID_START, GRID_GOAL})


@dataclass(frozen=True)
class IntList:
    """``n`` followed by ``n`` integers. The shape every sorting algorithm reads."""

    values: tuple[int, ...]

    def render(self) -> str:
        return " ".join(str(value) for value in self.values)


@dataclass(frozen=True)
class IntListWithTarget:
    """``n``, ``n`` integers, then the value to find. What both searches read."""

    values: tuple[int, ...]
    target: int


@dataclass(frozen=True)
class CoinSpec:
    """``k amount`` followed by ``k`` coin values -- the catalog's coin-change format."""

    coins: tuple[int, ...]
    amount: int


@dataclass(frozen=True)
class BracketSpec:
    """``n`` followed by ``n`` characters. The catalog's valid-parentheses format."""

    text: str


@dataclass(frozen=True)
class GridWithWord:
    """``rows cols``, ``rows`` lines of ``cols`` characters, then a word."""

    grid: tuple[tuple[str, ...], ...]
    word: str

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0]) if self.grid else 0


@dataclass(frozen=True)
class LabelledGrid:
    """``rows cols`` followed by ``rows`` lines of grid characters.

    ``S`` marks the start, ``G`` the goal, ``#`` a blocked cell, and everything
    else is open floor.
    """

    grid: tuple[tuple[str, ...], ...]

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0]) if self.grid else 0


def _tokens(text: str) -> list[str]:
    return text.split()


def _single_int(tokens: list[str], label: str) -> int:
    if len(tokens) != 1:
        raise InvalidInputError(
            f"Expected one {label} on its own, found {len(tokens)} values. {GRAMMAR_HINT}"
        )
    try:
        return int(tokens[0])
    except ValueError as error:
        raise InvalidInputError(f"{label} must be a whole number, found {tokens[0]!r}.") from error


def _bounded_items(tokens: list[str], count: int, label: str) -> tuple[int, ...]:
    """Read exactly ``count`` integers, refusing an over-long request."""
    if count < 0:
        raise InvalidInputError(f"{label} cannot be negative.")
    if count > MAX_INPUT_ITEMS:
        raise InvalidInputError(
            f"{label} is {count}, and this visualizer draws at most {MAX_INPUT_ITEMS} elements."
        )
    if len(tokens) < count:
        raise InvalidInputError(
            f"Expected {count} {label} after the count, found {len(tokens)}. {GRAMMAR_HINT}"
        )
    values: list[int] = []
    for token in tokens[:count]:
        try:
            values.append(int(token))
        except ValueError as error:
            raise InvalidInputError(f"{label} must be whole numbers, found {token!r}.") from error
    return tuple(values)


def parse_int_list(text: str) -> IntList:
    """``n`` on line 1, then ``n`` integers."""
    tokens = _tokens(text)
    if not tokens:
        raise InvalidInputError(f"No input was supplied. {GRAMMAR_HINT}")
    count = _single_int(tokens[:1], "element count")
    if len(tokens) != count + 1:
        raise InvalidInputError(
            f"Declared {count} elements but supplied {max(0, len(tokens) - 1)}. "
            f"{GRAMMAR_HINT}"
        )
    return IntList(values=_bounded_items(tokens[1:], count, "elements"))


def parse_int_list_target(text: str) -> IntListWithTarget:
    """``n``, ``n`` integers, then the target value."""
    tokens = _tokens(text)
    if not tokens:
        raise InvalidInputError(f"No input was supplied. {GRAMMAR_HINT}")
    count = _single_int(tokens[:1], "element count")
    if len(tokens) != count + 2:
        raise InvalidInputError(
            f"Declared {count} elements and expected a target after them, "
            f"but found {max(0, len(tokens) - 1)} values. {GRAMMAR_HINT}"
        )
    values = _bounded_items(tokens[1:], count, "elements")
    return IntListWithTarget(values=values, target=_single_int(tokens[count + 1 :], "target"))


def parse_coins_amount(text: str) -> CoinSpec:
    """``k amount`` on line 1, then ``k`` coin values -- the catalog's own format."""
    tokens = _tokens(text)
    if len(tokens) < 2:
        raise InvalidInputError(f"Expected a coin count and an amount. {GRAMMAR_HINT}")
    count = _single_int(tokens[:1], "coin count")
    if len(tokens) != count + 2:
        raise InvalidInputError(
            f"Declared {count} coins and expected an amount after them, "
            f"but found {max(0, len(tokens) - 1)} values. {GRAMMAR_HINT}"
        )
    coins = _bounded_items(tokens[1:], count, "coins")
    amount = _single_int(tokens[count + 1 :], "amount")
    if amount < 0:
        raise InvalidInputError("The amount cannot be negative.")
    if amount > MAX_AMOUNT:
        raise InvalidInputError(
            f"The amount is {amount}, and this visualizer builds a table of at most {MAX_AMOUNT}."
        )
    return CoinSpec(coins=coins, amount=amount)


def parse_bracket_string(text: str) -> BracketSpec:
    """``n`` followed by ``n`` characters."""
    tokens = _tokens(text)
    if not tokens:
        raise InvalidInputError(f"No input was supplied. {GRAMMAR_HINT}")
    count = _single_int(tokens[:1], "string length")
    if count > MAX_INPUT_ITEMS:
        raise InvalidInputError(
            f"The string is {count} characters, and this visualizer draws at most "
            f"{MAX_INPUT_ITEMS}."
        )
    if len(tokens) < 2:
        raise InvalidInputError(f"Expected a string after the length. {GRAMMAR_HINT}")
    body = "".join(tokens[1:])
    if len(body) != count:
        raise InvalidInputError(
            f"Declared a string of {count} characters but supplied {len(body)}. {GRAMMAR_HINT}"
        )
    return BracketSpec(text=body)


def parse_grid_word(text: str) -> GridWithWord:
    """``rows cols``, ``rows`` lines of ``cols`` characters, then the word."""
    tokens = _tokens(text)
    if len(tokens) < 2:
        raise InvalidInputError(f"Expected a row count and a column count. {GRAMMAR_HINT}")
    rows = _single_int(tokens[:1], "row count")
    cols = _single_int(tokens[1:2], "column count")
    _check_grid_size(rows, cols)
    if len(tokens) < 2 + rows:
        raise InvalidInputError(f"Declared {rows} grid rows but supplied {max(0, len(tokens) - 2)}.")
    if len(tokens) != 3 + rows:
        raise InvalidInputError(f"Expected a search word after the grid. {GRAMMAR_HINT}")
    grid_lines = tokens[2 : 2 + rows]
    for line in grid_lines:
        if len(line) != cols:
            raise InvalidInputError(
                f"Each grid row must be exactly {cols} characters; one was {len(line)}."
            )
    word = tokens[2 + rows]
    if not word:
        raise InvalidInputError("The search word cannot be empty.")
    if len(word) > MAX_INPUT_ITEMS:
        raise InvalidInputError(f"The search word is longer than {MAX_INPUT_ITEMS} characters.")
    return GridWithWord(grid=tuple(tuple(line) for line in grid_lines), word=word)


def parse_labelled_grid(text: str) -> LabelledGrid:
    """``rows cols`` followed by ``rows`` lines of grid characters.

    The alphabet is validated rather than assumed, because every other letter is
    ambiguous. Two ``S`` cells is a grid with two starts and no way to choose between
    them; a grid with no ``G`` has no destination; and any character that is not one
    of ``.``, ``#``, ``S``, or ``G`` would draw a wall that looks walkable, and the
    search would happily walk through it. Each of those is caught here, with a message
    naming the fix, rather than producing a confident wrong answer.
    """
    tokens = _tokens(text)
    if len(tokens) < 2:
        raise InvalidInputError(f"Expected a row count and a column count. {GRAMMAR_HINT}")
    rows = _single_int(tokens[:1], "row count")
    cols = _single_int(tokens[1:2], "column count")
    _check_grid_size(rows, cols)
    if len(tokens) < 2 + rows:
        raise InvalidInputError(f"Declared {rows} grid rows but supplied {max(0, len(tokens) - 2)}.")
    grid_lines = tokens[2 : 2 + rows]
    for line in grid_lines:
        if len(line) != cols:
            raise InvalidInputError(
                f"Each grid row must be exactly {cols} characters; one was {len(line)}."
            )
    flattened = "".join(grid_lines)
    unknown = sorted(set(flattened) - GRID_ALPHABET)
    if unknown:
        raise InvalidInputError(
            f"A path grid may only contain {''.join(sorted(GRID_ALPHABET))}; "
            f"found {', '.join(unknown)}."
        )
    starts = flattened.count(GRID_START)
    if starts != 1:
        raise InvalidInputError(
            f"A path grid needs exactly one S to mark the start; found {starts}."
        )
    goals = flattened.count(GRID_GOAL)
    if goals > 1:
        raise InvalidInputError(
            f"A path grid can have at most one G to mark the goal; found {goals}."
        )
    return LabelledGrid(grid=tuple(tuple(line) for line in grid_lines))


def _check_grid_size(rows: int, cols: int) -> None:
    if rows <= 0 or cols <= 0:
        raise InvalidInputError("A grid must have at least one row and one column.")
    if rows > MAX_GRID_ROWS or cols > MAX_GRID_COLUMNS:
        raise InvalidInputError(
            f"A grid may be at most {MAX_GRID_ROWS} by {MAX_GRID_COLUMNS}; "
            f"this one is {rows} by {cols}."
        )


#: Appended to every parse failure so a learner who guessed the format is told
#: what it is, not only that they were wrong.
GRAMMAR_HINT = "Check the input format shown with the algorithm."


#: Grammar name -> parser. The names are the ones ``AlgorithmDescriptor`` uses, so
#: an algorithm cannot declare a grammar this module does not implement.
PARSERS = {
    "int_list": parse_int_list,
    "int_list_target": parse_int_list_target,
    "coins_amount": parse_coins_amount,
    "bracket_string": parse_bracket_string,
    "grid_word": parse_grid_word,
    "labelled_grid": parse_labelled_grid,
}

#: The grammar names, published so the API can document them and a test can
#: assert every registered algorithm names one this module can parse.
GRAMMARS: tuple[str, ...] = tuple(PARSERS)


def parse(grammar: str, text: str) -> object:
    """Parse ``text`` under the named grammar.

    The dispatch is a lookup rather than a chain of ``if``s so that an unknown
    grammar name fails immediately and visibly, instead of every algorithm
    quietly falling through to the same default parser.
    """
    parser = PARSERS.get(grammar)
    if parser is None:
        raise InvalidInputError(f"{grammar!r} is not an input grammar this platform implements.")
    return parser(text)


__all__ = [
    "GRAMMAR_HINT",
    "GRAMMARS",
    "GRID_ALPHABET",
    "GRID_BLOCKED",
    "GRID_GOAL",
    "GRID_OPEN",
    "GRID_START",
    "MAX_AMOUNT",
    "MAX_GRID_COLUMNS",
    "MAX_GRID_ROWS",
    "MAX_INPUT_ITEMS",
    "PARSERS",
    "BracketSpec",
    "CoinSpec",
    "GridWithWord",
    "IntList",
    "IntListWithTarget",
    "InvalidInputError",
    "LabelledGrid",
    "parse",
    "parse_bracket_string",
    "parse_coins_amount",
    "parse_grid_word",
    "parse_int_list",
    "parse_int_list_target",
    "parse_labelled_grid",
]
