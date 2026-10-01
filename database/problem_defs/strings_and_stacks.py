"""Strings, stacks, and backtracking.

Three problems that read text rather than numbers. Two of them are solved by
walking a string with a single pass, and one needs a search that gives up
quickly -- which is the first time backtracking has to be written down
deliberately rather than by accident.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import judged_case, source, text_lines

# --------------------------------------------------------------------------- #
# Valid Parentheses
# --------------------------------------------------------------------------- #


def _valid_parentheses(stdin: str) -> str:
    lines = text_lines(stdin)
    # The string may legitimately be empty, so a missing second line is an empty
    # string rather than a malformed case.
    sequence = lines[1] if len(lines) > 1 else ""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for character in sequence:
        if character in "([{":
            stack.append(character)
        elif character in pairs and (not stack or stack.pop() != pairs[character]):
            return "false"
    return "true" if not stack else "false"


VALID_PARENTHESES_INPUT = "6\n(())[]"

VALID_PARENTHESES: dict[str, Any] = {
    "slug": "valid-parentheses",
    "title": "Valid Parentheses",
    "summary": "Decide whether a string of brackets is correctly opened, closed, and nested.",
    "difficulty": "Easy",
    "topics": ["Stack", "Strings"],
    "description": (
        "Given a string `s` containing only the characters `(`, `)`, `{`, `}`, "
        "`[` and `]`, decide whether every opening bracket is closed by the right "
        "kind of closing bracket, in the correct order.\n\n"
        "Return `true` if the string is valid, otherwise `false`."
    ),
    "input_format": (
        "Line 1: `n`, the length of the string.\n"
        "Line 2: the string of `n` bracket characters, with no spaces."
    ),
    "output_format": "Print `true` if the brackets are valid, otherwise `false`, in lower case.",
    "constraints": "0 <= n <= 10^4. The string contains only `(`, `)`, `{`, `}`, `[` and `]`.",
    "examples": [
        {
            "input": VALID_PARENTHESES_INPUT,
            "output": _valid_parentheses(VALID_PARENTHESES_INPUT),
            "explanation": "The two pairs open and close in order, so the string is valid.",
        }
    ],
    "hints": [
        "Read the string left to right. An opening bracket creates an obligation; a closing bracket has to discharge one. What structure holds obligations that must be discharged in reverse order?",
        "A stack. Push every opening bracket, and when a closing bracket appears, the bracket it needs must be the most recent one still open.",
        "Push opening brackets. On a closing bracket, pop the stack and check the popped character is the opening bracket that matches it; if the stack is empty, or the top does not match, the string is invalid.",
        "Use a dictionary from each closing bracket to its opening partner, so the match test is one lookup rather than a chain of comparisons.",
        "After the scan, an empty stack means valid. A leftover opening bracket means something was opened and never closed, which is invalid even though no closing bracket ever mismatched.",
    ],
    "explanation": (
        "Nesting means the bracket closed last was opened last, which is exactly "
        "what a stack stores. Push every opening bracket. When a closing bracket "
        "arrives, the only bracket it can legally close is the one on top of the "
        "stack, so pop and compare against the closing bracket's partner from a "
        "lookup table.\n\n"
        "Two failure modes are caught during the scan: a closing bracket with an "
        "empty stack (something was closed that was never opened) and a closing "
        "bracket whose partner is not the top of the stack (crossed pairs such as "
        "`([)]`). After the scan, a stack that is not empty means an opening "
        "bracket was never closed.\n\n"
        "Each character is pushed and popped at most once, so the time is O(n) "
        "and the stack holds at most n characters, so the space is O(n)."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def is_valid(s):
                \"\"\"Return True when the brackets in s are correctly nested.\"\"\"
                return False


            def main():
                raw = sys.stdin.read()
                sequence = raw.partition("\\n")[2].strip()
                print("true" if is_valid(sequence) else "false")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function isValid(s) {
              // Return true when the brackets in s are correctly nested.
              return false;
            }

            function main() {
              const raw = fs.readFileSync(0, "utf8");
              const sequence = raw.slice(raw.indexOf("\\n") + 1).trim();
              console.log(isValid(sequence) ? "true" : "false");
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def is_valid(s):
                partners = {")": "(", "]": "[", "}": "{"}
                stack = []
                for character in s:
                    if character in "([{":
                        stack.append(character)
                    elif character in partners:
                        if not stack or stack.pop() != partners[character]:
                            return False
                return not stack


            def main():
                raw = sys.stdin.read()
                sequence = raw.partition("\\n")[2].strip()
                print("true" if is_valid(sequence) else "false")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function isValid(s) {
              const partners = { ")": "(", "]": "[", "}": "{" };
              const stack = [];
              for (const character of s) {
                if ("([{".includes(character)) {
                  stack.push(character);
                } else if (Object.prototype.hasOwnProperty.call(partners, character)) {
                  if (stack.length === 0 || stack.pop() !== partners[character]) {
                    return false;
                  }
                }
              }
              return stack.length === 0;
            }

            function main() {
              const raw = fs.readFileSync(0, "utf8");
              const sequence = raw.slice(raw.indexOf("\\n") + 1).trim();
              console.log(isValid(sequence) ? "true" : "false");
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_valid_parentheses, VALID_PARENTHESES_INPUT),
        judged_case(_valid_parentheses, "1\n("),
        judged_case(_valid_parentheses, "2\n)("),
        judged_case(_valid_parentheses, "4\n([)]"),
        judged_case(_valid_parentheses, "0\n", is_hidden=True),
        judged_case(_valid_parentheses, "6\n{[]}{}[", is_hidden=True),
        judged_case(_valid_parentheses, "8\n(((())))", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Longest Substring Without Repeating Characters
# --------------------------------------------------------------------------- #


def _longest_substring(stdin: str) -> str:
    lines = text_lines(stdin)
    # An empty string is a legal answer, so a missing second line is not an error.
    sequence = lines[1] if len(lines) > 1 else ""
    last_seen: dict[str, int] = {}
    best = 0
    start = 0
    for index, character in enumerate(sequence):
        if character in last_seen and last_seen[character] >= start:
            start = last_seen[character] + 1
        last_seen[character] = index
        best = max(best, index - start + 1)
    return str(best)


LONGEST_SUBSTRING_INPUT = "7\nabcabcbb"

LONGEST_SUBSTRING: dict[str, Any] = {
    "slug": "longest-substring-without-repeating-characters",
    "title": "Longest Substring Without Repeating Characters",
    "summary": "Find the length of the longest run of characters with no repeats.",
    "difficulty": "Medium",
    "topics": ["Strings", "Sliding Window", "Hash Maps"],
    "description": (
        "Given a string `s`, return the length of the longest substring that "
        "contains no repeated character.\n\n"
        "A substring is a contiguous part of the string, not a subsequence."
    ),
    "input_format": (
        "Line 1: `n`, the length of the string.\n"
        "Line 2: the string of `n` characters, drawn from letters and digits with no spaces."
    ),
    "output_format": "Print the length of the longest substring with no repeated character.",
    "constraints": "0 <= n <= 5 * 10^4. The string contains only letters, digits, and symbols.",
    "examples": [
        {
            "input": LONGEST_SUBSTRING_INPUT,
            "output": _longest_substring(LONGEST_SUBSTRING_INPUT),
            "explanation": "`abc` has no repeats, while `abca` does, so the answer is 3.",
        }
    ],
    "hints": [
        "Checking every substring is O(n^2). A substring with no repeats is a property you can maintain as you move, which is the signal that a sliding window is the right shape.",
        "Keep a window `s[start..index]` that is known to be free of repeats, and slide the right end one character at a time. The only thing that can break it is the new character having appeared inside the window.",
        "Remember the last index at which each character was seen. When the new character was last seen at position `p`, and `p` is inside the current window, move `start` to `p + 1`; otherwise leave `start` alone.",
        "Always take the maximum of `start` and `last_seen[character] + 1` when the character is repeated. Forgetting to clamp against `start` lets a window jump backwards and overcounts.",
        "Record the answer *after* updating `start`, and compute the length as `index - start + 1`. Storing the last seen index is what makes the clamp possible; a set of characters would not tell you where to jump to.",
    ],
    "explanation": (
        "Maintain a window `s[start..index]` that contains no repeated character. "
        "Move `index` through the string one position at a time and keep a map "
        "from each character to the index it was last seen at.\n\n"
        "When a new character arrives, the window is still valid unless that "
        "character is already inside it. If it was last seen at `p` and "
        "`p >= start`, the window has to be trimmed to start after that repeat, "
        "so `start` becomes `p + 1`. The `>= start` test matters: a repeat that "
        "fell out of the window earlier must not drag the window backwards.\n\n"
        "After the adjustment the window is valid again, and its length is "
        "`index - start + 1`, so the running maximum of those lengths is the "
        "answer. The pointer only ever moves forward, so the time is O(n) with "
        "O(min(n, alphabet)) space for the map."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(min(n, alphabet size))",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def longest_unique_substring(s):
                \"\"\"Return the length of the longest substring with no repeats.\"\"\"
                return 0


            def main():
                raw = sys.stdin.read()
                print(longest_unique_substring(raw.partition("\\n")[2].strip()))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function longestUniqueSubstring(s) {
              // Return the length of the longest substring with no repeats.
              return 0;
            }

            function main() {
              const raw = fs.readFileSync(0, "utf8");
              console.log(longestUniqueSubstring(raw.slice(raw.indexOf("\\n") + 1).trim()));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def longest_unique_substring(s):
                last_seen = {}
                best = 0
                start = 0
                for index, character in enumerate(s):
                    if character in last_seen and last_seen[character] >= start:
                        start = last_seen[character] + 1
                    last_seen[character] = index
                    best = max(best, index - start + 1)
                return best


            def main():
                raw = sys.stdin.read()
                print(longest_unique_substring(raw.partition("\\n")[2].strip()))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function longestUniqueSubstring(s) {
              const lastSeen = new Map();
              let best = 0;
              let start = 0;
              for (let index = 0; index < s.length; index += 1) {
                const character = s[index];
                if (lastSeen.has(character) && lastSeen.get(character) >= start) {
                  start = lastSeen.get(character) + 1;
                }
                lastSeen.set(character, index);
                best = Math.max(best, index - start + 1);
              }
              return best;
            }

            function main() {
              const raw = fs.readFileSync(0, "utf8");
              console.log(longestUniqueSubstring(raw.slice(raw.indexOf("\\n") + 1).trim()));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_longest_substring, LONGEST_SUBSTRING_INPUT),
        judged_case(_longest_substring, "3\npww"),
        judged_case(_longest_substring, "1\na"),
        judged_case(_longest_substring, "0\n", is_hidden=True),
        judged_case(_longest_substring, "5\ndvdf", is_hidden=True),
        judged_case(_longest_substring, "12\ntmmzuxt", is_hidden=True),
        judged_case(_longest_substring, "4\nabba", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Word Search
# --------------------------------------------------------------------------- #

_WORD_SEARCH_DIRECTIONS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


def _word_search(stdin: str) -> str:
    lines = text_lines(stdin)
    rows, cols = (int(token) for token in lines[0].split())
    grid = [list(line) for line in lines[1 : 1 + rows]]
    word = lines[1 + rows]

    def search(row: int, col: int, offset: int) -> bool:
        if grid[row][col] != word[offset]:
            return False
        if offset == len(word) - 1:
            return True
        # A letter may be used once, so the cell is marked for the length of this
        # path and restored afterwards. Without the mark, a word longer than the
        # grid would be found by walking back and forth over the same cell.
        grid[row][col] = "#"
        try:
            for row_step, col_step in _WORD_SEARCH_DIRECTIONS:
                next_row, next_col = row + row_step, col + col_step
                if 0 <= next_row < rows and 0 <= next_col < cols and search(
                    next_row, next_col, offset + 1
                ):
                    return True
        finally:
            grid[row][col] = word[offset]
        return False

    for row in range(rows):
        for col in range(cols):
            if search(row, col, 0):
                return "true"
    return "false"


WORD_SEARCH_INPUT = "3 4\nABCE\nSFCS\nADEE\nABCB"

WORD_SEARCH: dict[str, Any] = {
    "slug": "word-search",
    "title": "Word Search",
    "summary": "Decide whether a word exists in a grid, where letters may move in 8 directions.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Backtracking", "Depth-First Search"],
    "description": (
        "Given a grid of characters and a word, decide whether the word can be "
        "built from letters in the grid. A letter may be used at most once, and "
        "each step must move to an adjacent cell: horizontally, vertically, or "
        "diagonally.\n\n"
        "Return `true` if the word exists, otherwise `false`."
    ),
    "input_format": (
        "Line 1: `rows cols`, the size of the grid.\n"
        "Lines 2 to rows+1: one row of the grid as `cols` characters, with no spaces.\n"
        "Line rows+2: the word to look for."
    ),
    "output_format": "Print `true` if the word can be built in the grid, otherwise `false`, in lower case.",
    "constraints": (
        "1 <= rows, cols <= 100, 1 <= len(word) <= 100. The grid and the word "
        "contain only upper-case English letters."
    ),
    "examples": [
        {
            "input": WORD_SEARCH_INPUT,
            "output": _word_search(WORD_SEARCH_INPUT),
            "explanation": "A at row 0, column 0, then B, C, and B again at row 1, column 2, using right, right, down.",
        }
    ],
    "hints": [
        "A word is a path through the grid, so a depth-first search over cells is the natural shape. What you have to decide for yourself is how to stop a search that is going nowhere.",
        "Try every cell as the start of the word, and from each one walk along the eight directions. The search is a recursion over the position in the word.",
        "Write `search(row, col, index)` that answers: can the rest of the word starting at `index` be built from cell `(row, col)`? Base it on whether the character at that cell matches `word[index]`, and when `index` is the last letter, the answer is yes.",
        "A letter cannot be reused, so a cell used earlier in the current path must not be entered again. The cheapest way is to mark the cell as visited when you step onto it and unmark it when you step off, which is what makes this backtracking rather than plain DFS.",
        "There is no need to keep a separate visited set. Temporarily overwriting the cell with a character that cannot appear in the word -- for example `#` -- marks it and restoring the original character unmarks it, with no extra state to unwind.",
    ],
    "explanation": (
        "The word defines a path: every step moves to one of the eight neighbours "
        "and a cell may not be reused. Try every cell as a starting point and walk "
        "the word from there.\n\n"
        "`search(row, col, index)` answers whether the suffix of the word starting "
        "at `index` can be built from cell `(row, col)`. If the cell's character "
        "does not match `word[index]` the answer is no. If it matches and `index` "
        "is the last letter, the answer is yes. Otherwise mark the cell as used "
        "and recurse into each in-bounds neighbour, restoring the cell afterwards "
        "so other paths can still use it.\n\n"
        "That mark-and-restore is what makes this backtracking: a cell that was "
        "unusable on one path may be essential on another, so the state is undone "
        "rather than recorded permanently. Writing the mark as a temporary "
        "overwrite of the cell avoids a separate visited set entirely.\n\n"
        "The time is O(rows * cols * 8 * len(word)) in the worst case, which is "
        "why the first-character check at each step matters, and the space is "
        "O(len(word)) for the recursion."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(rows * cols * word length)",
    "expected_space_complexity": "O(word length)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def exists(grid, word):
                \"\"\"Return True when word can be built from letters in grid.\"\"\"
                return False


            def main():
                lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
                rows, cols = (int(token) for token in lines[0].split())
                grid = lines[1 : 1 + rows]
                print("true" if exists(grid, lines[1 + rows]) else "false")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function exists(grid, word) {
              // Return true when word can be built from letters in grid.
              return false;
            }

            function main() {
              const lines = fs
                .readFileSync(0, "utf8")
                .split(/\\r?\\n/)
                .map((line) => line.trim())
                .filter((line) => line.length > 0);
              const [rows, cols] = lines[0].split(/\\s+/).map(Number);
              // The grid is an array of character arrays rather than an array
              // of strings: the search marks a cell while it is using it, and
              // assigning to an index of a string silently does nothing in
              // JavaScript, so a string grid would let one cell be reused.
              const grid = lines.slice(1, 1 + rows).map((line) => line.split(""));
              console.log(exists(grid, lines[1 + rows]) ? "true" : "false");
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys

            DIRECTIONS = (
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1), (0, 1),
                (1, -1), (1, 0), (1, 1),
            )


            def exists(grid, word):
                rows = len(grid)
                cols = len(grid[0])

                def search(row, col, index):
                    if grid[row][col] != word[index]:
                        return False
                    if index == len(word) - 1:
                        return True
                    saved = grid[row][col]
                    grid[row][col] = "#"
                    try:
                        for row_step, col_step in DIRECTIONS:
                            next_row, next_col = row + row_step, col + col_step
                            if 0 <= next_row < rows and 0 <= next_col < cols:
                                if search(next_row, next_col, index + 1):
                                    return True
                    finally:
                        grid[row][col] = saved
                    return False

                for row in range(rows):
                    for col in range(cols):
                        if search(row, col, 0):
                            return True
                return False


            def main():
                lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
                rows, cols = (int(token) for token in lines[0].split())
                grid = [list(line) for line in lines[1 : 1 + rows]]
                print("true" if exists(grid, lines[1 + rows]) else "false")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function exists(grid, word) {
              const rows = grid.length;
              const cols = grid[0].length;
              const directions = [
                [-1, -1], [-1, 0], [-1, 1],
                [0, -1], [0, 1],
                [1, -1], [1, 0], [1, 1],
              ];

              function search(row, col, index) {
                if (grid[row][col] !== word[index]) {
                  return false;
                }
                if (index === word.length - 1) {
                  return true;
                }
                const saved = grid[row][col];
                grid[row][col] = "#";
                try {
                  for (const [rowStep, colStep] of directions) {
                    const nextRow = row + rowStep;
                    const nextCol = col + colStep;
                    if (nextRow >= 0 && nextRow < rows && nextCol >= 0 && nextCol < cols) {
                      if (search(nextRow, nextCol, index + 1)) {
                        return true;
                      }
                    }
                  }
                } finally {
                  grid[row][col] = saved;
                }
                return false;
              }

              for (let row = 0; row < rows; row += 1) {
                for (let col = 0; col < cols; col += 1) {
                  if (search(row, col, 0)) {
                    return true;
                  }
                }
              }
              return false;
            }

            function main() {
              const lines = fs
                .readFileSync(0, "utf8")
                .split(/\\r?\\n/)
                .map((line) => line.trim())
                .filter((line) => line.length > 0);
              const [rows, cols] = lines[0].split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows).map((line) => line.split(""));
              console.log(exists(grid, lines[1 + rows]) ? "true" : "false");
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_word_search, WORD_SEARCH_INPUT),
        judged_case(_word_search, "3 4\nABCE\nSFCS\nADEE\nABFB"),
        judged_case(_word_search, "1 1\nA\nA"),
        judged_case(_word_search, "1 2\nAB\nA"),
        judged_case(_word_search, "2 2\nAB\nCD\nAC", is_hidden=True),
        judged_case(_word_search, "3 4\nABCE\nSFCS\nADEE\nSEE", is_hidden=True),
        judged_case(_word_search, "1 5\nAAAAA\nAAAAAB", is_hidden=True),
        judged_case(_word_search, "2 3\nABC\nDEF\nCF", is_hidden=True),
    ],
}


STRINGS_AND_STACKS_PROBLEMS: tuple[dict[str, Any], ...] = (
    VALID_PARENTHESES,
    LONGEST_SUBSTRING,
    WORD_SEARCH,
)
