"""Dynamic programming: what a table of answers buys you.

Four problems in three shapes, chosen so the technique is seen rather than
memorised:

* **Longest increasing subsequence** has an O(n^2) table and an O(n log n)
  answer that does not build one. Both are here, the slow one as the oracle and
  the fast one as the solution, because the difference between them is the
  lesson: the table was never the point, the *state* was.
* **Longest common subsequence** and **edit distance** are the same recurrence
  read in two directions -- top-down with memoisation, and bottom-up over a
  single row. Seeing both, and seeing that the one-row version is the two-row
  version with the older row thrown away, is what makes the technique reusable.
* **Count string segmentations** asks for a *number* of answers rather than the
  best one, which is the point where counting replaces maximising and the state
  stops being a cost.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source, text_lines

# --------------------------------------------------------------------------- #
# Longest increasing subsequence
# --------------------------------------------------------------------------- #

LIS_INPUT = "8\n10 9 2 5 3 7 101 18"

_LIS_BULK = [((index * 7919) % 501) - 250 for index in range(1200)]
LIS_BULK_INPUT = f"{len(_LIS_BULK)}\n" + " ".join(str(value) for value in _LIS_BULK)


def _lis_length(stdin: str) -> str:
    """The table every learner writes first: best ending at each index."""
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    if n == 0:
        return "0"
    best = [1] * n
    for index in range(1, n):
        for previous in range(index):
            if nums[previous] < nums[index] and best[previous] + 1 > best[index]:
                best[index] = best[previous] + 1
    return str(max(best))


LONGEST_INCREASING_SUBSEQUENCE: dict[str, Any] = {
    "slug": "longest-increasing-subsequence",
    "title": "Longest Increasing Subsequence",
    "summary": "Find the longest strictly increasing run of values, in order.",
    "difficulty": "Medium",
    "topics": ["Dynamic Programming", "Arrays", "Binary Search"],
    "description": (
        "Given an integer array `nums`, return the length of its longest "
        "**strictly** increasing subsequence.\n\n"
        "A subsequence keeps the original order but may skip values, so the answer "
        "is not the length of the longest run of adjacent values. Equal values "
        "never extend a strictly increasing subsequence."
    ),
    "input_format": "Line 1: `n`, the number of values.\nLine 2: `n` integers.",
    "output_format": "Print the length of the longest strictly increasing subsequence.",
    "constraints": "0 <= n <= 10^5 and -10^5 <= nums[i] <= 10^5. An empty array has the answer 0.",
    "examples": [
        {
            "input": LIS_INPUT,
            "output": _lis_length(LIS_INPUT),
            "explanation": "2, 3, 7, 101 is increasing and in order, so the answer is 4.",
        },
        {
            "input": "6\n7 7 7 7 7 7",
            "output": _lis_length("6\n7 7 7 7 7 7"),
            "explanation": "Equal values do not extend a strictly increasing subsequence, so only one value is used.",
        },
    ],
    "hints": [
        "The table form is: for each index, the longest increasing subsequence that ends there. Extending one of them is a maximum over all earlier smaller values, which is O(n^2) as written.",
        "O(n^2) is too slow for the largest inputs, but the *table* is the wrong object to keep. What the answer actually needs from an earlier value is only one number: how long a subsequence could have been if that value were the last one.",
        "Keep a sorted list of those numbers instead of one per index. For each value, find its position in that list by binary search: the position is the length of the best subsequence this value can extend, and the value replaces the entry there.",
        "Replace, do not insert. The list stays sorted because the entry being replaced is at least as large as the new value, and every later entry is larger still, so its length in the list is exactly the length of the longest subsequence that could end there.",
        "Use `lower_bound`, not `upper_bound`: replacing the first entry that is *greater than or equal to* the value is what makes duplicates refuse to extend the sequence. Using `upper_bound` answers the longest non-decreasing subsequence instead, which is a different question.",
    ],
    "explanation": (
        "The O(n^2) version defines `best[i]` as the length of the longest "
        "increasing subsequence ending at index `i`, and computes "
        "`best[i] = 1 + max(best[j])` over all `j < i` with `nums[j] < "
        "nums[i]`. It is correct and it is quadratic, because asking 'which "
        "earlier value is the best predecessor' is a linear scan.\n\n"
        "The faster version keeps something different. Instead of one length per "
        "index, maintain a sorted array `tails` where `tails[k]` is the smallest "
        "possible last value of an increasing subsequence of length `k + 1` seen "
        "so far. For each value, binary search for the first entry of `tails` "
        "that is greater than or equal to it, say at position `p`. Then:\n\n"
        "* `p == 0` means the value starts a length-1 subsequence.\n"
        "* Otherwise `tails[p - 1] < value`, so this value extends a subsequence "
        "of length `p` into one of length `p + 1`.\n"
        "* Replacing `tails[p]` with the value records that it ends a length-`p + "
        "1` subsequence, and doing so can only help later values, because a "
        "smaller tail is never worse for extension.\n\n"
        "The array stays sorted after the replacement, because everything after "
        "position `p` is strictly greater than the value being written, which is "
        "exactly the binary-search precondition. Its final length is the answer, "
        "because `tails` never contains a gap: a length-`p + 1` subsequence always "
        "implies one of every shorter length ending earlier or at the same place.\n\n"
        "One binary search per value is O(n log n) time, and `tails` holds at most "
        "n entries. Note `tails` is not itself a subsequence -- only its length "
        "is the answer, which is why the problem asks for a length."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n log n)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def longest_increasing_length(nums):
                \"\"\"Return the length of the longest strictly increasing subsequence.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(longest_increasing_length(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function longestIncreasingLength(nums) {
              // Return the length of the longest strictly increasing subsequence.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(longestIncreasingLength(nums));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int longestIncreasingLength(int[] nums) {
                    // Return the length of the longest strictly increasing subsequence.
                    return 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    System.out.println(longestIncreasingLength(nums));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys
            from bisect import bisect_left


            def longest_increasing_length(nums):
                tails = []
                for value in nums:
                    position = bisect_left(tails, value)
                    if position == len(tails):
                        tails.append(value)
                    else:
                        tails[position] = value
                return len(tails)


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(longest_increasing_length(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function longestIncreasingLength(nums) {
              const tails = [];
              for (const value of nums) {
                let low = 0;
                let high = tails.length;
                while (low < high) {
                  const middle = low + Math.floor((high - low) / 2);
                  if (tails[middle] < value) {
                    low = middle + 1;
                  } else {
                    high = middle;
                  }
                }
                if (low === tails.length) {
                  tails.push(value);
                } else {
                  tails[low] = value;
                }
              }
              return tails.length;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(longestIncreasingLength(nums));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int longestIncreasingLength(int[] nums) {
                    int[] tails = new int[nums.length];
                    int size = 0;
                    for (int value : nums) {
                        int low = 0;
                        int high = size;
                        while (low < high) {
                            int middle = low + (high - low) / 2;
                            if (tails[middle] < value) {
                                low = middle + 1;
                            } else {
                                high = middle;
                            }
                        }
                        tails[low] = value;
                        if (low + 1 > size) {
                            size = low + 1;
                        }
                    }
                    return size;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    System.out.println(longestIncreasingLength(nums));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_lis_length, LIS_INPUT),
        judged_case(_lis_length, "1\n5"),
        judged_case(_lis_length, "6\n7 7 7 7 7 7"),
        judged_case(_lis_length, "5\n5 4 3 2 1"),
        judged_case(_lis_length, "0", is_hidden=True),
        judged_case(_lis_length, "10\n1 2 3 4 5 6 7 8 9 10", is_hidden=True),
        judged_case(_lis_length, "6\n-3 -2 -1 0 1 2", is_hidden=True),
        judged_case(_lis_length, "8\n3 5 7 9 10 8 6 4", is_hidden=True),
        judged_case(_lis_length, "9\n-1 -1 0 0 1 1 -2 2 2", is_hidden=True),
        judged_case(_lis_length, LIS_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Longest common subsequence
# --------------------------------------------------------------------------- #

LCS_INPUT = "6 5\nabcdef\nbdf"


def _lcs_length(stdin: str) -> str:
    """Top-down with memoisation: the same table, built in the other order."""
    parts = text_lines(stdin)
    first = parts[1]
    second = parts[2]
    cache: dict[tuple[int, int], int] = {}

    def best(i: int, j: int) -> int:
        if i == 0 or j == 0:
            return 0
        key = (i, j)
        if key in cache:
            return cache[key]
        if first[i - 1] == second[j - 1]:
            answer = best(i, j - 1) + 1
        else:
            answer = max(best(i - 1, j), best(i, j - 1))
        cache[key] = answer
        return answer

    return str(best(len(first), len(second)))


LONGEST_COMMON_SUBSEQUENCE: dict[str, Any] = {
    "slug": "longest-common-subsequence",
    "title": "Longest Common Subsequence",
    "summary": "Longest run of characters two strings keep in the same order.",
    "difficulty": "Medium",
    "topics": ["Dynamic Programming", "Strings", "Recursion"],
    "description": (
        "Given two strings `a` and `b`, return the length of their longest "
        "common subsequence.\n\n"
        "A subsequence may skip characters but must keep their order, so `\"abc\"` "
        "and `\"acb\"` share `\"ab\"` of length 2 rather than 3."
    ),
    "input_format": (
        "Line 1: `n m`, the lengths of the two strings.\n"
        "Line 2: `a`, a string of `n` lowercase letters.\n"
        "Line 3: `b`, a string of `m` lowercase letters."
    ),
    "output_format": "Print the length of the longest common subsequence.",
    "constraints": "1 <= n, m <= 2000 and both strings consist of lowercase letters.",
    "examples": [
        {
            "input": LCS_INPUT,
            "output": _lcs_length(LCS_INPUT),
            "explanation": "b, d and f appear in both strings in that order.",
        },
        {
            "input": "4 4\nabcd\nabdc",
            "output": _lcs_length("4 4\nabcd\nabdc"),
            "explanation": "a, b and c are in the same order in both, giving 3; a, b and d are not, because d comes last in the first string.",
        },
    ],
    "hints": [
        "Ask the question that only mentions prefixes: what is the longest common subsequence of the first i characters of a and the first j characters of b? The full answer is the case i = n, j = m.",
        "When the last characters of the two prefixes match, they can both be taken and the answer is one more than the answer for the prefixes without them. When they differ, one of the two last characters has to be dropped, so take the better of the two smaller answers.",
        "Written that way the recurrence is self-referential, so it either recurses without remembering and blows up exponentially, or it fills a table. Top-down, the fix is a cache keyed by (i, j): each state is computed once, which is O(n * m).",
        "Bottom-up, notice that row i only ever reads row i - 1 and the cell to its left. So one row of storage is enough: keep the current row, overwrite it left to right, and keep the old value of the cell above in a single variable called the diagonal.",
        "The two characters do not have to be equal in the diagonal step: `max(diagonal + (a[i-1] != b[j-1]))` covers all three possibilities at once and is equivalent, because a substitution of a matching character is never better than taking the diagonal alone.",
    ],
    "explanation": (
        "The state is a pair of prefixes, `(i, j)`: the longest common "
        "subsequence of `a[:i]` and `b[:j]`. The recurrence has two cases.\n\n"
        "If `a[i - 1] == b[j - 1]`, both final characters can be used, and no "
        "longer answer exists without them, so `best[i][j] = best[i - 1][j - 1] + "
        "1`. If they differ, a subsequence cannot use both final characters -- it "
        "would have to use them in order, and they are in different positions -- so "
        "one of them is dropped and `best[i][j] = max(best[i - 1][j], best[i][j - "
        "1])`. The base cases are `best[0][j] = best[i][0] = 0`, since a prefix of "
        "length zero shares nothing.\n\n"
        "Written recursively the states overlap heavily, which is exponential "
        "without a cache; memoising on `(i, j)` makes each of the `n * m` states "
        "computed once. Written bottom-up, the table is filled in increasing `i` "
        "and then increasing `j`, and the only dependencies are the cell to the "
        "left and the cell above -- so the whole table collapses into a single row "
        "plus one variable for the old diagonal.\n\n"
        "The table version costs O(n * m) time and O(n * m) space, the rolling "
        "version O(n * m) time and O(m) space, and both are the same recurrence. "
        "Reaching for the rolling row is a mechanical optimisation once the "
        "dependency structure is understood, which is worth more than memorising "
        "it."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n * m)",
    "expected_space_complexity": "O(m)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def lcs_length(a, b):
                \"\"\"Return the length of the longest common subsequence of a and b.\"\"\"
                return 0


            def main():
                data = sys.stdin.read().split()
                print(lcs_length(data[2], data[3]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function lcsLength(a, b) {
              // Return the length of the longest common subsequence of a and b.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              console.log(lcsLength(data[2], data[3]));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int lcsLength(String a, String b) {
                    // Return the length of the longest common subsequence of a and b.
                    return 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    in.nextInt();
                    in.nextInt();
                    String a = in.next();
                    String b = in.next();
                    System.out.println(lcsLength(a, b));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def lcs_length(a, b):
                shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
                row = [0] * (len(shorter) + 1)
                for character in longer:
                    diagonal = 0
                    for index, other in enumerate(shorter, start=1):
                        above = row[index]
                        if character == other:
                            row[index] = diagonal + 1
                        elif above > row[index - 1]:
                            row[index] = above
                        else:
                            row[index] = row[index - 1]
                        diagonal = above
                return row[len(shorter)]


            def main():
                data = sys.stdin.read().split()
                print(lcs_length(data[2], data[3]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function lcsLength(a, b) {
              const [shorter, longer] = a.length <= b.length ? [a, b] : [b, a];
              const row = new Array(shorter.length + 1).fill(0);
              for (const character of longer) {
                let diagonal = 0;
                for (let index = 1; index <= shorter.length; index += 1) {
                  const above = row[index];
                  if (character === shorter[index - 1]) {
                    row[index] = diagonal + 1;
                  } else if (above > row[index - 1]) {
                    row[index] = above;
                  } else {
                    row[index] = row[index - 1];
                  }
                  diagonal = above;
                }
              }
              return row[shorter.length];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              console.log(lcsLength(data[2], data[3]));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int lcsLength(String a, String b) {
                    String shorter = a.length() <= b.length() ? a : b;
                    String longer = a.length() <= b.length() ? b : a;
                    int[] row = new int[shorter.length() + 1];
                    for (int p = 0; p < longer.length(); p += 1) {
                        int diagonal = 0;
                        for (int index = 1; index <= shorter.length(); index += 1) {
                            int above = row[index];
                            if (longer.charAt(p) == shorter.charAt(index - 1)) {
                                row[index] = diagonal + 1;
                            } else if (above > row[index - 1]) {
                                row[index] = above;
                            } else {
                                row[index] = row[index - 1];
                            }
                            diagonal = above;
                        }
                    }
                    return row[shorter.length()];
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    in.nextInt();
                    in.nextInt();
                    String a = in.next();
                    String b = in.next();
                    System.out.println(lcsLength(a, b));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_lcs_length, LCS_INPUT),
        judged_case(_lcs_length, "1 1\na\na"),
        judged_case(_lcs_length, "3 3\nabc\nxyz"),
        judged_case(_lcs_length, "4 4\nabcd\nabdc"),
        judged_case(_lcs_length, "5 5\naaaaa\naaaaa", is_hidden=True),
        judged_case(_lcs_length, "6 6\nabcdef\nfedcba", is_hidden=True),
        judged_case(_lcs_length, "7 4\nabcabca\ncaba", is_hidden=True),
        judged_case(_lcs_length, "10 10\nabracadabra\nbracadabra", is_hidden=True),
        judged_case(
            _lcs_length,
            "200 200\n"
            + "".join(chr(ord("a") + (index * 7) % 6) for index in range(200))
            + "\n"
            + "".join(chr(ord("a") + (index * 11) % 6) for index in range(200)),
            is_hidden=True,
        ),
    ],
}


# --------------------------------------------------------------------------- #
# Edit distance
# --------------------------------------------------------------------------- #

EDIT_DISTANCE_INPUT = "3 3\nkitten\nsitting"


def _edit_distance(stdin: str) -> str:
    """One rolling row, filled left to right, with the diagonal saved first."""
    parts = text_lines(stdin)
    a = parts[1]
    b = parts[2]
    row = list(range(len(b) + 1))
    for i, left in enumerate(a, start=1):
        diagonal = row[0]
        row[0] = i
        for j, right in enumerate(b, start=1):
            above = row[j]
            if left == right:
                row[j] = diagonal
            else:
                row[j] = 1 + min(diagonal, row[j - 1], above)
            diagonal = above
    return str(row[len(b)])


EDIT_DISTANCE: dict[str, Any] = {
    "slug": "edit-distance",
    "title": "Edit Distance",
    "summary": "Turn one string into another with as few single-character edits as possible.",
    "difficulty": "Hard",
    "topics": ["Dynamic Programming", "Strings", "Recursion"],
    "description": (
        "You are given two strings `a` and `b`. In one operation you may delete a "
        "character from `a`, insert a character into `a`, or replace one character "
        "of `a` with another. Each operation costs one.\n\n"
        "Print the minimum number of operations needed to turn `a` into `b`."
    ),
    "input_format": (
        "Line 1: `n m`, the lengths of the two strings.\n"
        "Line 2: `a`, a string of `n` lowercase letters.\n"
        "Line 3: `b`, a string of `m` lowercase letters."
    ),
    "output_format": "Print the minimum number of single-character edits.",
    "constraints": (
        "1 <= n, m <= 2000 and both strings consist of lowercase letters. Two "
        "strings that share no characters need `max(n, m)` edits, so the answer "
        "never exceeds 2000."
    ),
    "examples": [
        {
            "input": EDIT_DISTANCE_INPUT,
            "output": _edit_distance(EDIT_DISTANCE_INPUT),
            "explanation": "Replace k with s, e with i, and insert g at the end: three edits.",
        },
        {
            "input": "4 4\nabcd\nabdc",
            "output": _edit_distance("4 4\nabcd\nabdc"),
            "explanation": "c and d have swapped places, so one replacement fixes it.",
        },
    ],
    "hints": [
        "The state is again a pair of prefixes, but the answer is a cost instead of a length, and the cost has to be a minimum over *all* ways of finishing the shorter string.",
        "Look at the last character of each prefix. If they are equal, no operation is needed for it and the answer is the cost of the prefixes without them. If they differ, exactly one of three operations resolves the mismatch, and the answer is one plus the best of the three smaller states.",
        "The three operations are not symmetric, and mixing them up is the usual mistake: deleting the last character of `a` gives `a[:i-1]` against `b[:j]`, inserting the last character of `b` gives `a[:i]` against `b[:j-1]`, and replacing gives `a[:i-1]` against `b[:j-1]`.",
        "The base row is not all zeros: the cost of turning anything into the empty string is the length of that thing, because every character has to be deleted. Starting from zero makes the answer smaller than it can be, and it fails on unequal lengths first.",
        "Each state needs the cell above, the cell to the left and the diagonal, so one row plus a saved diagonal is enough. Fill left to right and keep the previous value of the cell above in a variable *before* overwriting it -- saving it after is the classic off-by-one.",
    ],
    "explanation": (
        "Let `cost[i][j]` be the minimum edits turning `a[:i]` into `b[:j]`. The "
        "base cases are `cost[i][0] = i` and `cost[0][j] = j`: an empty target "
        "costs one deletion per character, and building anything from nothing "
        "costs one insertion per character.\n\n"
        "For `i, j > 0`, if `a[i - 1] == b[j - 1]` the two characters already "
        "match and `cost[i][j] = cost[i - 1][j - 1]`. Otherwise the final "
        "mismatch must be resolved by one of three operations, and taking the "
        "cheapest gives `cost[i][j] = 1 + min(cost[i - 1][j], cost[i][j - 1], "
        "cost[i - 1][j - 1])`: delete, insert, or replace. Every sequence of "
        "edits ends with one of those three, and each of them extends a valid "
        "sequence for a shorter pair of prefixes, so the minimum is exactly the "
        "optimum.\n\n"
        "A single cell therefore depends on three cells: above, left, and the "
        "diagonal. Filling the table in row-major order means the row above is "
        "finished and the current row's left neighbour is already final, so the "
        "whole table reduces to one array of `m + 1` costs plus one variable "
        "holding the previous value of the diagonal.\n\n"
        "The result is O(n * m) time with O(m) space. The exponent-free structure "
        "comes from the fact that each of the `n * m` states is computed exactly "
        "once, which is the entire difference between this and the exponential "
        "recursion it is derived from."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n * m)",
    "expected_space_complexity": "O(n * m)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def edit_distance(a, b):
                \"\"\"Return the fewest single-character edits turning a into b.\"\"\"
                return 0


            def main():
                data = sys.stdin.read().split()
                print(edit_distance(data[2], data[3]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function editDistance(a, b) {
              // Return the fewest single-character edits turning a into b.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              console.log(editDistance(data[2], data[3]));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int editDistance(String a, String b) {
                    // Return the fewest single-character edits turning a into b.
                    return 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    in.nextInt();
                    in.nextInt();
                    String a = in.next();
                    String b = in.next();
                    System.out.println(editDistance(a, b));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def edit_distance(a, b):
                rows = len(a) + 1
                columns = len(b) + 1
                table = [[0] * columns for _ in range(rows)]
                for i in range(rows):
                    table[i][0] = i
                for j in range(columns):
                    table[0][j] = j
                for i in range(1, rows):
                    for j in range(1, columns):
                        if a[i - 1] == b[j - 1]:
                            table[i][j] = table[i - 1][j - 1]
                        else:
                            table[i][j] = 1 + min(
                                table[i - 1][j], table[i][j - 1], table[i - 1][j - 1]
                            )
                return table[len(a)][len(b)]


            def main():
                data = sys.stdin.read().split()
                print(edit_distance(data[2], data[3]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function editDistance(a, b) {
              const table = [];
              for (let i = 0; i <= a.length; i += 1) {
                table.push(new Array(b.length + 1).fill(0));
                table[i][0] = i;
              }
              for (let j = 0; j <= b.length; j += 1) {
                table[0][j] = j;
              }
              for (let i = 1; i <= a.length; i += 1) {
                for (let j = 1; j <= b.length; j += 1) {
                  if (a[i - 1] === b[j - 1]) {
                    table[i][j] = table[i - 1][j - 1];
                  } else {
                    table[i][j] = 1 + Math.min(
                      table[i - 1][j],
                      table[i][j - 1],
                      table[i - 1][j - 1]
                    );
                  }
                }
              }
              return table[a.length][b.length];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              console.log(editDistance(data[2], data[3]));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int editDistance(String a, String b) {
                    int[][] table = new int[a.length() + 1][b.length() + 1];
                    for (int i = 0; i <= a.length(); i += 1) {
                        table[i][0] = i;
                    }
                    for (int j = 0; j <= b.length(); j += 1) {
                        table[0][j] = j;
                    }
                    for (int i = 1; i <= a.length(); i += 1) {
                        for (int j = 1; j <= b.length(); j += 1) {
                            if (a.charAt(i - 1) == b.charAt(j - 1)) {
                                table[i][j] = table[i - 1][j - 1];
                            } else {
                                table[i][j] = 1 + Math.min(
                                        table[i - 1][j],
                                        Math.min(table[i][j - 1], table[i - 1][j - 1]));
                            }
                        }
                    }
                    return table[a.length()][b.length()];
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    in.nextInt();
                    in.nextInt();
                    String a = in.next();
                    String b = in.next();
                    System.out.println(editDistance(a, b));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_edit_distance, EDIT_DISTANCE_INPUT),
        judged_case(_edit_distance, "1 1\na\na"),
        judged_case(_edit_distance, "2 1\nab\na"),
        judged_case(_edit_distance, "2 2\nab\nba"),
        judged_case(_edit_distance, "5 5\nsunday\nsaturday", is_hidden=True),
        judged_case(_edit_distance, "6 6\nabcdef\nazced", is_hidden=True),
        judged_case(_edit_distance, "10 1\nabcdefghij\na", is_hidden=True),
        judged_case(_edit_distance, "1 10\na\nabcdefghij", is_hidden=True),
        judged_case(
            _edit_distance,
            "300 300\n"
            + "".join(chr(ord("a") + (index * 5 + 1) % 8) for index in range(300))
            + "\n"
            + "".join(chr(ord("a") + (index * 7 + 3) % 8) for index in range(300)),
            is_hidden=True,
        ),
    ],
}


# --------------------------------------------------------------------------- #
# Count string segmentations
# --------------------------------------------------------------------------- #

SEGMENTATIONS_INPUT = "2\ncatdog\ncat\ndog"


def _count_segmentations(stdin: str) -> str:
    """Enumerate every segmentation and count them. Exponential, and certain."""
    parts = text_lines(stdin)
    k = int(parts[0])
    subject = parts[1]
    words = parts[2 : 2 + k]

    found = [0]

    def walk(at: int) -> None:
        if at == len(subject):
            found[0] += 1
            return
        for word in words:
            if subject.startswith(word, at):
                walk(at + len(word))

    walk(0)
    return str(found[0])


COUNT_STRING_SEGMENTATIONS: dict[str, Any] = {
    "slug": "count-string-segmentations",
    "title": "Count String Segmentations",
    "summary": "Count the ways to cut a string into dictionary words.",
    "difficulty": "Hard",
    "topics": ["Dynamic Programming", "Strings", "Recursion", "Memoisation"],
    "description": (
        "You are given a string `s` and a dictionary of distinct words. Count how "
        "many ways `s` can be cut into a sequence of dictionary words, using the "
        "whole string.\n\n"
        "Words may be reused, and two cuts are different when they place a boundary "
        "somewhere different -- so `\"aaaa\"` cut into `\"aa\" + \"aa\"` and into "
        "`\"a\" + \"a\" + \"a\" + \"a\"` are two of several ways, not two "
        "solutions."
    ),
    "input_format": (
        "Line 1: `k`, the number of dictionary words.\n"
        "Line 2: `s`, the string to cut.\n"
        "Lines 3 to k+2: one dictionary word each, all distinct, in any order."
    ),
    "output_format": "Print the number of ways to cut s into dictionary words. Print 0 if there is no such cut.",
    "constraints": (
        "1 <= k <= 100, 1 <= len(s) <= 300, every word is 1..20 lowercase letters, "
        "and the words are distinct. The count can be exponential in len(s), so it "
        "is reported as an exact integer."
    ),
    "examples": [
        {
            "input": SEGMENTATIONS_INPUT,
            "output": _count_segmentations(SEGMENTATIONS_INPUT),
            "explanation": "cat + dog is the only cut, so the answer is 1.",        },
        {
            "input": "3\naaaaaaa\naaa\naa\na",
            "output": _count_segmentations("3\naaaaaaa\naaa\naa\na"),
            "explanation": "Every composition of 7 into parts of 1, 2 and 3 works, and there are 44 of them.",
        },
    ],
    "hints": [
        "Enumerating the cuts is the honest first attempt and it is exponential, which is exactly what a table of answers is for. Notice that many different prefixes of `s` lead to the *same* remaining suffix, and they therefore lead to the same number of completions.",
        "The state is a position in `s`: how many ways are there to cut `s[at:]`? The base case is `at == len(s)`, which is one way -- the empty remainder has exactly one cut, namely taking nothing.",
        "For each dictionary word, if it starts at `at`, add the answer for the position just past it. The question is only which position you have already solved when you arrive, which is what memoisation is for: a cache keyed by `at` turns the enumeration into one visit per position.",
        "Check `s.startswith(word, at)` rather than comparing slices. It tests the same thing without building a new string at every position, and it is the difference between comfortable and slow at len(s) = 300.",
        "Distinct words matter for correctness, not tidiness. A dictionary listed twice would count every cut using that word twice over, which is not what 'a dictionary' means.",
    ],
    "explanation": (
        "Two cuts of `s` that agree on everything up to position `p` have exactly "
        "the same completions available from `p` onwards -- the rest of the "
        "dictionary is still available and the remaining suffix is still the same "
        "string. So the number of completions depends only on the position, which "
        "is what makes a table of positions the right state.\n\n"
        "Define `ways(at)` as the number of cuts of the suffix `s[at:]`. The base "
        "case is `ways(len(s)) = 1`: there is exactly one way to cut nothing, and "
        "that is what terminates a successful recursion. Otherwise, every cut of "
        "`s[at:]` begins with some dictionary word `w` that matches at `at`, so "
        "`ways(at)` is the sum of `ways(at + len(w))` over all such `w`.\n\n"
        "Computed as written this recurses exponentially, because every position "
        "is reached once per distinct way of reaching it. Memoising on `at` makes "
        "each of the `len(s) + 1` positions computed once, which turns an "
        "exponential count into `O(len(s) * k * wordlen)` time. Bottom-up is the "
        "same recurrence filled from the end of the string backwards.\n\n"
        "The state here is a count rather than a best value, and that is the step "
        "most learners find surprising: the same structure answers 'how many' once "
        "the base case becomes 1 instead of 0 and the combination step becomes a "
        "sum instead of a maximum."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(len(s) * k * max word length)",
    "expected_space_complexity": "O(len(s))",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def count_segmentations(subject, words):
                \"\"\"Return how many ways subject can be cut into dictionary words.\"\"\"
                return 0


            def main():
                data = sys.stdin.read().split()
                k = int(data[0])
                print(count_segmentations(data[1], data[2 : 2 + k]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countSegmentations(subject, words) {
              // Return how many ways subject can be cut into dictionary words.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              console.log(countSegmentations(data[1], data.slice(2, 2 + k)));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static long countSegmentations(String subject, String[] words) {
                    // Return how many ways subject can be cut into dictionary words.
                    return 0L;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int k = in.nextInt();
                    String subject = in.next();
                    String[] words = new String[k];
                    for (int i = 0; i < k; i += 1) {
                        words[i] = in.next();
                    }
                    System.out.println(countSegmentations(subject, words));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def count_segmentations(subject, words):
                memo = {}

                def ways(at):
                    if at == len(subject):
                        return 1
                    if at in memo:
                        return memo[at]
                    total = 0
                    for word in words:
                        if subject.startswith(word, at):
                            total += ways(at + len(word))
                    memo[at] = total
                    return total

                return ways(0)


            def main():
                data = sys.stdin.read().split()
                k = int(data[0])
                print(count_segmentations(data[1], data[2 : 2 + k]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countSegmentations(subject, words) {
              const memo = new Array(subject.length + 1).fill(-1);

              function ways(at) {
                if (at === subject.length) {
                  return 1;
                }
                if (memo[at] !== -1) {
                  return memo[at];
                }
                let total = 0;
                for (const word of words) {
                  if (subject.startsWith(word, at)) {
                    total += ways(at + word.length);
                  }
                }
                memo[at] = total;
                return total;
              }

              return ways(0);
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              console.log(countSegmentations(data[1], data.slice(2, 2 + k)));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;
            import java.util.Arrays;

            public class Main {
                static long countSegmentations(String subject, String[] words) {
                    int length = subject.length();
                    long[] ways = new long[length + 1];
                    ways[length] = 1L;
                    for (int at = length - 1; at >= 0; at -= 1) {
                        long total = 0L;
                        for (String word : words) {
                            if (subject.startsWith(word, at)) {
                                total += ways[at + word.length()];
                            }
                        }
                        ways[at] = total;
                    }
                    return ways[0];
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int k = in.nextInt();
                    String subject = in.next();
                    String[] words = new String[k];
                    for (int i = 0; i < k; i += 1) {
                        words[i] = in.next();
                    }
                    System.out.println(countSegmentations(subject, words));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_count_segmentations, SEGMENTATIONS_INPUT),
        judged_case(_count_segmentations, "3\naaaaaaa\naaa\naa\na"),
        judged_case(_count_segmentations, "2\nabc\nab\nc"),
        judged_case(_count_segmentations, "2\npurple\npur\nple"),
        judged_case(_count_segmentations, "2\nabc\nab\nxyz", is_hidden=True),
        judged_case(_count_segmentations, "1\naaaaa\naa", is_hidden=True),
        judged_case(_count_segmentations, "3\naabbaa\naa\nb\na", is_hidden=True),
        judged_case(_count_segmentations, "2\nabcdef\nabc\ndef", is_hidden=True),
        judged_case(_count_segmentations, "1\nabc\na", is_hidden=True),
        judged_case(
            _count_segmentations,
            "6\n" + "ab" * 10 + "\na\nb\naa\nab\nba\nbb",
            is_hidden=True,
        ),
    ],
}


DYNAMIC_PROGRAMMING_PROBLEMS: tuple[dict[str, Any], ...] = (
    LONGEST_INCREASING_SUBSEQUENCE,
    LONGEST_COMMON_SUBSEQUENCE,
    EDIT_DISTANCE,
    COUNT_STRING_SEGMENTATIONS,
)
