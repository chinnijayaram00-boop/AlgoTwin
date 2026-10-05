"""Sorting: the comparison-based orders, and the counting that hides inside them.

Four problems. Two of them are about producing a sorted order; the other two are
about the two things a sort is usually wanted *for*, and those are the harder
half. Counting inversions asks how far an array is from sorted without ever
sorting it, which is the question a naive sort throws away; merging k sorted
lists is what a merge step looks like when it is repeated k times.

The Dutch national flag problem is here because three-way partitioning is the
first partition a learner writes that is not "less than the pivot or not", and
pancake sort because a severely restricted operation set -- prefix reversals and
nothing else -- is enough to force every step of the classic argument to be made
explicit. Both are stated with a procedure precise enough to be graded rather
than described, because a sort problem whose answer depends on which of two
equally valid algorithms the learner picked cannot be judged fairly.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source


# --------------------------------------------------------------------------- #
# Count inversions
# --------------------------------------------------------------------------- #

INVERSION_INPUT = "5\n5 2 4 6 1"

#: A large, deterministic, unsorted input. The oracle counts it by brute force,
#: which is only affordable because this runs once at import time; the point of
#: including it is that the reference solution has to be the O(n log n) one, so a
#: hidden case would separate the two.
_INVERSION_BULK = [((index * 7919) % 2011) - 1005 for index in range(2400)]
_INVERSION_BULK_INPUT = f"{len(_INVERSION_BULK)}\n" + " ".join(
    str(value) for value in _INVERSION_BULK
)


def _count_inversions(stdin: str) -> str:
    """Brute force: look at every pair, in the order the statement defines."""
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    total = 0
    for left in range(n):
        for right in range(left + 1, n):
            if nums[left] > nums[right]:
                total += 1
    return str(total)


COUNT_INVERSIONS: dict[str, Any] = {
    "slug": "count-inversions",
    "title": "Count Inversions",
    "summary": "Measure how far an array is from sorted, without sorting it.",
    "difficulty": "Medium",
    "topics": ["Sorting", "Arrays", "Divide and Conquer", "Merge Sort"],
    "description": (
        "An inversion is a pair of positions `i < j` where `nums[i] > nums[j]`. "
        "In other words it is one element of the array that has to travel past a "
        "smaller element to its right.\n\n"
        "Count the inversions in `nums` and print that count. Do not sort the "
        "array to do it: the question is what a sort would have to fix, so the "
        "sort itself is the thing being measured."
    ),
    "input_format": "Line 1: `n`, the number of values.\nLine 2: `n` integers, in the order given.",
    "output_format": "Print the number of inversions in the array.",
    "constraints": (
        "0 <= n <= 2 * 10^5 and -10^9 <= nums[i] <= 10^9. Equal values are never "
        "an inversion. The count can reach `n * (n - 1) / 2`, which overflows a "
        "32-bit integer once `n` passes about 65 536, so a fixed-width language "
        "needs a 64-bit accumulator."
    ),
    "examples": [
        {
            "input": INVERSION_INPUT,
            "output": _count_inversions(INVERSION_INPUT),
            "explanation": "5 precedes 2, 4 and 1; 2 precedes 1; 4 precedes 1; 6 precedes 1. Six in all.",
        },
        {
            "input": "4\n4 3 2 1",
            "output": _count_inversions("4\n4 3 2 1"),
            "explanation": "Every pair is an inversion, which is `4 * 3 / 2 = 6`.",
        },
    ],
    "hints": [
        "Comparing every pair with every other pair is O(n^2) and the definition of correct. What makes it too slow is not the counting but the fact that it re-reads the same values thousands of times.",
        "Sort the array as the statement forbids, and then ask where each element ended up. An element that ends up at index `j` after `i` elements moved left across it accounts for exactly `i` inversions.",
        "That gives the classic pairing: count `position_in_sorted - position_in_original` for each value, using a stable sort so equal values are not counted against each other.",
        "Merge sort already does the accounting for free. While merging two sorted halves, whenever you take an element from the right half, every still-unmerged element in the left half is larger than it -- that is a whole batch of inversions decided by one comparison.",
        "Count that batch with `mid - left`, the number of elements still waiting in the left half. Equal values must be taken from the *left* half, otherwise a pair of equal values is counted as an inversion.",
    ],
    "explanation": (
        "Counting every pair is O(n^2), which is too slow for the largest inputs, "
        "so the answer has to come from a sort that keeps score as it works.\n\n"
        "Merge sort merges two already-sorted halves. At that moment the halves "
        "contain no inversions internally -- everything inside a sorted run is in "
        "order -- so every remaining inversion is a pair whose left element sits in "
        "the left half and whose right element sits in the right half. When the "
        "merge takes an element from the right half, every element still waiting "
        "in the left half is larger than it, so `mid - left` inversions are "
        "resolved in one step. When the merge takes from the left half, no new "
        "inversion is counted, because those pairs were already ordered.\n\n"
        "Equal values are taken from the left half first, so a pair of equal "
        "values is never counted -- the statement is strict, `nums[i] > nums[j]`, "
        "and a merge that preferred the right half on ties would over-count every "
        "run of duplicates.\n\n"
        "The recursion is O(n log n) with O(n) scratch space. The count itself is "
        "O(1) state, but a merge needs somewhere to put the result, which is where "
        "the auxiliary space goes."
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


            def count_inversions(nums):
                \"\"\"Return the number of pairs i < j with nums[i] > nums[j].\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(count_inversions(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countInversions(nums) {
              // Return the number of pairs i < j with nums[i] > nums[j].
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(countInversions(nums));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static long countInversions(int[] nums) {
                    // Return the number of pairs i < j with nums[i] > nums[j].
                    return 0L;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    System.out.println(countInversions(nums));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def sort_and_count(nums):
                if len(nums) < 2:
                    return nums, 0
                middle = len(nums) // 2
                left, left_count = sort_and_count(nums[:middle])
                right, right_count = sort_and_count(nums[middle:])
                merged = []
                inversions = left_count + right_count
                i = j = 0
                while i < len(left) and j < len(right):
                    if left[i] <= right[j]:
                        merged.append(left[i])
                        i += 1
                    else:
                        merged.append(right[j])
                        j += 1
                        inversions += len(left) - i
                merged.extend(left[i:])
                merged.extend(right[j:])
                return merged, inversions


            def count_inversions(nums):
                return sort_and_count(list(nums))[1]


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(count_inversions(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function sortAndCount(nums) {
              if (nums.length < 2) {
                return { sorted: nums, inversions: 0 };
              }
              const middle = Math.floor(nums.length / 2);
              const leftResult = sortAndCount(nums.slice(0, middle));
              const rightResult = sortAndCount(nums.slice(middle));
              let inversions = leftResult.inversions + rightResult.inversions;
              const merged = [];
              let i = 0;
              let j = 0;
              while (i < leftResult.sorted.length && j < rightResult.sorted.length) {
                if (leftResult.sorted[i] <= rightResult.sorted[j]) {
                  merged.push(leftResult.sorted[i]);
                  i += 1;
                } else {
                  merged.push(rightResult.sorted[j]);
                  j += 1;
                  inversions += leftResult.sorted.length - i;
                }
              }
              while (i < leftResult.sorted.length) {
                merged.push(leftResult.sorted[i]);
                i += 1;
              }
              while (j < rightResult.sorted.length) {
                merged.push(rightResult.sorted[j]);
                j += 1;
              }
              return { sorted: merged, inversions };
            }

            function countInversions(nums) {
              return sortAndCount(nums).inversions;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(countInversions(nums));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;
            import java.util.Arrays;

            public class Main {
                static long sortAndCount(int[] nums, int[] scratch, int low, int high) {
                    if (high - low < 2) {
                        return 0L;
                    }
                    int middle = low + (high - low) / 2;
                    long inversions = sortAndCount(nums, scratch, low, middle)
                            + sortAndCount(nums, scratch, middle, high);
                    int i = low;
                    int j = middle;
                    for (int k = low; k < high; k += 1) {
                        int take;
                        if (i < middle && (j >= high || nums[i] <= nums[j])) {
                            take = nums[i];
                            i += 1;
                        } else {
                            take = nums[j];
                            j += 1;
                            inversions += middle - i;
                        }
                        scratch[k] = take;
                    }
                    System.arraycopy(scratch, low, nums, low, high - low);
                    return inversions;
                }

                static long countInversions(int[] nums) {
                    if (nums.length < 2) {
                        return 0L;
                    }
                    return sortAndCount(nums, new int[nums.length], 0, nums.length);
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    System.out.println(countInversions(nums));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_count_inversions, INVERSION_INPUT),
        judged_case(_count_inversions, "1\n7"),
        judged_case(_count_inversions, "3\n1 2 3"),
        judged_case(_count_inversions, "4\n4 3 2 1"),
        judged_case(_count_inversions, "0", is_hidden=True),
        judged_case(_count_inversions, "5\n3 3 3 3 3", is_hidden=True),
        judged_case(_count_inversions, "7\n7 6 5 4 3 2 1", is_hidden=True),
        judged_case(_count_inversions, "6\n4 1 4 1 4 1", is_hidden=True),
        judged_case(_count_inversions, "8\n-9 -8 -7 -6 -5 -4 -3 -2", is_hidden=True),
        judged_case(_count_inversions, _INVERSION_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Dutch national flag
# --------------------------------------------------------------------------- #

FLAG_INPUT = "9\n2 0 1 2 0 1 0 2 1"


def _dutch_flag(stdin: str) -> str:
    """Three buckets and a count, which is the whole idea in a different shape."""
    values = int_tokens(stdin)
    n = values[0]
    counts = [0, 0, 0]
    for value in values[1 : 1 + n]:
        counts[value] += 1
    ordered = [0] * counts[0] + [1] * counts[1] + [2] * counts[2]
    return " ".join(str(value) for value in ordered)


DUTCH_NATIONAL_FLAG: dict[str, Any] = {
    "slug": "dutch-national-flag",
    "title": "Sort Zeroes, Ones and Twos",
    "summary": "Partition an array into three value ranges in a single pass.",
    "difficulty": "Medium",
    "topics": ["Sorting", "Arrays", "Two Pointers", "Partitioning"],
    "description": (
        "You are given an array `nums` whose values are only `0`, `1` and `2`. "
        "Rearrange it so that all the `0`s come first, then all the `1`s, then all "
        "the `2`s.\n\n"
        "Do it in one pass over the array and in place: no counting array, no "
        "`sort`, and no second output array. The sorted values are printed "
        "space-separated on one line, and the extra space your solution uses "
        "besides the input array must be O(1)."
    ),
    "input_format": "Line 1: `n`, the number of values.\nLine 2: `n` values, each `0`, `1` or `2`.",
    "output_format": "Print the rearranged values in ascending order, separated by single spaces.",
    "constraints": "0 <= n <= 3 * 10^5 and every value is `0`, `1` or `2`.",
    "examples": [
        {
            "input": FLAG_INPUT,
            "output": _dutch_flag(FLAG_INPUT),
            "explanation": "Three 0s, three 1s and three 2s, so the answer keeps every value and only changes their order.",
        },
        {
            "input": "5\n2 0 2 1 1",
            "output": _dutch_flag("5\n2 0 2 1 1"),
            "explanation": "One 0, two 1s and two 2s.",
        },
    ],
    "hints": [
        "Counting the three values first and then printing them works, but it uses a second array of size n. The interesting question is how to do it where the array already is.",
        "Keep four positions: the start of the array, the start of the 1s, the start of the 2s, and the end of the array. Everything before the first pointer is 0, between the first two is 1, between the last two is 2, and after the fourth is unknown.",
        "Look at the unknown value at the fourth position. A `0` belongs at the front and a `2` belongs at the back, so swap it in and move the corresponding pointer. A `1` is already home, so just move the fourth pointer past it.",
        "After swapping in a value from the back, do not advance the fourth pointer: the value you swapped with has just arrived in the unknown region and still has to be looked at. Advancing anyway is the classic bug here.",
        "The loop condition is `while current <= high`, and `current` is the only pointer that moves by one. When the pointers meet, every value is in place, which you can see from the invariant rather than by checking the array.",
    ],
    "explanation": (
        "This is a three-way partition, and it is the first partition a learner "
        "writes that is not two-way. A two-way partition has one boundary; this "
        "one has two, so the invariant is stated over three regions instead of "
        "two.\n\n"
        "Maintain `low` (the next slot a 0 should go into), `mid` (the next slot "
        "of the unprocessed region), `high` (the last slot of the unprocessed "
        "region), and the cursor `current`. The regions are `[0, low)` holding 0, "
        "`[low, current)` holding 1, `[current, high]` unprocessed, and `(high, "
        "n)` holding 2.\n\n"
        "At each step, look only at `nums[current]`. If it is a 1 it is already "
        "in the right region, so `current` advances and nothing else changes. If it "
        "is a 0, swap it with `nums[low]`, which is a 1 or a 2 sitting in the 0 "
        "region, and advance both `low` and `current`. If it is a 2, swap it with "
        "`nums[high]` and advance `high` but *not* `current`, because the value "
        "that arrived at `current` has not been classified yet.\n\n"
        "Each swap moves one value permanently into its final region, so the "
        "unprocessed region shrinks by one every iteration: one pass, O(n) time, "
        "and O(1) extra space."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def rearrange(nums):
                \"\"\"Sort 0s, 1s and 2s in place and return the same list.\"\"\"
                return nums


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(" ".join(str(value) for value in rearrange(data[1 : 1 + n])))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function rearrange(nums) {
              // Sort 0s, 1s and 2s in place and return the same array.
              return nums;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(rearrange(nums).join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static void rearrange(int[] nums) {
                    // Sort 0s, 1s and 2s in place.
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    rearrange(nums);
                    StringBuilder out = new StringBuilder();
                    for (int i = 0; i < n; i += 1) {
                        if (i > 0) {
                            out.append(' ');
                        }
                        out.append(nums[i]);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def rearrange(nums):
                low = 0
                current = 0
                high = len(nums) - 1
                while current <= high:
                    value = nums[current]
                    if value == 0:
                        nums[low], nums[current] = nums[current], nums[low]
                        low += 1
                        current += 1
                    elif value == 1:
                        current += 1
                    else:
                        nums[current], nums[high] = nums[high], nums[current]
                        high -= 1
                return nums


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(" ".join(str(value) for value in rearrange(data[1 : 1 + n])))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function rearrange(nums) {
              let low = 0;
              let current = 0;
              let high = nums.length - 1;
              while (current <= high) {
                const value = nums[current];
                if (value === 0) {
                  const swap = nums[low];
                  nums[low] = nums[current];
                  nums[current] = swap;
                  low += 1;
                  current += 1;
                } else if (value === 1) {
                  current += 1;
                } else {
                  const swap = nums[high];
                  nums[high] = nums[current];
                  nums[current] = swap;
                  high -= 1;
                }
              }
              return nums;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(rearrange(nums).join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static void rearrange(int[] nums) {
                    int low = 0;
                    int current = 0;
                    int high = nums.length - 1;
                    while (current <= high) {
                        int value = nums[current];
                        if (value == 0) {
                            int swap = nums[low];
                            nums[low] = nums[current];
                            nums[current] = swap;
                            low += 1;
                            current += 1;
                        } else if (value == 1) {
                            current += 1;
                        } else {
                            int swap = nums[high];
                            nums[high] = nums[current];
                            nums[current] = swap;
                            high -= 1;
                        }
                    }
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    rearrange(nums);
                    StringBuilder out = new StringBuilder();
                    for (int i = 0; i < n; i += 1) {
                        if (i > 0) {
                            out.append(' ');
                        }
                        out.append(nums[i]);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_dutch_flag, FLAG_INPUT),
        judged_case(_dutch_flag, "1\n0"),
        judged_case(_dutch_flag, "3\n2 2 2"),
        judged_case(_dutch_flag, "6\n1 0 1 0 1 0"),
        judged_case(_dutch_flag, "0", is_hidden=True),
        judged_case(_dutch_flag, "7\n2 1 2 1 2 1 0", is_hidden=True),
        judged_case(_dutch_flag, "10\n1 1 1 1 1 1 1 1 1 1", is_hidden=True),
        judged_case(
            _dutch_flag,
            "300\n" + " ".join(str((index * 7) % 3) for index in range(300)),
            is_hidden=True,
        ),
    ],
}


# --------------------------------------------------------------------------- #
# Merge K sorted lists
# --------------------------------------------------------------------------- #

MERGE_K_INPUT = "3\n2 2 2\n1 4 5 6 1 9"

_MERGE_K_BULK_SIZES = [600, 600, 600, 600, 600]
_MERGE_K_BULK_START = [index * 13 - 400 for index in range(5)]
_MERGE_K_BULK = " ".join(
    str(_MERGE_K_BULK_START[which] + 3 * offset)
    for which, size in enumerate(_MERGE_K_BULK_SIZES)
    for offset in range(size)
)
MERGE_K_BULK_INPUT = f"5\n{' '.join(str(size) for size in _MERGE_K_BULK_SIZES)}\n{_MERGE_K_BULK}"


def _merge_k(stdin: str) -> str:
    """Concatenate and sort. The heap is the interesting half of the problem."""
    values = int_tokens(stdin)
    k = values[0]
    sizes = values[1 : 1 + k]
    flat = values[1 + k :]
    merged: list[int] = []
    start = 0
    for size in sizes:
        merged.extend(flat[start : start + size])
        start += size
    return " ".join(str(value) for value in sorted(merged))


MERGE_K_SORTED_LISTS: dict[str, Any] = {
    "slug": "merge-k-sorted-lists",
    "title": "Merge K Sorted Lists",
    "summary": "Merge k sorted lists without materialising k-1 intermediate merges.",
    "difficulty": "Hard",
    "topics": ["Sorting", "Heaps", "Merging", "Arrays"],
    "description": (
        "You are given `k` lists, each of them sorted in non-decreasing order, and "
        "their values concatenated in that order together with the length of each "
        "list.\n\n"
        "Merge them into one sorted list and print every value, space-separated "
        "on a single line. The values keep their identity: merging must not drop "
        "or duplicate anything, so the answer has exactly as many values as the "
        "input did."
    ),
    "input_format": (
        "Line 1: `k`, the number of lists.\n"
        "Line 2: `k` integers, the length of each list in the same order. They sum "
        "to the number of values on the next line.\n"
        "Line 3: every value of every list, concatenated in list order."
    ),
    "output_format": "Print all merged values in non-decreasing order, separated by single spaces.",
    "constraints": (
        "1 <= k <= 10^4, each list is non-empty, and the lists hold at most 10^5 "
        "values in total. Values are in -10^9..10^9 and may repeat across lists."
    ),
    "examples": [
        {
            "input": MERGE_K_INPUT,
            "output": _merge_k(MERGE_K_INPUT),
            "explanation": "Lists [1, 4], [5, 6] and [1, 9] merge into 1 1 4 5 6 9.",
        },
        {
            "input": "2\n2 2\n-5 9 0 0",
            "output": _merge_k("2\n2 2\n-5 9 0 0"),
            "explanation": "Lists [-5, 9] and [0, 0] overlap at nothing and both 0s survive, so the answer holds four values for four inputs.",
        },
    ],
    "hints": [
        "Concatenating everything and sorting once is the shortest program here and it is also O(m log m) for m values. Ask instead how many times each value is *compared* -- that is what the merge should be measured on.",
        "Merging the lists one at a time is the obvious fix, but the first list gets compared to itself again on every merge, so a single long list is re-read k times. What has to be avoided is revisiting a value that is already known to be larger than everything still waiting.",
        "The unsorted part of the answer is always a suffix: at any moment every value already emitted is smaller than or equal to every value still un-emitted. So the next value must be the smallest head among the k lists that still have one.",
        "Keep the k heads in a min-heap keyed by value, together with which list and which position the head came from. Emit the smallest head, then push that list's next value into the heap. That is a complete algorithm on its own.",
        "Two details decide whether it is right: the heap comparison must break ties on the head value alone, because equal values from different lists may come out in any order and the output is still identical; and a list that runs out must simply stop contributing heads.",
    ],
    "explanation": (
        "A merge of two sorted runs is linear in their combined length. Doing it "
        "`k - 1` times over `k` runs is not: run 1 is merged into run 2, then that "
        "result is merged into run 3, then into run 4, and every element of run 1 "
        "is compared again on each of those merges. A k-way merge has to avoid "
        "that.\n\n"
        "The invariant that makes it possible is that the output so far is always "
        "a prefix of the final answer: everything already emitted is no larger "
        "than anything still waiting. So the next value to emit is not merely *a* "
        "candidate, it is exactly the smallest of the k current heads, because no "
        "value behind a head can be smaller than that head.\n\n"
        "Put every non-empty run's head into a min-heap keyed by value. Emit the "
        "smallest, replace it with the next value from the same run, and repeat "
        "until the heap is empty. Each value is pushed and popped once, so the "
        "time is O(m log k) for m values across k runs -- and for k = 1 that "
        "degenerates to O(m), which is the right answer.\n\n"
        "The heap holds at most k entries, so the extra space is O(k), "
        "independent of how many values there are. Ties are broken arbitrarily by "
        "the heap's own ordering and do not affect the answer, since equal values "
        "are interchangeable in a non-decreasing output."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(m log k)",
    "expected_space_complexity": "O(k)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def merge_k(lists):
                \"\"\"Merge already-sorted lists into one sorted list.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                sizes = data[1 : 1 + k]
                flat = data[1 + k :]
                lists = []
                start = 0
                for size in sizes:
                    lists.append(flat[start : start + size])
                    start += size
                print(" ".join(str(value) for value in merge_k(lists)))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function mergeK(lists) {
              // Merge already-sorted lists into one sorted list.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              const sizes = data.slice(1, 1 + k).map(Number);
              const flat = data.slice(1 + k).map(Number);
              const lists = [];
              let start = 0;
              for (const size of sizes) {
                lists.push(flat.slice(start, start + size));
                start += size;
              }
              console.log(mergeK(lists).join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;
            import java.util.ArrayList;
            import java.util.List;
            import java.util.PriorityQueue;

            public class Main {
                static List<Integer> mergeK(List<List<Integer>> lists) {
                    // Merge already-sorted lists into one sorted list.
                    return new ArrayList<>();
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int k = in.nextInt();
                    int[] sizes = new int[k];
                    for (int i = 0; i < k; i += 1) {
                        sizes[i] = in.nextInt();
                    }
                    List<List<Integer>> lists = new ArrayList<>();
                    for (int i = 0; i < k; i += 1) {
                        List<Integer> run = new ArrayList<>(sizes[i]);
                        for (int j = 0; j < sizes[i]; j += 1) {
                            run.add(in.nextInt());
                        }
                        lists.add(run);
                    }
                    List<Integer> merged = mergeK(lists);
                    StringBuilder out = new StringBuilder();
                    for (int i = 0; i < merged.size(); i += 1) {
                        if (i > 0) {
                            out.append(' ');
                        }
                        out.append(merged.get(i));
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys
            import heapq


            def merge_k(lists):
                heap = []
                for run_index, run in enumerate(lists):
                    if run:
                        heap.append((run[0], run_index, 0))
                heapq.heapify(heap)
                merged = []
                while heap:
                    value, run_index, offset = heapq.heappop(heap)
                    merged.append(value)
                    following = offset + 1
                    if following < len(lists[run_index]):
                        heapq.heappush(heap, (lists[run_index][following], run_index, following))
                return merged


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                sizes = data[1 : 1 + k]
                flat = data[1 + k :]
                lists = []
                start = 0
                for size in sizes:
                    lists.append(flat[start : start + size])
                    start += size
                print(" ".join(str(value) for value in merge_k(lists)))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function before(left, right) {
              if (left.value !== right.value) return left.value < right.value;
              return left.run < right.run;
            }

            function heapPush(heap, item) {
              heap.push(item);
              let index = heap.length - 1;
              while (index > 0) {
                const parent = Math.floor((index - 1) / 2);
                if (!before(heap[index], heap[parent])) break;
                const swap = heap[parent];
                heap[parent] = heap[index];
                heap[index] = swap;
                index = parent;
              }
            }

            function heapPop(heap) {
              const top = heap[0];
              const last = heap.pop();
              if (heap.length > 0) {
                heap[0] = last;
                let index = 0;
                for (;;) {
                  const left = index * 2 + 1;
                  const right = left + 1;
                  let smallest = index;
                  if (left < heap.length && before(heap[left], heap[smallest])) {
                    smallest = left;
                  }
                  if (right < heap.length && before(heap[right], heap[smallest])) {
                    smallest = right;
                  }
                  if (smallest === index) break;
                  const swap = heap[index];
                  heap[index] = heap[smallest];
                  heap[smallest] = swap;
                  index = smallest;
                }
              }
              return top;
            }

            function mergeK(lists) {
              const heads = lists.map(() => 0);
              const heap = [];
              for (let run = 0; run < lists.length; run += 1) {
                if (lists[run].length > 0) {
                  heapPush(heap, { value: lists[run][0], run });
                }
              }
              const merged = [];
              while (heap.length > 0) {
                const head = heapPop(heap);
                merged.push(head.value);
                const following = heads[head.run] + 1;
                heads[head.run] = following;
                if (following < lists[head.run].length) {
                  heapPush(heap, { value: lists[head.run][following], run: head.run });
                }
              }
              return merged;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              const sizes = data.slice(1, 1 + k).map(Number);
              const flat = data.slice(1 + k).map(Number);
              const lists = [];
              let start = 0;
              for (const size of sizes) {
                lists.push(flat.slice(start, start + size));
                start += size;
              }
              console.log(mergeK(lists).join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;
            import java.util.ArrayList;
            import java.util.Comparator;
            import java.util.List;
            import java.util.PriorityQueue;

            public class Main {
                record Head(int value, int run, int offset) {}

                static List<Integer> mergeK(List<List<Integer>> lists) {
                    PriorityQueue<Head> heap = new PriorityQueue<>(
                            Comparator.comparingInt(Head::value));
                    for (int run = 0; run < lists.size(); run += 1) {
                        if (!lists.get(run).isEmpty()) {
                            heap.add(new Head(lists.get(run).get(0), run, 0));
                        }
                    }
                    List<Integer> merged = new ArrayList<>();
                    while (!heap.isEmpty()) {
                        Head head = heap.poll();
                        merged.add(head.value());
                        int next = head.offset() + 1;
                        if (next < lists.get(head.run()).size()) {
                            heap.add(new Head(lists.get(head.run()).get(next), head.run(), next));
                        }
                    }
                    return merged;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int k = in.nextInt();
                    int[] sizes = new int[k];
                    for (int i = 0; i < k; i += 1) {
                        sizes[i] = in.nextInt();
                    }
                    List<List<Integer>> lists = new ArrayList<>();
                    for (int i = 0; i < k; i += 1) {
                        List<Integer> run = new ArrayList<>(sizes[i]);
                        for (int j = 0; j < sizes[i]; j += 1) {
                            run.add(in.nextInt());
                        }
                        lists.add(run);
                    }
                    List<Integer> merged = mergeK(lists);
                    StringBuilder out = new StringBuilder();
                    for (int i = 0; i < merged.size(); i += 1) {
                        if (i > 0) {
                            out.append(' ');
                        }
                        out.append(merged.get(i));
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_merge_k, MERGE_K_INPUT),
        judged_case(_merge_k, "1\n4\n-3 -1 5 7"),
        judged_case(_merge_k, "2\n1 3\n9 0 0 0"),
        judged_case(_merge_k, "3\n1 1 1\n2 2 2"),
        judged_case(_merge_k, "2\n2 1\n5 5 5", is_hidden=True),
        judged_case(_merge_k, "4\n3 1 2 1\n-4 0 9 -4 -4 -1 0", is_hidden=True),
        judged_case(_merge_k, "3\n3 3 3\n1 1 1 2 2 2 3 3 3", is_hidden=True),
        judged_case(_merge_k, MERGE_K_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Pancake sort
# --------------------------------------------------------------------------- #

PANCAKE_INPUT = "4\n2 1 4 3"


def _pancake_sort(stdin: str) -> str:
    """Follow the statement's procedure exactly; the flips are the answer."""
    values = int_tokens(stdin)
    n = values[0]
    pancakes = values[1 : 1 + n]

    def flip(length: int) -> None:
        pancakes[:length] = pancakes[:length][::-1]

    flips: list[int] = []
    for fixed in range(n - 1, -1, -1):
        largest = 0
        for index in range(1, fixed + 1):
            if pancakes[index] > pancakes[largest]:
                largest = index
        flip(largest + 1)
        flips.append(largest + 1)
        flip(fixed + 1)
        flips.append(fixed + 1)

    ordered = " ".join(str(value) for value in sorted(pancakes))
    return f"{ordered}\n{' '.join(str(length) for length in flips)}"


