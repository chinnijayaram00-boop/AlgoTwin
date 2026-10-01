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


ARRAYS_PROBLEMS: tuple[dict[str, Any], ...] = (
    TWO_SUM,
    MERGE_INTERVALS,
    CONTAINER_WITH_MOST_WATER,
    KTH_LARGEST,
    SINGLE_NUMBER,
)
