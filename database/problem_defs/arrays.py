"""Arrays, sorting, and the two scan-and-hash shapes that dominate interviews.

Five problems, chosen because together they cover the array techniques a learner
meets first: hash maps, interval merging, two pointers, selecting the k-th
largest, and a bit of arithmetic that is really an array of bits in disguise.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source

# --------------------------------------------------------------------------- #
# Two Sum
# --------------------------------------------------------------------------- #


def _two_sum(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    target = values[1 + n]
    seen: dict[int, int] = {}
    for index, value in enumerate(nums):
        complement = target - value
        if complement in seen:
            return f"{seen[complement]} {index}"
        seen.setdefault(value, index)
    raise ValueError("the two-sum inputs in the catalog always contain an answer")


TWO_SUM_INPUT = "4\n2 7 11 15\n9"

TWO_SUM: dict[str, Any] = {
    "slug": "two-sum",
    "title": "Two Sum",
    "summary": "Return the indices of the two values that add up to a target.",
    "difficulty": "Easy",
    "topics": ["Arrays", "Hash Maps", "Two Pointers"],
    "description": (
        "Given an array of integers `nums` and an integer `target`, return the "
        "indices of the two numbers that add up to `target`.\n\n"
        "Exactly one answer exists, and the same element may not be used twice. "
        "Return the smaller index first."
    ),
    "input_format": (
        "Line 1: `n`, how many values follow.\n"
        "Line 2: `n` integers.\n"
        "Line 3: `target`, the sum the two values must reach."
    ),
    "output_format": "Print the two 0-based indices separated by a single space, smaller first.",
    "constraints": (
        "1 <= n <= 10^4, -10^9 <= nums[i] <= 10^9, -2 * 10^9 <= target <= 2 * 10^9. "
        "Exactly one valid answer exists and it does not reuse an element."
    ),
    "examples": [
        {
            "input": TWO_SUM_INPUT,
            "output": _two_sum(TWO_SUM_INPUT),
            "explanation": "2 + 7 = 9, and the values sit at indices 0 and 1.",
        }
    ],
    "hints": [
        "A brute force tries every pair, which is O(n^2). Ask what you could learn from a value you have already looked at.",
        "As you scan left to right, for each value `v` you only need to know whether `target - v` has already appeared. A hash map turns that question into a lookup.",
        "Keep a map from value to the index where it was first seen. For each value, check the map for `target - value` before inserting the current value, so an element is never paired with itself.",
        "Check the map before you insert the current value, otherwise a value equal to half of `target` would be matched with itself.",
        "Return the pair of indices, smaller first. Inserting only when a value is new (`setdefault`) keeps the earliest index for duplicates, which is what the statement asks for.",
    ],
    "explanation": (
        "Walk the array once, keeping a hash map from each value you have seen to "
        "the index it was seen at. For the value at index `i`, the only partner "
        "that could work is `target - nums[i]`; if that is already in the map, the "
        "answer is the stored index and `i`. Otherwise store `nums[i]` and move on.\n\n"
        "The lookup happens before the insert, so the element at `i` can never be "
        "its own partner, and the stored index is always smaller than `i`, so the "
        "pair is returned in order. The array is scanned once and the map holds at "
        "most `n` entries, so the time and space are both O(n)."
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


            def two_sum(nums, target):
                \"\"\"Return the two indices whose values add up to target.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                nums = data[1 : 1 + n]
                target = data[1 + n]
                print(*two_sum(nums, target))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function twoSum(nums, target) {
              // Return the two indices whose values add up to target.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              console.log(twoSum(nums, target).join(" "));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def two_sum(nums, target):
                seen = {}
                for index, value in enumerate(nums):
                    complement = target - value
                    if complement in seen:
                        return [seen[complement], index]
                    seen.setdefault(value, index)
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                nums = data[1 : 1 + n]
                target = data[1 + n]
                print(*two_sum(nums, target))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function twoSum(nums, target) {
              const seen = new Map();
              for (let index = 0; index < nums.length; index += 1) {
                const complement = target - nums[index];
                if (seen.has(complement)) {
                  return [seen.get(complement), index];
                }
                if (!seen.has(nums[index])) {
                  seen.set(nums[index], index);
                }
              }
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              console.log(twoSum(nums, target).join(" "));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_two_sum, TWO_SUM_INPUT),
        judged_case(_two_sum, "2\n3 5\n8"),
        judged_case(_two_sum, "3\n3 3 3\n6"),
        judged_case(_two_sum, "5\n-1 -2 -3 -4 -5\n-8", is_hidden=True),
        judged_case(_two_sum, "2\n0 0\n0"),
        judged_case(_two_sum, "4\n5 75 25 35\n100", is_hidden=True),
        judged_case(_two_sum, "6\n1 2 3 4 5 9\n11", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Merge Intervals
# --------------------------------------------------------------------------- #


def _merge_intervals(stdin: str) -> str:
    values = int_tokens(stdin)
    k = values[0]
    pairs = sorted((values[1 + 2 * i], values[2 + 2 * i]) for i in range(k))
    merged: list[list[int]] = []
    for start, end in pairs:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return "\n".join(f"{start} {end}" for start, end in merged)


MERGE_INTERVALS_INPUT = "3\n1 3\n2 6\n8 10"

MERGE_INTERVALS: dict[str, Any] = {
    "slug": "merge-intervals",
    "title": "Merge Intervals",
    "summary": "Merge overlapping intervals into the smallest possible set.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Sorting", "Intervals"],
    "description": (
        "Given a collection of intervals where `intervals[i] = [start, end]`, "
        "merge all overlapping intervals and return the result as a set of "
        "non-overlapping intervals covering every input interval.\n\n"
        "Two intervals touch when `next.start <= current.end`, so `[1, 3]` and "
        "`[3, 5]` do overlap."
    ),
    "input_format": (
        "Line 1: `k`, how many intervals follow.\n"
        "Lines 2 to k+1: `start end` for one interval."
    ),
    "output_format": (
        "Print one merged interval per line as `start end`, ordered by start, "
        "with no blank lines between them."
    ),
    "constraints": (
        "0 <= k <= 1000, 0 <= start <= end <= 10^4. The input need not be sorted."
    ),
    "examples": [
        {
            "input": MERGE_INTERVALS_INPUT,
            "output": _merge_intervals(MERGE_INTERVALS_INPUT),
            "explanation": "[1, 3] and [2, 6] overlap, so they become [1, 6]. [8, 10] stands alone.",
        }
    ],
    "hints": [
        "If the intervals arrive in any order, deciding whether a new interval overlaps the previous one is a coin flip. Sort first and the question becomes easy.",
        "Sort the intervals by their start. Then scan left to right, keeping only the interval you last emitted. Each new interval either overlaps it or starts a fresh one.",
        "Keep `merged` as a list of finished intervals. For each `[start, end]`, if `merged` is not empty and `start <= merged[-1][1]`, extend the last interval to `max(merged[-1][1], end)`; otherwise append `[start, end]`.",
        "Use `<=` rather than `<` for the overlap test. With `<=`, touching intervals such as `[1, 3]` and `[3, 5]` merge, which the statement requires.",
        "Sorting by start is enough; the list is then ordered, so the last element of `merged` is always the only interval a new one can overlap. Compare against `merged[-1][1]`, not the whole list.",
    ],
    "explanation": (
        "Sort the intervals by start time. Now every interval that could overlap "
        "the one you are looking at comes before or after it, and the only "
        "overlap candidate for the current interval is the last one you emitted.\n\n"
        "Walk the sorted list, keeping `merged`. If the current start is at or "
        "before the end of the last emitted interval, the two overlap, so extend "
        "that interval to the larger of the two ends. Otherwise the current "
        "interval cannot overlap anything earlier, so append it. Because the "
        "input is sorted by start, `merged` is already in ascending order and no "
        "second sort is needed.\n\n"
        "Sorting dominates: O(n log n) time. The scan itself is O(n) and needs "
        "O(n) space in the worst case, when nothing overlaps."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n log n)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def merge(intervals):
                \"\"\"Return the merged, non-overlapping intervals.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                intervals = [[data[1 + 2 * i], data[2 + 2 * i]] for i in range(k)]
                for start, end in merge(intervals):
                    print(start, end)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function merge(intervals) {
              // Return the merged, non-overlapping intervals as [start, end] pairs.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              const intervals = [];
              for (let i = 0; i < k; i += 1) {
                intervals.push([Number(data[1 + 2 * i]), Number(data[2 + 2 * i])]);
              }
              for (const [start, end] of merge(intervals)) {
                console.log(`${start} ${end}`);
              }
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def merge(intervals):
                ordered = sorted(intervals, key=lambda interval: interval[0])
                merged = []
                for start, end in ordered:
                    if merged and start <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], end)
                    else:
                        merged.append([start, end])
                return merged


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                intervals = [[data[1 + 2 * i], data[2 + 2 * i]] for i in range(k)]
                for start, end in merge(intervals):
                    print(start, end)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function merge(intervals) {
              const ordered = intervals
                .map((interval) => [interval[0], interval[1]])
                .sort((a, b) => a[0] - b[0]);
              const merged = [];
              for (const [start, end] of ordered) {
                if (merged.length > 0 && start <= merged[merged.length - 1][1]) {
                  merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], end);
                } else {
                  merged.push([start, end]);
                }
              }
              return merged;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              const intervals = [];
              for (let i = 0; i < k; i += 1) {
                intervals.push([Number(data[1 + 2 * i]), Number(data[2 + 2 * i])]);
              }
              for (const [start, end] of merge(intervals)) {
                console.log(`${start} ${end}`);
              }
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_merge_intervals, MERGE_INTERVALS_INPUT),
        judged_case(_merge_intervals, "4\n1 4\n2 3\n3 4\n5 6"),
        judged_case(_merge_intervals, "0"),
        judged_case(_merge_intervals, "1\n1 1"),
        judged_case(_merge_intervals, "3\n1 4\n2 3\n8 10", is_hidden=True),
        judged_case(_merge_intervals, "5\n1 4\n0 4\n4 5\n2 6\n9 10", is_hidden=True),
        judged_case(_merge_intervals, "2\n5 6\n1 2", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Container With Most Water
# --------------------------------------------------------------------------- #


def _container_with_most_water(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    heights = values[1 : 1 + n]
    best = 0
    left, right = 0, n - 1
    while left < right:
        best = max(best, min(heights[left], heights[right]) * (right - left))
        if heights[left] < heights[right]:
            left += 1
        else:
            right -= 1
    return str(best)


CONTAINER_INPUT = "9\n1 8 6 2 5 4 8 3 7"

CONTAINER_WITH_MOST_WATER: dict[str, Any] = {
    "slug": "container-with-most-water",
    "title": "Container With Most Water",
    "summary": "Find the two lines that hold the most water between them.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Two Pointers"],
    "description": (
        "There are `n` vertical lines on the x-axis, the `i`-th at `x = i` with "
        "height `heights[i]`. Two lines and the x-axis form a container, and it "
        "holds `min(left, right) * (right - left)` units of water.\n\n"
        "Return the largest amount of water any container can hold."
    ),
    "input_format": (
        "Line 1: `n`, how many lines there are.\nLine 2: `n` heights, left to right."
    ),
    "output_format": "Print the largest area as a single integer.",
    "constraints": "0 <= n <= 10^5, 0 <= heights[i] <= 10^4.",
    "examples": [
        {
            "input": CONTAINER_INPUT,
            "output": _container_with_most_water(CONTAINER_INPUT),
            "explanation": "Lines at indices 1 and 8 hold 7 * 8 = 56, and the maximum is 49 from indices 1 and 6.",
        }
    ],
    "hints": [
        "Trying every pair is O(n^2). Think about what the area of a pair depends on: the shorter of the two heights and the distance between them.",
        "Start at both ends, where the distance is largest, and move the shorter of the two lines inwards.",
        "Keep `left = 0` and `right = n - 1`. At each step, record `min(heights[left], heights[right]) * (right - left)`, then move whichever end is shorter.",
        "Move the *shorter* end. Moving the taller end inwards only reduces the width while the height cannot improve past the shorter line, so the area can only get worse.",
        "Loop while `left < right`, and stop as soon as they meet: a container needs two distinct lines. The area is evaluated before the move, so the widest candidate is never skipped.",
    ],
    "explanation": (
        "Start with one pointer at each end, which gives the widest container "
        "available. At every step compute the area and then move the pointer at "
        "the shorter line inwards.\n\n"
        "The move is the whole trick. If `heights[left]` is the shorter line, then "
        "any container that keeps `left` and uses a pointer further right is at "
        "most as tall as `heights[left]` and strictly narrower, so none of them "
        "can beat the one just measured. `left` is therefore safe to discard, and "
        "the same argument applies to `right` when it is the shorter. Each step "
        "shrinks the window, so the loop runs at most n times.\n\n"
        "Time is O(n) and the extra space is O(1): two pointers and a running "
        "maximum."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def max_area(heights):
                \"\"\"Return the largest area a container between two lines can hold.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(max_area(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function maxArea(heights) {
              // Return the largest area a container between two lines can hold.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const heights = data.slice(1, 1 + n).map(Number);
              console.log(maxArea(heights));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def max_area(heights):
                best = 0
                left, right = 0, len(heights) - 1
                while left < right:
                    best = max(best, min(heights[left], heights[right]) * (right - left))
                    if heights[left] < heights[right]:
                        left += 1
                    else:
                        right -= 1
                return best


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(max_area(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function maxArea(heights) {
              let best = 0;
              let left = 0;
              let right = heights.length - 1;
              while (left < right) {
                const area = Math.min(heights[left], heights[right]) * (right - left);
                if (area > best) {
                  best = area;
                }
                if (heights[left] < heights[right]) {
                  left += 1;
                } else {
                  right -= 1;
                }
              }
              return best;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const heights = data.slice(1, 1 + n).map(Number);
              console.log(maxArea(heights));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_container_with_most_water, CONTAINER_INPUT),
        judged_case(_container_with_most_water, "2\n1 1"),
        judged_case(_container_with_most_water, "1\n5"),
        judged_case(_container_with_most_water, "0"),
        judged_case(_container_with_most_water, "2\n1 8", is_hidden=True),
        judged_case(_container_with_most_water, "5\n1 2 4 3 5", is_hidden=True),
        judged_case(_container_with_most_water, "6\n4 3 2 1 4 9", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Kth Largest Element
# --------------------------------------------------------------------------- #


def _kth_largest(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    k = values[1 + n]
    ordered = sorted(nums, reverse=True)
    return str(ordered[k - 1])


KTH_LARGEST_INPUT = "6\n3 2 1 5 6 4\n2"

KTH_LARGEST: dict[str, Any] = {
    "slug": "kth-largest-element",
    "title": "Kth Largest Element",
    "summary": "Return the kth largest value in an unsorted array.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Sorting", "Heaps"],
    "description": (
        "Given an unsorted array `nums` and an integer `k`, return the kth largest "
        "element of the array, counting duplicates as separate values.\n\n"
        "`k` is 1-based, so `k = 1` asks for the largest value."
    ),
    "input_format": (
        "Line 1: `n`, how many values follow.\n"
        "Line 2: `n` integers.\n"
        "Line 3: `k`, 1-based rank from the largest."
    ),
    "output_format": "Print the kth largest value as a single integer.",
    "constraints": (
        "1 <= n <= 10^5, -10^4 <= nums[i] <= 10^4, 1 <= k <= n. Values may repeat."
    ),
    "examples": [
        {
            "input": KTH_LARGEST_INPUT,
            "output": _kth_largest(KTH_LARGEST_INPUT),
            "explanation": "Sorted descending the array is [6, 5, 4, 3, 2, 1], so the second largest is 5.",
        }
    ],
    "hints": [
        "Sorting the whole array is a valid answer and costs O(n log n). The statement gives no constraint that forbids it, so start there and see whether you can do better.",
        "You only need the value at one position, not the whole sorted array. Ask whether a full sort is doing work you do not need.",
        "Sort the array, or use a heap. A max-heap built from the array, polled once and then drained, has already paid for the top of the order.",
        "A simple heap-based answer: heapify a max-heap of all values, then pop `k` times. That is O(n + k log n) after the O(n) build, which beats a sort when `k` is small.",
        "Do not use a min-heap for this: the order you want is the largest first, so the default heap in every standard library is the wrong way round. In Python, `heapq` is a min-heap, so negate the values or use `heapq.nlargest`.",
    ],
    "explanation": (
        "The straightforward answer is to sort the array descending and read the "
        "value at index `k - 1`. That is O(n log n) time and, depending on the "
        "sort, O(n) space.\n\n"
        "A heap-based answer is better when `k` is small. Building a max-heap from "
        "the array costs O(n), because heapifying an existing collection is "
        "linear rather than n separate inserts. Removing the maximum `k` times "
        "costs O(k log n), so the total is O(n + k log n) -- the same answer, "
        "computed without sorting values you were never going to read.\n\n"
        "Either way, note that duplicates count separately, so the heap approach "
        "must not de-duplicate the input. This problem is a good place to see why "
        "a library's default heap direction matters: Python's `heapq` is a "
        "min-heap, so a max-heap is built by pushing the negated values."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n + k log n)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def kth_largest(nums, k):
                \"\"\"Return the kth largest value, counting duplicates separately.\"\"\"
                return None


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(kth_largest(data[1 : 1 + n], data[1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function kthLargest(nums, k) {
              // Return the kth largest value, counting duplicates separately.
              return null;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const k = Number(data[1 + n]);
              console.log(kthLargest(nums, k));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def kth_largest(nums, k):
                return sorted(nums, reverse=True)[k - 1]


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(kth_largest(data[1 : 1 + n], data[1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function kthLargest(nums, k) {
              return [...nums].sort((a, b) => b - a)[k - 1];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const k = Number(data[1 + n]);
              console.log(kthLargest(nums, k));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_kth_largest, KTH_LARGEST_INPUT),
        judged_case(_kth_largest, "1\n7\n1"),
        judged_case(_kth_largest, "5\n2 2 1 3 1\n4"),
        judged_case(_kth_largest, "4\n-1 -1 -1 -1\n2", is_hidden=True),
        judged_case(_kth_largest, "6\n1 2 3 4 5 6\n6", is_hidden=True),
        judged_case(_kth_largest, "7\n5 5 5 5 5 5 5\n3", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Single Number
# --------------------------------------------------------------------------- #


def _single_number(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    result = 0
    for value in nums:
        result ^= value
    return str(result)


SINGLE_NUMBER_INPUT = "5\n4 1 2 1 2"

SINGLE_NUMBER: dict[str, Any] = {
    "slug": "single-number",
    "title": "Single Number",
    "summary": "Find the one value that appears once while every other value appears twice.",
    "difficulty": "Easy",
    "topics": ["Arrays", "Bit Manipulation", "Hash Maps"],
    "description": (
        "Given an array of integers where exactly one element appears once and "
        "every other element appears exactly twice, return that single element.\n\n"
        "Your algorithm must run in linear time and use constant extra space."
    ),
    "input_format": "Line 1: `n`, how many values follow.\nLine 2: `n` integers.",
    "output_format": "Print the value that appears exactly once.",
    "constraints": (
        "1 <= n <= 3 * 10^4, and n is odd. Exactly one value appears once, all "
        "others appear exactly twice. Integer overflow does not occur in Python."
    ),
    "examples": [
        {
            "input": SINGLE_NUMBER_INPUT,
            "output": _single_number(SINGLE_NUMBER_INPUT),
            "explanation": "4 appears once while 1 and 2 each appear twice.",
        }
    ],
    "hints": [
        "A count map would find it, but the statement asks for constant extra space. A map holding every distinct value is not constant space.",
        "Every value that appears twice can be made to cancel itself out, if you can find an operation that does that to equal values.",
        "XOR is that operation: `a ^ a == 0`, and XOR is associative and commutative so the order does not matter.",
        "Fold XOR over the whole array. Every value that appears twice contributes `v ^ v`, which is 0, and the single value is left standing.",
        "Start the accumulator at 0, because `0 ^ v == v`. Note that XOR on negative numbers uses two's complement and still satisfies these identities, so the argument holds for negative input too.",
    ],
    "explanation": (
        "XOR every value in the array into a running accumulator that starts at "
        "zero.\n\n"
        "XOR has three properties that make this work: `a ^ a = 0`, `a ^ 0 = a`, "
        "and it is associative and commutative, so the pairs can cancel regardless "
        "of order. Every value that appears twice appears as `v ^ v`, which "
        "vanishes, and the only value left contributing is the one that appears "
        "once.\n\n"
        "The fold is a single pass with one integer of state, so the time is O(n) "
        "and the extra space is O(1), which is what the statement demands. This "
        "also works for negative numbers, because two's complement XOR satisfies "
        "the same identities."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def single_number(nums):
                \"\"\"Return the value that appears exactly once.\"\"\"
                return None


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(single_number(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function singleNumber(nums) {
              // Return the value that appears exactly once.
              return null;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(singleNumber(nums));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def single_number(nums):
                result = 0
                for value in nums:
                    result ^= value
                return result


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(single_number(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function singleNumber(nums) {
              let result = 0;
              for (const value of nums) {
                result ^= value;
              }
              return result;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(singleNumber(nums));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_single_number, SINGLE_NUMBER_INPUT),
        judged_case(_single_number, "1\n7"),
        judged_case(_single_number, "3\n-2 -3 -2"),
        judged_case(_single_number, "5\n0 0 0 0 -5", is_hidden=True),
        judged_case(_single_number, "7\n9 8 7 8 9 7 3", is_hidden=True),
        judged_case(_single_number, "3\n-1 -1 -4", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Group Anagrams
# --------------------------------------------------------------------------- #


def _group_anagrams(stdin: str) -> str:
    tokens = stdin.split()
    count = int(tokens[0])
    words = tokens[1 : 1 + count]
    groups: dict[str, list[str]] = {}
    for word in words:
        groups.setdefault("".join(sorted(word)), []).append(word)
    lines = sorted(" ".join(sorted(group)) for group in groups.values())
    return "\n".join(lines)


GROUP_ANAGRAMS_INPUT = "6\neat tea tan ate nat bat"


GROUP_ANAGRAMS: dict[str, Any] = {
    "slug": "group-anagrams",
    "title": "Group Anagrams",
    "summary": "Collect words that are rearrangements of one another into groups.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Hash Maps", "Strings", "Sorting"],
    "description": (
        "You are given `n` words made of lowercase letters. Two words belong in the "
        "same group when one is a rearrangement of the other, meaning they contain "
        "exactly the same letters with exactly the same counts.\n\n"
        "A group is printed as its words sorted alphabetically and separated by "
        "single spaces. The groups themselves are printed in sorted order, so the "
        "answer is unique and does not depend on the order the words arrived in."
    ),
    "input_format": (
        "Line 1: `n`, the number of words.\n"
        "Line 2: `n` lowercase words separated by spaces."
    ),
    "output_format": (
        "Print one line per group: the group's words sorted alphabetically, "
        "separated by single spaces. Print the lines themselves in sorted order."
    ),
    "constraints": (
        "1 <= n <= 10^4. Each word has length between 1 and 100 and contains only "
        "lowercase English letters (`a`-`z`). Words inside a group may repeat."
    ),
    "examples": [
        {
            "input": GROUP_ANAGRAMS_INPUT,
            "output": _group_anagrams(GROUP_ANAGRAMS_INPUT),
            "explanation": "`ate`, `eat` and `tea` share their letters, so they form one group; `nat` and `tan` form another; `bat` stands alone.",
        },
        {
            "input": "3\nabc cba bca",
            "output": _group_anagrams("3\nabc cba bca"),
            "explanation": "All three words are rearrangements of the same letters, so they print together, sorted as `abc bca cba`.",
        },
    ],
    "hints": [
        "Comparing every pair of words with a letter count is O(n^2) comparisons. The question to ask is what single value you could compute for a word that is the *same* for every rearrangement of it.",
        "A sort of the word's letters is such a value: `eat`, `ate` and `tea` all become `aet`. Two words are anagrams exactly when their sorted forms are equal.",
        "Use the sorted form as a hash-map key and store the original word in a list under that key. Every word lands in the bucket of the one group it belongs to.",
        "Sorting each group and then sorting the list of printed lines is what makes the output canonical. The judge compares exact text, so an arbitrary group or word order would make the same answer look different.",
        "The total work is the cost of sorting every word: with words of length `L`, that is O(n * L log L). The extra space is O(n * L) to hold the groups.",
    ],
    "explanation": (
        "The key observation is that a word and any rearrangement of it sort to the "
        "same string of letters. That sorted string is a canonical name for the "
        "group, and it is cheap to compute.\n\n"
        "Walk the words once. For each word, sort its letters and use the result as "
        "a map key, appending the word to the list stored there. Words with the same "
        "letters share a key and therefore a bucket, so each bucket is exactly one "
        "group. To make the printed answer unique, sort the words within each bucket "
        "and sort the resulting lines before printing.\n\n"
        "Each word is sorted once, which costs O(L log L) for a word of length `L`, "
        "for O(n * L log L) overall. The map holds every word once, so the space is "
        "O(n * L)."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n * L log L)",
    "expected_space_complexity": "O(n * L)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def group_anagrams(words):
                \"\"\"Return the words grouped by anagram.\"\"\"
                return []


            def main():
                tokens = sys.stdin.read().split()
                n = int(tokens[0])
                words = tokens[1 : 1 + n]
                groups = [sorted(group) for group in group_anagrams(words)]
                for line in sorted(" ".join(group) for group in groups):
                    print(line)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function groupAnagrams(words) {
              // Return the words grouped by anagram.
              return [];
            }

            function main() {
              const tokens = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(tokens[0]);
              const words = tokens.slice(1, 1 + n);
              const lines = groupAnagrams(words).map((group) =>
                group.slice().sort().join(" ")
              );
              lines.sort();
              console.log(lines.join("\\n"));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def group_anagrams(words):
                groups = {}
                for word in words:
                    groups.setdefault("".join(sorted(word)), []).append(word)
                return list(groups.values())


            def main():
                tokens = sys.stdin.read().split()
                n = int(tokens[0])
                words = tokens[1 : 1 + n]
                groups = [sorted(group) for group in group_anagrams(words)]
                for line in sorted(" ".join(group) for group in groups):
                    print(line)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function groupAnagrams(words) {
              const groups = new Map();
              for (const word of words) {
                const key = word.split("").sort().join("");
                if (!groups.has(key)) {
                  groups.set(key, []);
                }
                groups.get(key).push(word);
              }
              return Array.from(groups.values());
            }

            function main() {
              const tokens = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(tokens[0]);
              const words = tokens.slice(1, 1 + n);
              const lines = groupAnagrams(words).map((group) =>
                group.slice().sort().join(" ")
              );
              lines.sort();
              console.log(lines.join("\\n"));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_group_anagrams, GROUP_ANAGRAMS_INPUT),
        judged_case(_group_anagrams, "1\nhello"),
        judged_case(_group_anagrams, "3\nabc cba bca"),
        judged_case(_group_anagrams, "2\na a"),
        judged_case(_group_anagrams, "4\nab ba ab ba", is_hidden=True),
        judged_case(
            _group_anagrams,
            "5\nlisten silent enlist inlets google",
            is_hidden=True,
        ),
        judged_case(_group_anagrams, "3\nzzz zzz aaa", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# 3Sum
# --------------------------------------------------------------------------- #


def _three_sum(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    nums = sorted(values[1 : 1 + n])
    triples: list[str] = []
    for i in range(n):
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        if nums[i] > 0:
            break
        low, high = i + 1, n - 1
        target = -nums[i]
        while low < high:
            total = nums[low] + nums[high]
            if total < target:
                low += 1
            elif total > target:
                high -= 1
            else:
                triples.append(f"{nums[i]} {nums[low]} {nums[high]}")
                low += 1
                high -= 1
                while low < high and nums[low] == nums[low - 1]:
                    low += 1
                while low < high and nums[high] == nums[high + 1]:
                    high -= 1
    return "\n".join(triples)


THREE_SUM_INPUT = "6\n-1 0 1 2 -1 -4"


THREE_SUM: dict[str, Any] = {
    "slug": "three-sum",
    "title": "3Sum",
    "summary": "Find every distinct triple of values that adds up to zero.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Two Pointers", "Sorting"],
    "description": (
        "Given an array of `n` integers, find every distinct triple of values "
        "`(a, b, c)` such that `a + b + c = 0`. Each value comes from a different "
        "position in the array, and the same triple of values must not be printed "
        "twice, however many times the values occur.\n\n"
        "Print each triple on its own line with its three values in ascending order, "
        "and print the triples themselves in ascending order."
    ),
    "input_format": (
        "Line 1: `n`, how many integers follow.\n"
        "Line 2: `n` integers separated by spaces."
    ),
    "output_format": (
        "Print one line per distinct triple, the three values in ascending order "
        "separated by single spaces. Print nothing at all when no triple sums to zero."
    ),
    "constraints": (
        "0 <= n <= 3000, and -10^5 <= nums[i] <= 10^5. A triple uses three different "
        "positions; the same triple of values is printed only once even if the values "
        "repeat."
    ),
    "examples": [
        {
            "input": THREE_SUM_INPUT,
            "output": _three_sum(THREE_SUM_INPUT),
            "explanation": "The two distinct triples are -1 + -1 + 2 and -1 + 0 + 1. The repeated -1 at two positions is not printed a second time.",
        },
        {
            "input": "5\n-2 0 1 1 2",
            "output": _three_sum("5\n-2 0 1 1 2"),
            "explanation": "Using both 1s gives -2 + 1 + 1; the other triple is -2 + 0 + 2.",
        },
    ],
    "hints": [
        "The brute force tries every triple, which is O(n^3). Sorting the array first does not by itself fix that, but it makes a smaller search possible.",
        "Fix the first value `nums[i]` and now the problem is Two Sum: find two later values adding to `-nums[i]`. In a sorted array those two can be found by moving one pointer inward from each end.",
        "If the current pair's sum is too small, move the left pointer right; if it is too large, move the right pointer left; if it matches, record the triple and move both inward.",
        "Sorted order makes duplicates visible as neighbours. Skip an `nums[i]` equal to the previous one, and after recording a triple skip equal values on both pointers, so no triple is emitted twice.",
        "Because the array is sorted, a triple's first value is the smallest, so once `nums[i]` is positive the target `-nums[i]` is negative and can never be reached by two larger values. Breaking there is what keeps the search tight.",
    ],
    "explanation": (
        "Sort the array so that each triple is discovered in ascending order and "
        "duplicates sit next to each other. Then fix the smallest element at index "
        "`i` and look for two values later in the array that sum to `-nums[i]`.\n\n"
        "Those two are found with two pointers: `low` just after `i` and `high` at "
        "the end. In a sorted array, if the pair sum is below the target the only "
        "way to increase it is to advance `low`, and if it is above the target the "
        "only way to decrease it is to retreat `high`. When it matches, record the "
        "triple and step both pointers inward.\n\n"
        "Duplicates are removed by skipping equal neighbours at all three levels: "
        "the fixed element, and either pointer after a match. Skips on the pointers "
        "happen before the next comparison, so no triple is recorded twice. The sort "
        "costs O(n log n) and the outer loop with its inner pointer walk is O(n^2), "
        "which dominates; the extra space is O(1) beyond the sort itself."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n^2)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 3_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def three_sum(nums):
                \"\"\"Return the distinct triples that sum to zero.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                nums = data[1 : 1 + n]
                for triple in three_sum(nums):
                    print(*triple)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function threeSum(nums) {
              // Return the distinct triples that sum to zero.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              for (const triple of threeSum(nums)) {
                console.log(triple.join(" "));
              }
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def three_sum(nums):
                nums.sort()
                n = len(nums)
                result = []
                for i in range(n):
                    if i > 0 and nums[i] == nums[i - 1]:
                        continue
                    if nums[i] > 0:
                        break
                    low, high = i + 1, n - 1
                    while low < high:
                        total = nums[i] + nums[low] + nums[high]
                        if total < 0:
                            low += 1
                        elif total > 0:
                            high -= 1
                        else:
                            result.append([nums[i], nums[low], nums[high]])
                            low += 1
                            high -= 1
                            while low < high and nums[low] == nums[low - 1]:
                                low += 1
                            while low < high and nums[high] == nums[high + 1]:
                                high -= 1
                return result


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                nums = data[1 : 1 + n]
                for triple in three_sum(nums):
                    print(*triple)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function threeSum(nums) {
              nums.sort((a, b) => a - b);
              const n = nums.length;
              const result = [];
              for (let i = 0; i < n; i += 1) {
                if (i > 0 && nums[i] === nums[i - 1]) {
                  continue;
                }
                if (nums[i] > 0) {
                  break;
                }
                let low = i + 1;
                let high = n - 1;
                while (low < high) {
                  const total = nums[i] + nums[low] + nums[high];
                  if (total < 0) {
                    low += 1;
                  } else if (total > 0) {
                    high -= 1;
                  } else {
                    result.push([nums[i], nums[low], nums[high]]);
                    low += 1;
                    high -= 1;
                    while (low < high && nums[low] === nums[low - 1]) {
                      low += 1;
                    }
                    while (low < high && nums[high] === nums[high + 1]) {
                      high -= 1;
                    }
                  }
                }
              }
              return result;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              for (const triple of threeSum(nums)) {
                console.log(triple.join(" "));
              }
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_three_sum, THREE_SUM_INPUT),
        judged_case(_three_sum, "3\n0 0 0"),
        judged_case(_three_sum, "5\n-2 0 1 1 2"),
        judged_case(_three_sum, "3\n-1 0 1"),
        judged_case(_three_sum, "4\n1 2 3 4", is_hidden=True),
        judged_case(_three_sum, "2\n0 0", is_hidden=True),
        judged_case(_three_sum, "6\n-4 -2 -2 0 2 4", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Longest consecutive sequence
# --------------------------------------------------------------------------- #


def _longest_consecutive(stdin: str) -> str:
    """A set of the values, then a count upward from each run's start."""
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    present = set(nums)
    best = 0
    for value in present:
        if value - 1 in present:
            continue
        length = 1
        while value + length in present:
            length += 1
        if length > best:
            best = length
    return str(best)


