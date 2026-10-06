"""Binary search: the halving, the bounds, and the answer hiding in a range.

Three problems, and three different things binary search is good for. Searching a
rotated array is the classic -- one comparison still eliminates half the array,
because at least one of the two halves around the midpoint is ordered. Finding a
value's first and last position replaces "equal?" with "at least?" and "greater
than?", which is the lower-bound and upper-bound search every library exposes.
Splitting an array minimises a *quantity* rather than finding a value, so there
is nothing to search for: the search space is the range of possible answers and
the test is whether that answer is achievable.

That third one is the one worth internalising. Binary search is a technique for
answering a monotone yes/no question quickly, and "is there a way to split this
array with no part larger than X?" is monotone in X, which is the whole reason
the technique transfers.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source

# --------------------------------------------------------------------------- #
# Search in a rotated sorted array
# --------------------------------------------------------------------------- #

ROTATED_INPUT = "7\n4 5 6 7 0 1 2\n0"


def _search_rotated(stdin: str) -> str:
    """One pass over every index: the answer cannot hide from a linear scan."""
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    target = values[1 + n]
    for index, value in enumerate(nums):
        if value == target:
            return str(index)
    return "-1"


SEARCH_ROTATED_SORTED_ARRAY: dict[str, Any] = {
    "slug": "search-in-rotated-sorted-array",
    "title": "Search in a Rotated Sorted Array",
    "summary": "Halve a sorted array that has been rotated, and still find the target.",
    "difficulty": "Medium",
    "topics": ["Binary Search", "Arrays", "Divide and Conquer"],
    "description": (
        "An ascending array of distinct integers has been rotated at an unknown "
        "pivot: `[0, 5, 6, 7, 8, 9]` might become `[7, 8, 9, 0, 5, 6]`. Search "
        "the rotated array for `target` and return its 0-based index, or `-1`.\n\n"
        "You may not scan the array. The whole point is that one comparison still "
        "rules out half of the candidates, exactly as in an unrotated search."
    ),
    "input_format": (
        "Line 1: `n`, the number of values.\n"
        "Line 2: `n` distinct integers, the rotated form of an ascending array.\n"
        "Line 3: `target`."
    ),
    "output_format": "Print the 0-based index of target, or `-1` when it is absent.",
    "constraints": (
        "1 <= n <= 2 * 10^4, the values are distinct, and an ascending rotation of "
        "them was rotated by some amount including zero."
    ),
    "examples": [
        {
            "input": ROTATED_INPUT,
            "output": _search_rotated(ROTATED_INPUT),
            "explanation": "The 0 sits at index 4.",
        },
        {
            "input": "5\n3 4 5 1 2\n3",
            "output": _search_rotated("5\n3 4 5 1 2\n3"),
            "explanation": "The rotation starts at index 3, so the first half is out of order and the second half is sorted.",
        },
    ],
    "hints": [
        "A linear scan always works, which is exactly the problem: it is O(n) and the question asks for better. What does one comparison still tell you about an array that is out of order in exactly one place?",
        "At any midpoint, one of the two halves is still sorted. Comparing `nums[low]` with `nums[mid]` tells you which one: if `nums[low] <= nums[mid]` the left half is ordered, because a rotation can only make one side wrap.",
        "Once you know which half is sorted, that half gives you a normal binary-search step: `nums[low] <= target < nums[mid]` means the target is inside it, otherwise it is in the other half.",
        "When the *right* half is the sorted one, the test is `nums[mid] < target <= nums[high]`. The direction of the inequalities flips with the half, and getting that backwards is the usual mistake here.",
        "Use distinct values. With duplicates, a half can look unsorted even when it is not, and the midpoint test stops deciding anything. Duplicates are the reason this problem states them away.",
    ],
    "explanation": (
        "A rotation splits the array into two ascending runs. Whichever side the "
        "midpoint falls on, one of the two halves spanning `low..mid` or "
        "`mid..high` lies entirely inside a single run and is therefore sorted, "
        "and comparing `nums[low]` with `nums[mid]` identifies which half that is.\n\n"
        "With the sorted half in hand, one comparison eliminates it or the other: "
        "if the target falls inside the sorted half's value range it is in that "
        "half, otherwise it is not, and either way half the candidates is gone. "
        "That is why the loop still halves its range every iteration and finishes "
        "in O(log n) comparisons.\n\n"
        "The distinctness requirement is what makes the test sound. If "
        "`nums[low] == nums[mid]`, a sorted half and an unsorted half look "
        "identical, and no amount of further comparison rules anything out -- "
        "which is why the duplicate version of this problem genuinely degrades to "
        "a linear scan.\n\n"
        "The invariant is the same one an ordinary binary search keeps: every "
        "remaining candidate lies in `low..high`, and the loop exits exactly when "
        "that range is empty, which means the target was not present."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(log n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def search(nums, target):
                \"\"\"Return the index of target in a rotated sorted array, or -1.\"\"\"
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(search(data[1 : 1 + n], data[1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function search(nums, target) {
              // Return the index of target in a rotated sorted array, or -1.
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              console.log(search(nums, target));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int search(int[] nums, int target) {
                    // Return the index of target in a rotated sorted array, or -1.
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    int target = in.nextInt();
                    System.out.println(search(nums, target));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def search(nums, target):
                low, high = 0, len(nums) - 1
                while low <= high:
                    middle = low + (high - low) // 2
                    if nums[middle] == target:
                        return middle
                    if nums[low] <= nums[middle]:
                        if nums[low] <= target < nums[middle]:
                            high = middle - 1
                        else:
                            low = middle + 1
                    else:
                        if nums[middle] < target <= nums[high]:
                            low = middle + 1
                        else:
                            high = middle - 1
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(search(data[1 : 1 + n], data[1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function search(nums, target) {
              let low = 0;
              let high = nums.length - 1;
              while (low <= high) {
                const middle = low + Math.floor((high - low) / 2);
                if (nums[middle] === target) {
                  return middle;
                }
                if (nums[low] <= nums[middle]) {
                  if (nums[low] <= target && target < nums[middle]) {
                    high = middle - 1;
                  } else {
                    low = middle + 1;
                  }
                } else if (nums[middle] < target && target <= nums[high]) {
                  low = middle + 1;
                } else {
                  high = middle - 1;
                }
              }
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              console.log(search(nums, target));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int search(int[] nums, int target) {
                    int low = 0;
                    int high = nums.length - 1;
                    while (low <= high) {
                        int middle = low + (high - low) / 2;
                        if (nums[middle] == target) {
                            return middle;
                        }
                        if (nums[low] <= nums[middle]) {
                            if (nums[low] <= target && target < nums[middle]) {
                                high = middle - 1;
                            } else {
                                low = middle + 1;
                            }
                        } else if (nums[middle] < target && target <= nums[high]) {
                            low = middle + 1;
                        } else {
                            high = middle - 1;
                        }
                    }
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    int target = in.nextInt();
                    System.out.println(search(nums, target));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_search_rotated, ROTATED_INPUT),
        judged_case(_search_rotated, "5\n1 2 3 4 5\n1"),
        judged_case(_search_rotated, "1\n3\n3"),
        judged_case(_search_rotated, "5\n4 5 6 7 0\n9"),
        judged_case(_search_rotated, "6\n3 4 5 1 2 6\n6", is_hidden=True),
        judged_case(_search_rotated, "1\n0\n0", is_hidden=True),
        judged_case(_search_rotated, "9\n9 10 11 12 0 1 2 3 4\n11", is_hidden=True),
        judged_case(_search_rotated, "4\n2 3 4 1\n1", is_hidden=True),
        judged_case(_search_rotated, "2\n2 1\n2", is_hidden=True),
        judged_case(_search_rotated, "8\n11 13 15 17 19 21 0 2\n17", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# First and last position
# --------------------------------------------------------------------------- #

FIRST_LAST_INPUT = "8\n1 2 2 2 3 3 5 5\n2"


def _first_and_last(stdin: str) -> str:
    """A single pass that remembers the first match and the most recent one."""
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    target = values[1 + n]
    first = -1
    last = -1
    for index, value in enumerate(nums):
        if value == target:
            if first == -1:
                first = index
            last = index
    return f"{first} {last}" if first != -1 else "-1 -1"


FIND_FIRST_AND_LAST_POSITION: dict[str, Any] = {
    "slug": "find-first-and-last-position",
    "title": "Find First and Last Position of a Value",
    "summary": "Find the bounds of a value's run in a sorted array with two binary searches.",
    "difficulty": "Medium",
    "topics": ["Binary Search", "Arrays"],
    "description": (
        "You are given a non-decreasing array of integers and a `target`. Find "
        "the index of the first occurrence and the index of the last occurrence "
        "of `target`, and print them in that order, space-separated.\n\n"
        "If `target` is absent, print `-1 -1`. Stopping at the first match is not "
        "enough, and neither is scanning: both halves of the answer have to come "
        "from the sorted order."
    ),
    "input_format": (
        "Line 1: `n`, the number of values.\n"
        "Line 2: `n` integers in non-decreasing order.\n"
        "Line 3: `target`."
    ),
    "output_format": "Print the first index and the last index of target, or `-1 -1` when it is absent.",
    "constraints": "0 <= n <= 10^5, -10^5 <= nums[i], target <= 10^5, and nums is non-decreasing.",
    "examples": [
        {
            "input": FIRST_LAST_INPUT,
            "output": _first_and_last(FIRST_LAST_INPUT),
            "explanation": "The 2s occupy indexes 1, 2 and 3.",
        },
        {
            "input": "4\n1 1 2 2\n2",
            "output": _first_and_last("4\n1 1 2 2\n2"),
            "explanation": "The run of 2s starts at index 2 and ends at index 3.",
        },
    ],
    "hints": [
        "Two searches are the obvious structure, and the question is what each one asks. 'Where is the value' is the wrong question for a run of equal values, because a run has many equal answers.",
        "Reframe both halves as boundary questions: where is the first index whose value is at least the target, and where is the first index whose value is greater than the target? Those are the lower bound and the upper bound.",
        "A lower-bound search is a binary search that never stops at a match. When `nums[middle] < target` the answer is to the right; otherwise it is at `middle` or to the left, so `high = middle`, not `middle - 1`.",
        "The answer is only a real position if the lower bound's value actually equals the target. With an empty range the search returns `n`, which is a legal index-shaped answer meaning 'past the end', and comparing it first is what stops you reporting `n` as a position.",
        "Notice that the lower bound already tells you where the run ends. The upper bound is the lower bound of `target + 1`, so the two searches share the same shape and differ only in the comparison.",
    ],
    "explanation": (
        "A sorted array with duplicates turns 'find the value' into 'find the "
        "boundary of the value's run', and boundaries are what binary search is "
        "genuinely good at.\n\n"
        "The lower bound is the first index whose value is at least `target`. The "
        "usual binary search is adjusted by one character: on `nums[middle] >= "
        "target` the boundary could be at `middle` itself, so the range shrinks to "
        "`[low, middle]` rather than `[low, middle - 1]`. When the range empties, "
        "`low` is the lower bound -- and if `low == n`, or `nums[low] != target`, "
        "the value is not in the array at all.\n\n"
        "The upper bound is the same search with the comparison the other way "
        "round: the first index whose value is greater than `target`. It is also "
        "the lower bound of `target + 1`, so it is the same ten lines with a "
        "different inequality, and the last occurrence is simply one less than "
        "it.\n\n"
        "Two searches is O(log n), which is worth two functions of clarity: it "
        "reads as two independent questions rather than one search with two "
        "results, and each half is easy to get right on its own."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(log n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def first_and_last(nums, target):
                \"\"\"Return (first index, last index) of target, or (-1, -1).\"\"\"
                return -1, -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                first, last = first_and_last(data[1 : 1 + n], data[1 + n])
                print(first, last)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function firstAndLast(nums, target) {
              // Return [firstIndex, lastIndex] of target, or [-1, -1].
              return [-1, -1];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              const [first, last] = firstAndLast(nums, target);
              console.log(first + " " + last);
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int[] firstAndLast(int[] nums, int target) {
                    // Return { firstIndex, lastIndex } of target, or { -1, -1 }.
                    return new int[] { -1, -1 };
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    int target = in.nextInt();
                    int[] answer = firstAndLast(nums, target);
                    System.out.println(answer[0] + " " + answer[1]);
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def lower_bound(nums, target):
                low, high = 0, len(nums)
                while low < high:
                    middle = low + (high - low) // 2
                    if nums[middle] < target:
                        low = middle + 1
                    else:
                        high = middle
                return low


            def first_and_last(nums, target):
                start = lower_bound(nums, target)
                if start == len(nums) or nums[start] != target:
                    return -1, -1
                return start, lower_bound(nums, target + 1) - 1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                first, last = first_and_last(data[1 : 1 + n], data[1 + n])
                print(first, last)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function lowerBound(nums, target) {
              let low = 0;
              let high = nums.length;
              while (low < high) {
                const middle = low + Math.floor((high - low) / 2);
                if (nums[middle] < target) {
                  low = middle + 1;
                } else {
                  high = middle;
                }
              }
              return low;
            }

            function firstAndLast(nums, target) {
              const start = lowerBound(nums, target);
              if (start === nums.length || nums[start] !== target) {
                return [-1, -1];
              }
              return [start, lowerBound(nums, target + 1) - 1];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              const [first, last] = firstAndLast(nums, target);
              console.log(first + " " + last);
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int lowerBound(int[] nums, int target) {
                    int low = 0;
                    int high = nums.length;
                    while (low < high) {
                        int middle = low + (high - low) / 2;
                        if (nums[middle] < target) {
                            low = middle + 1;
                        } else {
                            high = middle;
                        }
                    }
                    return low;
                }

                static int[] firstAndLast(int[] nums, int target) {
                    int start = lowerBound(nums, target);
                    if (start == nums.length || nums[start] != target) {
                        return new int[] { -1, -1 };
                    }
                    return new int[] { start, lowerBound(nums, target + 1) - 1 };
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    int target = in.nextInt();
                    int[] answer = firstAndLast(nums, target);
                    System.out.println(answer[0] + " " + answer[1]);
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_first_and_last, FIRST_LAST_INPUT),
        judged_case(_first_and_last, "5\n1 1 1 1 1\n1"),
        judged_case(_first_and_last, "4\n1 2 3 4\n9"),
        judged_case(_first_and_last, "3\n5 5 5\n5"),
        judged_case(_first_and_last, "0\n0", is_hidden=True),
        judged_case(_first_and_last, "6\n-5 -3 -3 0 0 4\n0", is_hidden=True),
        judged_case(_first_and_last, "7\n2 2 2 2 2 2 2\n2", is_hidden=True),
        judged_case(_first_and_last, "10\n1 1 2 2 3 3 4 4 5 5\n4", is_hidden=True),
        judged_case(_first_and_last, "1\n0\n0", is_hidden=True),
        judged_case(_first_and_last, "9\n-9 -9 -9 -9 -1 0 0 7 7\n-1", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Split array largest sum
# --------------------------------------------------------------------------- #

SPLIT_INPUT = "5\n7 2 5 10 8\n2"

#: The oracle solves this one with a table, which is O(k * n^2) and is why the
#: table-driven reading is kept as the oracle rather than the solution: it is the
#: slow, obviously-correct way to be sure the fast answer is the right one.
_SPLIT_BULK = [1 + ((index * 37) % 613) for index in range(180)]
SPLIT_BULK_INPUT = (
    f"{len(_SPLIT_BULK)}\n" + " ".join(str(value) for value in _SPLIT_BULK) + "\n23"
)


def _split_largest_sum(stdin: str) -> str:
    """Dynamic programming: the best largest sum over exactly k parts."""
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    k = values[1 + n]

    prefix = [0] * (n + 1)
    for index, value in enumerate(nums):
        prefix[index + 1] = prefix[index] + value

    # Any real answer is at most the total, so total + 1 stands in for infinity.
    unreachable = prefix[n] + 1
    # best[parts][length]: the smallest possible largest sum when the first
    # `length` values are cut into exactly `parts` non-empty pieces. Zero parts
    # can only cover zero values, so every other cell of row 0 is unreachable.
    best = [[unreachable] * (n + 1) for _ in range(k + 1)]
    best[0][0] = 0
    for parts in range(1, k + 1):
        for length in range(parts, n + 1):
            best_value = unreachable
            for start in range(parts - 1, length):
                piece = prefix[length] - prefix[start]
                candidate = max(best[parts - 1][start], piece)
                best_value = min(best_value, candidate)
            best[parts][length] = best_value
    return str(best[k][n])


SPLIT_ARRAY_LARGEST_SUM: dict[str, Any] = {
    "slug": "split-array-largest-sum",
    "title": "Split Array Largest Sum",
    "summary": "Minimise the largest part of an array cut into k pieces.",
    "difficulty": "Hard",
    "topics": ["Binary Search", "Greedy", "Arrays", "Divide and Conquer"],
    "description": (
        "You are given an array of positive integers `nums` and an integer `k`. "
        "Cut the array into `k` non-empty contiguous parts, and print the smallest "
        "possible value of the largest part's sum.\n\n"
        "Every part must be contiguous, so a cut is a choice of `k - 1` positions "
        "between values, and nothing may be skipped or reordered."
    ),
    "input_format": (
        "Line 1: `n`, the number of values.\n"
        "Line 2: `n` positive integers.\n"
        "Line 3: `k`, the number of parts."
    ),
    "output_format": "Print the smallest possible largest part sum.",
    "constraints": (
        "1 <= n <= 2 * 10^4, 1 <= nums[i] <= 10^4, and 1 <= k <= n. The answer is "
        "the sum of the array when `k == 1` and its largest value when `k == n`."
    ),
    "examples": [
        {
            "input": SPLIT_INPUT,
            "output": _split_largest_sum(SPLIT_INPUT),
            "explanation": "Cuts [7, 2, 5] and [10, 8] give parts of 14 and 18, and every other single cut leaves a part of 24 or more.",
        },
        {
            "input": "4\n1 2 3 4\n2",
            "output": _split_largest_sum("4\n1 2 3 4\n2"),
            "explanation": "Cuts [1, 2, 3] and [4] balance to 6 and 4, so 6 beats every other cut.",
        },
    ],
    "hints": [
        "Enumerating the cuts is combinatorial. Enumerating the *answers* is not: the largest sum is a number, the number of possible values is bounded by the total of the array, and the question 'could the answer be at most X' is monotone in X.",
        "That monotone question is what binary search consumes. Feasibility of a limit X is monotone -- if X works, anything larger works -- so binary search over [largest value, total] finds the smallest workable limit.",
        "Feasibility itself is greedy: walk the array, keep adding to the current part, and start a new part whenever adding the next value would exceed X. Filling each part as much as possible is what minimises the number of parts.",
        "Count the parts that greedy needs. Feasible means that count is at most k, not exactly k: with positive values, cutting an existing part in two never makes the largest sum larger, so at most k can always be promoted to exactly k.",
        "The bounds are not arbitrary. The answer cannot be below the largest single value, since some part contains that value, and cannot exceed the total, since one part holding everything always works.",
    ],
    "explanation": (
        "The search is over answers, not over positions. Define feasibility as "
        "'can the array be cut so that every part sums to at most X'. Feasibility "
        "is monotone in X -- a cut that respects X also respects any larger limit "
        "-- so the smallest feasible X can be found by binary search over the "
        "integers from the largest single value up to the total of the array.\n\n"
        "Greedy answers feasibility. Scan the values, keeping a running part sum, "
        "and start a new part the moment the next value would push the current "
        "part over X. This produces the fewest parts possible: making each part as "
        "long as it can be while respecting X cannot leave more parts than any "
        "other valid arrangement of the same values, because no valid first part "
        "ends later and the same argument then applies to what follows.\n\n"
        "The comparison is `parts <= k` rather than `parts == k`. Every value is "
        "positive, so splitting a part into two produces two smaller sums and "
        "cannot raise the largest; so whenever a cut with at most k parts exists, "
        "one with exactly k exists too, and the two formulations agree.\n\n"
        "Binary search is O(log(total)) iterations of an O(n) check, so the whole "
        "solution is O(n log(total)) time and O(1) extra space beyond the input."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n log(sum(nums)))",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def smallest_largest_sum(nums, k):
                \"\"\"Return the smallest possible largest sum over k contiguous parts.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(smallest_largest_sum(data[1 : 1 + n], data[1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function smallestLargestSum(nums, k) {
              // Return the smallest possible largest sum over k contiguous parts.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const k = Number(data[1 + n]);
              console.log(smallestLargestSum(nums, k));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static long smallestLargestSum(int[] nums, int k) {
                    // Return the smallest possible largest sum over k contiguous parts.
                    return 0L;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    int k = in.nextInt();
                    System.out.println(smallestLargestSum(nums, k));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def smallest_largest_sum(nums, k):
                def parts_needed(limit):
                    parts = 1
                    running = 0
                    for value in nums:
                        if running + value > limit:
                            parts += 1
                            running = value
                        else:
                            running += value
                    return parts

                low = max(nums)
                high = sum(nums)
                while low < high:
                    middle = (low + high) // 2
                    if parts_needed(middle) <= k:
                        high = middle
                    else:
                        low = middle + 1
                return low


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(smallest_largest_sum(data[1 : 1 + n], data[1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function smallestLargestSum(nums, k) {
              const partsNeeded = (limit) => {
                let parts = 1;
                let running = 0;
                for (const value of nums) {
                  if (running + value > limit) {
                    parts += 1;
                    running = value;
                  } else {
                    running += value;
                  }
                }
                return parts;
              };
              let low = Math.max(...nums);
              let high = nums.reduce((total, value) => total + value, 0);
              while (low < high) {
                const middle = low + Math.floor((high - low) / 2);
                if (partsNeeded(middle) <= k) {
                  high = middle;
                } else {
                  low = middle + 1;
                }
              }
              return low;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const k = Number(data[1 + n]);
              console.log(smallestLargestSum(nums, k));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int partsNeeded(int[] nums, int limit) {
                    int parts = 1;
                    int running = 0;
                    for (int value : nums) {
                        if (running + value > limit) {
                            parts += 1;
                            running = value;
                        } else {
                            running += value;
                        }
                    }
                    return parts;
                }

                static long smallestLargestSum(int[] nums, int k) {
                    long low = 0;
                    long high = 0;
                    for (int value : nums) {
                        if (value > low) {
                            low = value;
                        }
                        high += value;
                    }
                    while (low < high) {
                        long middle = low + (high - low) / 2;
                        if (partsNeeded(nums, (int) middle) <= k) {
                            high = middle;
                        } else {
                            low = middle + 1;
                        }
                    }
                    return low;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    int k = in.nextInt();
                    System.out.println(smallestLargestSum(nums, k));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_split_largest_sum, SPLIT_INPUT),
        judged_case(_split_largest_sum, "3\n1 2 3\n1"),
        judged_case(_split_largest_sum, "3\n1 2 3\n3"),
        judged_case(_split_largest_sum, "4\n9 9 9 9\n2"),
        judged_case(_split_largest_sum, "6\n1 2 3 4 5 6\n3", is_hidden=True),
        judged_case(_split_largest_sum, "8\n1 1 1 1 1 1 1 1\n4", is_hidden=True),
        judged_case(_split_largest_sum, "7\n100 200 300 400 500 600 700\n2", is_hidden=True),
        judged_case(_split_largest_sum, "1\n5\n1", is_hidden=True),
        judged_case(_split_largest_sum, "10\n5 4 3 2 1 9 8 7 6 10\n5", is_hidden=True),
        judged_case(_split_largest_sum, SPLIT_BULK_INPUT, is_hidden=True),
    ],
}


BINARY_SEARCH_PROBLEMS: tuple[dict[str, Any], ...] = (
    SEARCH_ROTATED_SORTED_ARRAY,
    FIND_FIRST_AND_LAST_POSITION,
    SPLIT_ARRAY_LARGEST_SUM,
)
