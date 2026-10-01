"""The single definition of "the program printed the right answer".

One rule, used by the judge, by the catalog integrity test, and by anything else
that has to decide whether two outputs are the same, so a run cannot be accepted
by one component and rejected by another.

The rule is deliberately narrow:

* line endings are normalised, so a program that writes ``\\r\\n`` is not
  penalised for running on Windows;
* trailing whitespace on each line is dropped, so a stray space or a final
  ``\\r`` does not fail a run;
* trailing blank lines are dropped, so a program that ends with ``print()`` is
  not penalised.

Everything else is compared exactly. Internal spacing is part of the answer: if
a problem says the answer is ``0 1``, then ``0  1`` is wrong, because a learner
comparing two outputs by eye would read them as different. Being strict here
keeps the platform from accepting a submission that a human would reject.
"""

from __future__ import annotations

#: How much output a run may produce. A program that prints without stopping
#: would otherwise fill the disk before the time limit stopped it. Generous
#: enough for any legitimate answer in this catalog, and small enough to hold in
#: memory comfortably.
MAX_OUTPUT_BYTES = 256 * 1024


def normalize_output(text: str | None) -> str:
    """Reduce insignificant differences in a program's output to nothing.

    Returns a single string with ``\\r\\n`` collapsed to ``\\n``, trailing
    whitespace removed from every line, and trailing blank lines removed. Two
    programs that differ only in those respects produce the same result, so
    :func:`outputs_match` treats them as agreeing.
    """
    if not text:
        return ""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def outputs_match(actual: str | None, expected: str | None) -> bool:
    """Whether a program's output is the expected answer.

    ``normalize_output`` is applied to both sides, so this is the comparison the
    judge and the catalog integrity test both use.
    """
    return normalize_output(actual) == normalize_output(expected)