LONGEST_CONSECUTIVE_INPUT = "6\n100 4 200 1 3 2"


LONGEST_CONSECUTIVE_SEQUENCE: dict[str, Any] = {
    "slug": "longest-consecutive-sequence",
    "title": "Longest Consecutive Sequence",
    "summary": "Find the longest run of consecutive integers, in any order.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Hash Maps"],
    "description": (
        "Given an unsorted array of integers `nums`, return the length of the "
        "longest run of consecutive values it contains.\n\n"
        "The values do not have to be adjacent in the array, only consecutive as "
        "numbers: `1, 2, 3, 4` is a run of length 4 wherever those values sit. "
        "The solution has to run in O(n) time, so sorting is not allowed."
    ),
    "input_format": "Line 1: `n`, the number of values.\nLine 2: `n` integers separated by spaces.",
    "output_format": "Print the length of the longest run of consecutive integers.",
    "constraints": (
        "0 <= n <= 10^5 and -10^9 <= nums[i] <= 10^9. Values may repeat; duplicates "
        "count once and an empty array has the answer 0."
    ),
    "examples": [
        {
            "input": LONGEST_CONSECUTIVE_INPUT,
            "output": _longest_consecutive(LONGEST_CONSECUTIVE_INPUT),
            "explanation": "`1 2 3 4` is the longest run, so the answer is 4.",
        },
        {
            "input": "10\n0 3 7 2 5 8 4 6 0 1",
            "output": _longest_consecutive("10\n0 3 7 2 5 8 4 6 0 1"),
            "explanation": "The values 0 through 8 are all present, so the run has length 9.",
        },
    ],
    "hints": [
        "Sorting gives the answer in O(n log n) by walking adjacent values. The problem asks for O(n), so the ordering has to come from something cheaper than a sort.",
        "A hash set answers 'is this value present?' in constant time. That is enough to walk a run upward one value at a time without ever sorting.",
        "The key is not to start counting from every value: that would be O(n^2) when the whole array is one long run. Start counting only from a value whose predecessor is absent, because such a value is the first of its run.",
        "For each run, count how many successors are present by checking `value + 1`, `value + 2`, and so on in the set. When you do this only from run starts, each value is visited at most twice across the whole scan.",
        "Put the values in a set first so duplicates collapse, then loop over the set. Every value is the start of at most one run, so the total work is linear.",
    ],
    "explanation": (
        "Two facts make an O(n) solution possible. First, membership in a set is "
        "constant time, so 'is the next value present?' can be asked cheaply. "
        "Second, a run has exactly one start: the value whose predecessor is not "
        "present. Counting from every value would re-walk long runs many times, but "
        "counting only from starts visits each run once.\n\n"
        "Build a set of the values. For each value `v` in the set, check whether "
        "`v - 1` is present; if it is, `v` is in the middle of a run and some other "
        "value already represents that run, so skip it. Otherwise `v` begins a run, "
        "so extend upward with `v + 1`, `v + 2`, and so on while those values are "
        "present, and keep the longest length found.\n\n"
        "Each value is looked at once as a candidate start and at most once as a "
        "successor of some run, so the time is O(n). The set uses O(n) space, which "
        "is also what removes the need to sort."
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


            def longest_consecutive(nums):
                \"\"\"Return the length of the longest run of consecutive values.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(longest_consecutive(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function longestConsecutive(nums) {
              // Return the length of the longest run of consecutive values.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(longestConsecutive(nums));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def longest_consecutive(nums):
                present = set(nums)
                best = 0
                for value in present:
                    if value - 1 in present:
                        continue
                    length = 1
                    while value + length in present:
                        length += 1
                    best = max(best, length)
                return best


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(longest_consecutive(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function longestConsecutive(nums) {
              const present = new Set(nums);
              let best = 0;
              for (const value of present) {
                if (present.has(value - 1)) {
                  continue;
                }
                let length = 1;
                while (present.has(value + length)) {
                  length += 1;
                }
                best = Math.max(best, length);
              }
              return best;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(longestConsecutive(nums));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_longest_consecutive, LONGEST_CONSECUTIVE_INPUT),
        judged_case(_longest_consecutive, "10\n0 3 7 2 5 8 4 6 0 1"),
        judged_case(_longest_consecutive, "1\n5"),
        judged_case(_longest_consecutive, "4\n1 2 0 1"),
        judged_case(_longest_consecutive, "0\n", is_hidden=True),
        judged_case(_longest_consecutive, "5\n10 5 12 3 55", is_hidden=True),
        judged_case(_longest_consecutive, "7\n-3 -2 -1 0 1 2 3", is_hidden=True),
        judged_case(_longest_consecutive, "6\n1 1 1 1 1 1", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Trapping rain water
# --------------------------------------------------------------------------- #


def _trap(stdin: str) -> str:
    """For each column, water is bounded by the tallest wall on either side."""
    values = int_tokens(stdin)
    n = values[0]
    heights = values[1 : 1 + n]
    if n == 0:
        return "0"
    left = [0] * n
    right = [0] * n
    left[0] = heights[0]
    for index in range(1, n):
        left[index] = max(left[index - 1], heights[index])
    right[n - 1] = heights[n - 1]
    for index in range(n - 2, -1, -1):
        right[index] = max(right[index + 1], heights[index])
    total = 0
    for index in range(n):
        total += min(left[index], right[index]) - heights[index]
    return str(total)


TRAP_INPUT = "12\n0 1 0 2 1 0 1 3 2 1 2 1"


TRAPPING_RAIN_WATER: dict[str, Any] = {
    "slug": "trapping-rain-water",
    "title": "Trapping Rain Water",
    "summary": "Measure the water held between walls of varying height.",
    "difficulty": "Hard",
    "topics": ["Arrays", "Two Pointers"],
    "description": (
        "You are given `n` non-negative integers `height`, where each value is the "
        "height of a wall one unit wide, standing in a row.\n\n"
        "After it rains, water is trapped in the dips between taller walls. Water "
        "above a wall at index `i` reaches only as high as the shorter of the two "
        "tallest walls to its left and right, and the amount held there is that "
        "level minus the wall's own height. Return the total units of water trapped."
    ),
    "input_format": "Line 1: `n`, the number of walls.\nLine 2: `n` non-negative integers, the wall heights.",
    "output_format": "Print the total number of units of water trapped.",
    "constraints": (
        "0 <= n <= 2 * 10^4 and 0 <= height[i] <= 10^5. An empty row of walls traps "
        "nothing, and water resting on top of a wall is not counted."
    ),
    "examples": [
        {
            "input": TRAP_INPUT,
            "output": _trap(TRAP_INPUT),
            "explanation": "Six units are held in the hollows, mostly between the heights 3 and 2 and the dips before them.",
        },
        {
            "input": "6\n4 2 0 3 2 5",
            "output": _trap("6\n4 2 0 3 2 5"),
            "explanation": "Two units sit above the 0 and three above the second 2, for a total of 9.",
        },
    ],
    "hints": [
        "Water at a position is not about the wall there; it is about the walls on both sides. Write down the height water reaches at index `i` in terms of the tallest wall to the left and the tallest wall to the right.",
        "Water at index `i` reaches `min(tallest-left, tallest-right)`, because it spills over the lower of the two sides. If that is below `height[i]`, no water rests there.",
        "Precompute the running maximum height from the left in one pass and from the right in another. Then one more pass adds `min(left[i], right[i]) - height[i]` wherever that is positive.",
        "This prefix/suffix form is O(n) time and O(n) space. It is the version to write first because it is hard to get wrong, and it makes the two-pointer version's correctness easy to argue.",
        "The two-pointer version removes the arrays: advance whichever side currently has the shorter wall, because that side's bound is already decided by the other side's maximum. It trades O(n) space for O(1) and is the reason this is classed as a two-pointer problem.",
    ],
    "explanation": (
        "For a wall at index `i`, the water above it is bounded by the shorter of "
        "the two tallest walls to its left and right. If `left[i]` is the maximum "
        "height in `height[0..i]` and `right[i]` is the maximum in `height[i..n-1]`, "
        "the water resting on top of this wall is `min(left[i], right[i]) - "
        "height[i]`, and never negative.\n\n"
        "Both maxima can be built in a single pass each: `left` by sweeping forward "
        "and keeping the running maximum, `right` by sweeping backward the same way. "
        "A final pass sums the positive differences to get the total. That is O(n) "
        "time and O(n) space.\n\n"
        "The same sum can be computed with two pointers and no arrays. Keep `low` at "
        "the left end and `high` at the right, with `left_max` and `right_max` as "
        "the tallest walls seen from each pointer. When `left_max <= right_max` the "
        "true bound for the `low` wall is `left_max`, because the wall on the other "
        "side is at least that tall, so that column can be settled and `low` "
        "advanced. Otherwise the `high` column is settled and `high` retreated. Each "
        "pointer moves inward at most n times, so the time is still O(n) and the "
        "space drops to O(1)."
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


            def trap(height):
                \"\"\"Return the total units of water trapped between the walls.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(trap(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function trap(height) {
              // Return the total units of water trapped between the walls.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const height = data.slice(1, 1 + n).map(Number);
              console.log(trap(height));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def trap(height):
                if not height:
                    return 0
                n = len(height)
                left = [0] * n
                right = [0] * n
                left[0] = height[0]
                for index in range(1, n):
                    left[index] = max(left[index - 1], height[index])
                right[n - 1] = height[n - 1]
                for index in range(n - 2, -1, -1):
                    right[index] = max(right[index + 1], height[index])
                total = 0
                for index in range(n):
                    total += min(left[index], right[index]) - height[index]
                return total


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(trap(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function trap(height) {
              const n = height.length;
              if (n === 0) {
                return 0;
              }
              const left = new Array(n).fill(0);
              const right = new Array(n).fill(0);
              left[0] = height[0];
              for (let index = 1; index < n; index += 1) {
                left[index] = Math.max(left[index - 1], height[index]);
              }
              right[n - 1] = height[n - 1];
              for (let index = n - 2; index >= 0; index -= 1) {
                right[index] = Math.max(right[index + 1], height[index]);
              }
              let total = 0;
              for (let index = 0; index < n; index += 1) {
                total += Math.min(left[index], right[index]) - height[index];
              }
              return total;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const height = data.slice(1, 1 + n).map(Number);
              console.log(trap(height));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_trap, TRAP_INPUT),
        judged_case(_trap, "6\n4 2 0 3 2 5"),
        judged_case(_trap, "3\n2 0 2"),
        judged_case(_trap, "1\n5"),
        judged_case(_trap, "0\n", is_hidden=True),
        judged_case(_trap, "5\n5 4 3 2 1", is_hidden=True),
        judged_case(_trap, "5\n1 2 3 4 5", is_hidden=True),
        judged_case(_trap, "7\n0 1 0 2 1 0 1", is_hidden=True),
        judged_case(_trap, "6\n2 0 2 0 2 0", is_hidden=True),
    ],
}


ARRAYS_PROBLEMS: tuple[dict[str, Any], ...] = (
    TWO_SUM,
    MERGE_INTERVALS,
    CONTAINER_WITH_MOST_WATER,
    KTH_LARGEST,
    SINGLE_NUMBER,
    GROUP_ANAGRAMS,
    THREE_SUM,
    LONGEST_CONSECUTIVE_SEQUENCE,
    TRAPPING_RAIN_WATER,
)