PANCAKE_SORT: dict[str, Any] = {
    "slug": "pancake-sort",
    "title": "Pancake Sort",
    "summary": "Sort an array using prefix reversals as the only allowed move.",
    "difficulty": "Hard",
    "topics": ["Sorting", "Arrays", "Greedy", "Simulation"],
    "description": (
        "A stack of pancakes is given as its values from the top of the stack "
        "downwards, and every value is distinct. The only operation allowed is a "
        "**flip**: take the top `k` pancakes and reverse their order.\n\n"
        "Produce the sorted stack in non-decreasing order from the top down, "
        "together with the flip sequence that got you there. Use exactly this "
        "procedure, because the sequence of flips is part of the answer:\n\n"
        "1. For `fixed` from `n - 1` down to `0`:\n"
        "2. Let `j` be the 0-based position, counting from the top, of the "
        "largest value among the first `fixed + 1` pancakes.\n"
        "3. Flip the first `j + 1` pancakes and record `j + 1`.\n"
        "4. Flip the first `fixed + 1` pancakes and record `fixed + 1`.\n\n"
        "Both flips of every round are performed and recorded even when they "
        "reverse a single pancake or reverse a prefix that is already in order."
    ),
    "input_format": (
        "Line 1: `n`, the number of pancakes.\n"
        "Line 2: `n` distinct integers, from the top of the stack downwards."
    ),
    "output_format": (
        "Line 1: the `n` values in non-decreasing order from the top down, "
        "separated by single spaces.\n"
        "Line 2: the recorded flip lengths in order, separated by single spaces. "
        "For an empty stack, print two empty lines."
    ),
    "constraints": (
        "0 <= n <= 200, values are distinct and in 1..10^6. The procedure "
        "performs exactly `2n` flips, so line 2 holds `2n` numbers."
    ),
    "examples": [
        {
            "input": PANCAKE_INPUT,
            "output": _pancake_sort(PANCAKE_INPUT),
            "explanation": "Flips 3 4 place the 4 at the bottom, then 1 3 and 2 2 place the 3, then 1 1 finishes.",
        },
        {
            "input": "2\n2 1",
            "output": _pancake_sort("2\n2 1"),
            "explanation": "The 2 is already on the bottom, so the two recorded flips do nothing visible and still count.",
        },
    ],
    "hints": [
        "Ask what a flip can achieve for you. It reverses a prefix, so it can bring any chosen pancake to the very top in a single move.",
        "Once the largest remaining pancake is on top, one more flip of the right length puts it in the correct final place for good. That is the whole argument: a flip gives you access to a value, and a second flip consumes it.",
        "The place it belongs is the end of the unsorted prefix, so the second flip length is `fixed + 1` where `fixed` is the last index you still have to fix. Working from `n - 1` downwards means each round settles one more position permanently.",
        "Finding the largest value in the unsorted prefix is a scan, so the whole procedure is O(n^2) and never needs an array of indexes, a heap, or any structure beyond the array itself.",
        "Both flips are unconditional. If the largest pancake is already at the top, you still flip 1; if it is already at its final place, you still flip `fixed + 1`. Skipping them because they look unnecessary is what makes an otherwise-correct answer differ from the expected one.",
    ],
    "explanation": (
        "The array is sorted in ascending order, so position `n - 1` must hold "
        "the largest value. A flip of the first `j + 1` elements moves whatever "
        "sits at position `j` to the top, so any single pancake of the unsorted "
        "prefix can be brought to the top in one move -- the two-flip trick that "
        "distinguishes pancake sort from a general permutation sort.\n\n"
        "Round `fixed` therefore does this: find the largest of the first "
        "`fixed + 1` pancakes at position `j`, flip `j + 1` to bring it to the "
        "top, then flip `fixed + 1` to move it from the top to position `fixed`. "
        "After that second flip the value at `fixed` is the largest of the "
        "unsorted prefix and therefore correct for that position, and the prefix "
        "is never touched again -- which is why `fixed` may then decrease by one.\n\n"
        "Each round performs two flips and settles one position, so there are "
        "exactly `2n` flips for `n` pancakes, and the procedure finishes with the "
        "array sorted. Finding the maximum of the prefix is a scan, so the time "
        "is O(n^2) with O(1) extra space; the reversal itself is in place, and "
        "the flip list is the only thing that grows, with `2n` entries.\n\n"
        "Pancake sort is famously not the fewest flips possible -- that problem "
        "is open -- but the bound here is two per pancake, which is all the "
        "argument above claims."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n^2)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def pancake_sort(nums):
                \"\"\"Return (sorted values, flip lengths) for the stated procedure.\"\"\"
                return list(nums), []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                ordered, flips = pancake_sort(data[1 : 1 + n])
                print(" ".join(str(value) for value in ordered))
                print(" ".join(str(length) for length in flips))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function pancakeSort(nums) {
              // Return { sorted, flips } for the procedure in the statement.
              return { sorted: nums.slice(), flips: [] };
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const result = pancakeSort(data.slice(1, 1 + n).map(Number));
              console.log(result.sorted.join(" "));
              console.log(result.flips.join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;
            import java.util.ArrayList;
            import java.util.List;

            public class Main {
                static int[] flip(int[] nums, int length) {
                    // Reverse the first `length` values in place and return them.
                    return nums;
                }

                static String pancakeSort(int[] nums) {
                    // Two lines: the sorted values, then the recorded flip lengths.
                    return "";
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    System.out.println(pancakeSort(nums));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def pancake_sort(nums):
                pancakes = list(nums)
                n = len(pancakes)
                flips = []

                def flip(length):
                    pancakes[:length] = pancakes[:length][::-1]
                    flips.append(length)

                for fixed in range(n - 1, -1, -1):
                    largest = 0
                    for index in range(1, fixed + 1):
                        if pancakes[index] > pancakes[largest]:
                            largest = index
                    flip(largest + 1)
                    flip(fixed + 1)
                return pancakes, flips


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                ordered, flips = pancake_sort(data[1 : 1 + n])
                print(" ".join(str(value) for value in ordered))
                print(" ".join(str(length) for length in flips))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function pancakeSort(nums) {
              const pancakes = nums.slice();
              const flips = [];
              const flip = (length) => {
                const head = pancakes.slice(0, length).reverse();
                for (let i = 0; i < length; i += 1) {
                  pancakes[i] = head[i];
                }
                flips.push(length);
              };
              for (let fixed = pancakes.length - 1; fixed >= 0; fixed -= 1) {
                let largest = 0;
                for (let index = 1; index <= fixed; index += 1) {
                  if (pancakes[index] > pancakes[largest]) {
                    largest = index;
                  }
                }
                flip(largest + 1);
                flip(fixed + 1);
              }
              return { sorted: pancakes, flips };
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const result = pancakeSort(data.slice(1, 1 + n).map(Number));
              console.log(result.sorted.join(" "));
              console.log(result.flips.join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;
            import java.util.Arrays;

            public class Main {
                static void flip(int[] nums, int length) {
                    for (int i = 0, j = length - 1; i < j; i += 1, j -= 1) {
                        int swap = nums[i];
                        nums[i] = nums[j];
                        nums[j] = swap;
                    }
                }

                static String pancakeSort(int[] nums) {
                    int n = nums.length;
                    StringBuilder flips = new StringBuilder();
                    for (int fixed = n - 1; fixed >= 0; fixed -= 1) {
                        int largest = 0;
                        for (int index = 1; index <= fixed; index += 1) {
                            if (nums[index] > nums[largest]) {
                                largest = index;
                            }
                        }
                        flip(nums, largest + 1);
                        if (flips.length() > 0) {
                            flips.append(' ');
                        }
                        flips.append(largest + 1);
                        flip(nums, fixed + 1);
                        if (flips.length() > 0) {
                            flips.append(' ');
                        }
                        flips.append(fixed + 1);
                    }
                    StringBuilder ordered = new StringBuilder();
                    for (int i = 0; i < n; i += 1) {
                        if (i > 0) {
                            ordered.append(' ');
                        }
                        ordered.append(nums[i]);
                    }
                    return ordered + "\\n" + flips;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    System.out.println(pancakeSort(nums));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_pancake_sort, PANCAKE_INPUT),
        judged_case(_pancake_sort, "1\n5"),
        judged_case(_pancake_sort, "3\n3 2 1"),
        judged_case(_pancake_sort, "5\n1 2 3 4 5"),
        judged_case(_pancake_sort, "0", is_hidden=True),
        judged_case(_pancake_sort, "4\n9 4 7 1", is_hidden=True),
        judged_case(_pancake_sort, "6\n6 5 4 3 2 1", is_hidden=True),
        judged_case(_pancake_sort, "7\n100 3 42 7 99 1 55", is_hidden=True),
        judged_case(
            _pancake_sort,
            "12\n" + " ".join(str(value) for value in [17, 3, 90, 8, 1, 66, 24, 5, 71, 2, 39, 12]),
            is_hidden=True,
        ),
    ],
}


SORTING_PROBLEMS: tuple[dict[str, Any], ...] = (
    COUNT_INVERSIONS,
    DUTCH_NATIONAL_FLAG,
    MERGE_K_SORTED_LISTS,
    PANCAKE_SORT,
)
