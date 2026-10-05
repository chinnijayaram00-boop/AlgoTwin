"""Heaps: the structure for "what changes at the boundary".

Three problems that all keep a stream rather than a list, and all keep it in a
structure that makes one question cheap:

* **Kth largest in a stream** keeps a min-heap of exactly `k` values. The heap is
  the size of the answer, not the size of the stream, which is the whole trick.
* **Sliding window maximum** uses a *monotonic* deque rather than a heap: the
  window's left edge moves one step at a time, and that is a stronger promise
  than a heap can exploit.
* **Median from a stream** needs both halves at once, so it keeps two heaps whose
  tops are the middle two values and rebalances between them.

The progression is deliberate. One heap is a tool. Two heaps with a rule about
their relative sizes is a design, and the design is what the median problem is
actually teaching.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source


# --------------------------------------------------------------------------- #
# Kth largest element in a stream
# --------------------------------------------------------------------------- #

KTH_STREAM_INPUT = "2 4\n3 2 1 5"


def _kth_largest(stdin: str) -> str:
    """Sort each prefix and index it: deliberately O(n^2 log n).

    The reference keeps a heap of `k` values instead, so agreement between them
    is a real check on the heap's boundary handling.
    """
    values = int_tokens(stdin)
    k = values[0]
    n = values[1]
    stream = values[2 : 2 + n]
    answers = []
    for index in range(k - 1, n):
        answers.append(str(sorted(stream[: index + 1], reverse=True)[k - 1]))
    return "\n".join(answers)


KTH_STREAM_BULK = [((index * 7919) % 100_003) for index in range(20_000)]
KTH_STREAM_BULK_INPUT = f"37 {len(KTH_STREAM_BULK)}\n" + " ".join(
    str(value) for value in KTH_STREAM_BULK
)


KTH_LARGEST_IN_STREAM: dict[str, Any] = {
    "slug": "kth-largest-in-stream",
    "title": "Kth Largest Element in a Stream",
    "summary": "Keep the top k values seen so far in a min-heap of size k.",
    "difficulty": "Medium",
    "topics": ["Heaps", "Streaming", "Sorting"],
    "description": (
        "A stream of integers arrives one value at a time. From the `k`th value "
        "onwards, report the `k`th largest value seen so far after each arrival.\n\n"
        "The first `k - 1` arrivals have no answer yet, so they produce no output. "
        "The stream is given in full on input, in the order the values arrive."
    ),
    "input_format": (
        "Line 1: `k n`.\n"
        "Line 2: `n` integers, the stream in arrival order.\n"
        "`1 <= k <= n`, so at least one answer always exists."
    ),
    "output_format": "Print `n - k + 1` lines, the `k`th largest value after each arrival from the `k`th onwards.",
    "constraints": (
        "1 <= k <= n <= 2 * 10^4 and -10^9 <= values <= 10^9. Values may repeat, and "
        "repeats count separately."
    ),
    "examples": [
        {
            "input": KTH_STREAM_INPUT,
            "output": _kth_largest(KTH_STREAM_INPUT),
            "explanation": "After 3 and 2 the second largest is 2; after adding 1 it is still 2; after adding 5 the top two are 5 and 3, so it is 3.",
        },
        {
            "input": "1 3\n-1 -2 -3",
            "output": _kth_largest("1 3\n-1 -2 -3"),
            "explanation": "With k = 1 the answer is the largest value so far, and this stream only ever decreases.",
        },
    ],
    "hints": [
        "Keeping every value and sorting on demand answers the question but ignores the only interesting thing about a stream: you never need to look at a value twice.",
        "You only need the top `k` values. Everything smaller than the `k`th largest can be discarded permanently, because a later value can only push things down, never promote a discarded one back into the top `k`.",
        "Keep those top `k` values in a **min**-heap, not a max-heap. The smallest of them is then on top, and that is the value you have to compare against: if the new value is larger, it belongs in the top `k` and the smallest has to go.",
        "After inserting, if the heap has more than `k` values, remove its root. The root is the current `k`th largest, so that single `peek` is the answer to print -- no sorting anywhere.",
        "The heap never grows past `k + 1` entries, so the whole stream costs O(n log k) rather than O(n log n). That difference is the problem."
    ],
    "explanation": (
        "The invariant is: after each step the min-heap holds exactly the `k` "
        "largest values seen so far, and no others.\n\n"
        "It is established once the heap has `k` elements, and maintained by one "
        "rule. When a new value arrives:\n\n"
        "* If the heap is not yet full, insert it. There cannot be `k` larger values "
        "than any of the stored ones yet.\n"
        "* Otherwise compare against the heap's root, which is the smallest of the "
        "stored `k` values and therefore the current `k`th largest. If the new "
        "value is larger, insert it and pop the root: the `k` smallest of the old "
        "`k + 1` values are removed, leaving the `k` largest. If it is not larger, "
        "discard it: the heap already holds `k` values at least as large, so the new "
        "one can never again reach the top `k`.\n\n"
        "The answer after each step is then simply the heap's root, which is why "
        "there is no sorting step anywhere.\n\n"
        "The discard is the part worth being careful about, because it is only "
        "sound because values are never removed from the stream. A value that is "
        "not in the top `k` at some moment cannot enter it later: the top `k` only "
        "changes by new arrivals displacing the smallest, which never promotes "
        "anything from below.\n\n"
        "The heap holds `k` values, so each step is O(log k) and the stream is "
        "processed in O(n log k) time and O(k) space. For `k = 1` the heap holds a "
        "single value and the structure degenerates to tracking a maximum, which is "
        "the right sanity check on any implementation."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n log k)",
    "expected_space_complexity": "O(k)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def kth_largest_stream(k, values):
                \"\"\"Return the kth largest value after every step of the stream.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                n = data[1]
                for answer in kth_largest_stream(k, data[2 : 2 + n]):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            class MinHeap {
              constructor() {
                this.values = [];
              }
            }

            function kthLargestStream(k, values) {
              // Return the kth largest value after every step of the stream.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const k = data[0];
              const n = data[1];
              for (const answer of kthLargestStream(k, data.slice(2, 2 + n))) {
                console.log(answer);
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.ArrayList;
            import java.util.List;
            import java.util.Scanner;

            public class Main {
                static List<Integer> kthLargestStream(int k, int[] values) {
                    // Return the kth largest value after every step of the stream.
                    return new ArrayList<>();
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int k = in.nextInt();
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    for (int answer : kthLargestStream(k, values)) {
                        System.out.println(answer);
                    }
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import heapq
            import sys


            def kth_largest_stream(k, values):
                top = []
                answers = []
                for value in values:
                    heapq.heappush(top, value)
                    if len(top) > k:
                        heapq.heappop(top)
                    if len(top) == k:
                        answers.append(top[0])
                return answers


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                n = data[1]
                for answer in kth_largest_stream(k, data[2 : 2 + n]):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            class MinHeap {
              constructor() {
                this.values = [];
              }

              push(value) {
                this.values.push(value);
                let child = this.values.length - 1;
                while (child > 0) {
                  const parent = Math.floor((child - 1) / 2);
                  if (this.values[parent] <= this.values[child]) {
                    break;
                  }
                  const swap = this.values[parent];
                  this.values[parent] = this.values[child];
                  this.values[child] = swap;
                  child = parent;
                }
              }

              peek() {
                return this.values[0];
              }

              pop() {
                const smallest = this.values[0];
                const last = this.values.pop();
                if (this.values.length > 0) {
                  this.values[0] = last;
                  let parent = 0;
                  for (;;) {
                    const left = parent * 2 + 1;
                    const right = left + 1;
                    let smallestChild = left;
                    if (right < this.values.length && this.values[right] < this.values[left]) {
                      smallestChild = right;
                    }
                    if (smallestChild >= this.values.length) {
                      break;
                    }
                    if (this.values[parent] <= this.values[smallestChild]) {
                      break;
                    }
                    const swap = this.values[parent];
                    this.values[parent] = this.values[smallestChild];
                    this.values[smallestChild] = swap;
                    parent = smallestChild;
                  }
                }
                return smallest;
              }

              get size() {
                return this.values.length;
              }
            }

            function kthLargestStream(k, values) {
              const top = new MinHeap();
              const answers = [];
              for (const value of values) {
                top.push(value);
                if (top.size > k) {
                  top.pop();
                }
                if (top.size === k) {
                  answers.push(top.peek());
                }
              }
              return answers;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const k = data[0];
              const n = data[1];
              for (const answer of kthLargestStream(k, data.slice(2, 2 + n))) {
                console.log(answer);
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.ArrayList;
            import java.util.List;
            import java.util.PriorityQueue;
            import java.util.Scanner;

            public class Main {
                static List<Integer> kthLargestStream(int k, int[] values) {
                    PriorityQueue<Integer> top = new PriorityQueue<>();
                    List<Integer> answers = new ArrayList<>();
                    for (int value : values) {
                        top.add(value);
                        if (top.size() > k) {
                            top.poll();
                        }
                        if (top.size() == k) {
                            answers.add(top.peek());
                        }
                    }
                    return answers;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int k = in.nextInt();
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    for (int answer : kthLargestStream(k, values)) {
                        System.out.println(answer);
                    }
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_kth_largest, KTH_STREAM_INPUT),
        judged_case(_kth_largest, "1 3\n-1 -2 -3"),
        judged_case(_kth_largest, "2 2\n7 7"),
        judged_case(_kth_largest, "3 4\n2 1 3 4"),
        judged_case(_kth_largest, "2 6\n5 4 3 2 1 0", is_hidden=True),
        judged_case(_kth_largest, "4 4\n-1 -2 -3 -4", is_hidden=True),
        judged_case(_kth_largest, "2 7\n8 8 1 1 9 9 2", is_hidden=True),
        judged_case(_kth_largest, "5 6\n10 -10 0 0 -10 10", is_hidden=True),
        judged_case(_kth_largest, "1 2\n-1000000000 1000000000", is_hidden=True),
        judged_case(_kth_largest, KTH_STREAM_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Sliding window maximum
# --------------------------------------------------------------------------- #

SLIDING_MAX_INPUT = "6 3\n2 1 3 4 6 3"


def _sliding_max(stdin: str) -> str:
    """Rescan every window: O(n * k), and impossible to get subtly wrong.

    The reference uses a monotonic deque, so this is the slow, obvious statement
    of the same question.
    """
    values = int_tokens(stdin)
    n = values[0]
    k = values[1]
    nums = values[2 : 2 + n]
    answers = []
    for start in range(n - k + 1):
        answers.append(str(max(nums[start : start + k])))
    return "\n".join(answers)


SLIDING_MAX_BULK = [((index * 3253) % 50_009) for index in range(4000)]
SLIDING_MAX_BULK_INPUT = f"{len(SLIDING_MAX_BULK)} 500\n" + " ".join(
    str(value) for value in SLIDING_MAX_BULK
)


SLIDING_WINDOW_MAXIMUM: dict[str, Any] = {
    "slug": "sliding-window-maximum",
    "title": "Sliding Window Maximum",
    "summary": "Answer every window's maximum with a deque of values that can still win.",
    "difficulty": "Hard",
    "topics": ["Heaps", "Sliding Window", "Monotonic Deque"],
    "description": (
        "Given an array of integers and a window size `k`, slide a window of "
        "length `k` across the array from left to right and report the largest "
        "value inside each window.\n\n"
        "Each window differs from the previous one by exactly one removal and one "
        "addition, and there are `n - k + 1` windows."
    ),
    "input_format": (
        "Line 1: `n k`.\nLine 2: `n` integers."
    ),
    "output_format": "Print `n - k + 1` lines, the maximum of each window in order.",
    "constraints": (
        "1 <= k <= n <= 4 * 10^3 and -10^9 <= nums[i] <= 10^9. Values may be equal "
        "and the array need not be sorted."
    ),
    "examples": [
        {
            "input": SLIDING_MAX_INPUT,
            "output": _sliding_max(SLIDING_MAX_INPUT),
            "explanation": "The windows are [2,1,3], [1,3,4], [3,4,6] and [4,6,3], so the answers are 3, 4, 6 and 3.",
        },
        {
            "input": "5 5\n5 4 3 2 1",
            "output": _sliding_max("5 5\n5 4 3 2 1"),
            "explanation": "A window covering the whole array is the only window, so the answer is 5.",
        },
    ],
    "hints": [
        "A heap gives O(n log k) and is correct, so reach for it first if you like -- but look at how little the problem actually promises. The window's left edge moves exactly one step per answer, which is far more than a heap needs.",
        "Ask what you may throw away permanently. A value that is smaller than something to its right can never be a window maximum again: any future window containing it also contains that larger value to its right.",
        "That gives a strictly decreasing sequence of candidate values, kept in order of arrival. Store them with their indices so you can tell whether the oldest one has fallen out of the window.",
        "The oldest candidate is the front of the deque, so dropping the expired ones is a loop at the front and the answer is always the front after that loop. Adding a value means popping from the back every value smaller than it, then pushing it.",
        "Each index is pushed once and popped at most once, from either end, so the whole thing is O(n) -- no heap and no log factor."
    ],
    "explanation": (
        "The key observation is about what can be discarded. Suppose `nums[i] <= "
        "nums[j]` for some `i < j`. Any window that contains index `i` and ends "
        "after index `j` contains `j` as well, so `nums[i]` is not the maximum of "
        "that window. And every window that contains `i` but not `j` ends before "
        "`j`, meaning it has already been answered. So once `j` arrives, `i` is "
        "finished: it can neither be an answer now nor an answer later.\n\n"
        "That justifies keeping the candidates in a **decreasing** deque of indices, "
        "newest at the back. For each new index `j`:\n\n"
        "1. Pop from the back while the value there is `<= nums[j]`. Those indices "
        "are exactly the ones the observation discards.\n"
        "2. Push `j`.\n\n"
        "The deque is now sorted by decreasing value, so its front holds the largest "
        "value not yet discarded. It is the answer provided it is still inside the "
        "current window, and since the deque is in index order, only the front can "
        "be expired. So before reading the answer, pop from the front while the "
        "front index is `<= j - k`.\n\n"
        "With those two loops the answer is always the front of the deque. The "
        "deque's values are strictly decreasing, which also means its length is at "
        "most `k` once the expired indices are gone.\n\n"
        "Every index is pushed exactly once and popped at most once, from one end "
        "or the other, so the total work is O(n) and the deque holds O(k) indices. "
        "The equal-value case is why the back-loop uses `<=` rather than `<`: a "
        "later value that merely *ties* the earlier one still makes the earlier one "
        "unnecessary, and using `<` would leave ties to expire one at a time."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(k)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def sliding_maximum(nums, k):
                \"\"\"Return the maximum of every window of length k, in order.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                k = data[1]
                for answer in sliding_maximum(data[2 : 2 + n], k):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function slidingMaximum(nums, k) {
              // Return the maximum of every window of length k, in order.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const n = data[0];
              const k = data[1];
              for (const answer of slidingMaximum(data.slice(2, 2 + n), k)) {
                console.log(answer);
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.ArrayDeque;
            import java.util.ArrayList;
            import java.util.Deque;
            import java.util.List;
            import java.util.Scanner;

            public class Main {
                static List<Integer> slidingMaximum(int[] nums, int k) {
                    // Return the maximum of every window of length k, in order.
                    return new ArrayList<>();
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int k = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    for (int answer : slidingMaximum(nums, k)) {
                        System.out.println(answer);
                    }
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys
            from collections import deque


            def sliding_maximum(nums, k):
                candidates = deque()
                answers = []
                for index, value in enumerate(nums):
                    while candidates and index - candidates[0] >= k:
                        candidates.popleft()
                    while candidates and nums[candidates[-1]] <= value:
                        candidates.pop()
                    candidates.append(index)
                    if index >= k - 1:
                        answers.append(nums[candidates[0]])
                return answers


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                k = data[1]
                for answer in sliding_maximum(data[2 : 2 + n], k):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function slidingMaximum(nums, k) {
              const candidates = [];
              const answers = [];
              for (let index = 0; index < nums.length; index += 1) {
                while (candidates.length > 0 && index - candidates[0] >= k) {
                  candidates.shift();
                }
                while (
                  candidates.length > 0 &&
                  nums[candidates[candidates.length - 1]] <= nums[index]
                ) {
                  candidates.pop();
                }
                candidates.push(index);
                if (index >= k - 1) {
                  answers.push(nums[candidates[0]]);
                }
              }
              return answers;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const n = data[0];
              const k = data[1];
              for (const answer of slidingMaximum(data.slice(2, 2 + n), k)) {
                console.log(answer);
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.ArrayDeque;
            import java.util.ArrayList;
            import java.util.Deque;
            import java.util.List;
            import java.util.Scanner;

            public class Main {
                static List<Integer> slidingMaximum(int[] nums, int k) {
                    Deque<Integer> candidates = new ArrayDeque<>();
                    List<Integer> answers = new ArrayList<>();
                    for (int index = 0; index < nums.length; index += 1) {
                        while (!candidates.isEmpty() && index - candidates.peekFirst() >= k) {
                            candidates.pollFirst();
                        }
                        while (!candidates.isEmpty() && nums[candidates.peekLast()] <= nums[index]) {
                            candidates.pollLast();
                        }
                        candidates.addLast(index);
                        if (index >= k - 1) {
                            answers.add(nums[candidates.peekFirst()]);
                        }
                    }
                    return answers;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int k = in.nextInt();
                    int[] nums = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        nums[i] = in.nextInt();
                    }
                    for (int answer : slidingMaximum(nums, k)) {
                        System.out.println(answer);
                    }
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_sliding_max, SLIDING_MAX_INPUT),
        judged_case(_sliding_max, "5 5\n5 4 3 2 1"),
        judged_case(_sliding_max, "1 1\n42"),
        judged_case(_sliding_max, "5 2\n3 3 3 3 3"),
        judged_case(_sliding_max, "6 3\n7 2 4 1 5 3", is_hidden=True),
        judged_case(_sliding_max, "6 4\n-5 -5 -5 -5 -5 -5", is_hidden=True),
        judged_case(_sliding_max, "7 2\n9 8 7 6 5 4 3", is_hidden=True),
        judged_case(_sliding_max, "8 3\n1 2 3 4 5 6 7 8", is_hidden=True),
        judged_case(_sliding_max, SLIDING_MAX_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Find the median from a stream
# --------------------------------------------------------------------------- #

MEDIAN_STREAM_INPUT = "6\n5 15 1 3 8 7"


def _median_stream(stdin: str) -> str:
    """Sort each prefix and index the middle: O(n^2 log n) and totally clear."""
    values = int_tokens(stdin)
    n = values[0]
    stream = values[1 : 1 + n]
    answers = []
    for index in range(n):
        prefix = sorted(stream[: index + 1])
        middle = len(prefix) // 2
        if len(prefix) % 2 == 1:
            answers.append(str(prefix[middle]))
        else:
            answers.append(str((prefix[middle - 1] + prefix[middle]) // 2))
    return "\n".join(answers)


MEDIAN_STREAM_BULK = [((index * 5171) % 200_003) for index in range(6000)]
MEDIAN_STREAM_BULK_INPUT = f"{len(MEDIAN_STREAM_BULK)}\n" + " ".join(
    str(value) for value in MEDIAN_STREAM_BULK
)


FIND_MEDIAN_FROM_STREAM: dict[str, Any] = {
    "slug": "find-median-from-stream",
    "title": "Find the Median from a Stream",
    "summary": "Two heaps, kept balanced against each other, hold the middle of a stream.",
    "difficulty": "Hard",
    "topics": ["Heaps", "Streaming", "Design"],
    "description": (
        "A stream of integers arrives one value at a time. After each value, report "
        "the median of everything seen so far.\n\n"
        "The median of an odd number of values is the middle one. For an even "
        "number, average the two middle values; because this problem works in "
        "integers, print that average **truncated toward negative infinity**.\n\n"
        "The stream is given in full on input, in arrival order. Print one line per "
        "step."
    ),
    "input_format": (
        "Line 1: `n`.\nLine 2: `n` integers, the stream in arrival order."
    ),
    "output_format": "Print `n` lines, the median after each step.",
    "constraints": (
        "1 <= n <= 2 * 10^4 and -10^9 <= values <= 10^9. Duplicates and a "
        "decreasing stream are both allowed."
    ),
    "examples": [
        {
            "input": MEDIAN_STREAM_INPUT,
            "output": _median_stream(MEDIAN_STREAM_INPUT),
            "explanation": "The prefixes are [5], [5 15], [1 5 15], [1 3 5 15], [1 3 5 8 15] and [1 3 5 7 8 15], so the medians are 5, 10, 5, 4, 5 and 6.",
        },
        {
            "input": "4\n2 2 2 2",
            "output": _median_stream("4\n2 2 2 2"),
            "explanation": "Every prefix has median 2, including the even-length ones, where the two middle values are both 2.",
        },
    ],
    "hints": [
        "The median is a *rank*, not a value, so what you need is cheap access to the middle of a growing collection. A list gives that but inserts in O(n), and a sorted array gives it in O(1) at O(n) cost per arrival. Something in between is possible.",
        "Split the values seen so far into two halves: a lower half and an upper half. The median is then determined by the tops of both halves and nothing else, so you never need the values underneath.",
        "Keep the lower half in a max-heap and the upper half in a min-heap. The max-heap's top is the largest of the lower half and the min-heap's top is the smallest of the upper half, so those two tops are the two middle values whenever the split is right.",
        "Keep two invariants and the answer is trivial: every lower value is `<=` every upper value, and `size(lower)` is either equal to `size(upper)` or one larger. Only the second value can break them, and moving one element between the heaps repairs both.",
        "For an odd count, both tops are the same element: the max-heap's top. For an even count they are the two middle values and you average them -- and since integer division truncates toward zero in two of the three languages, use explicit floor division rather than dividing and hoping."
    ],
    "explanation": (
        "The design is two heaps and one invariant between them.\n\n"
        "* `lower` is a **max**-heap holding the smaller half of the values seen.\n"
        "* `upper` is a **min**-heap holding the larger half.\n\n"
        "Two properties are maintained after every arrival:\n\n"
        "1. `max(lower) <= min(upper)`, so the two halves are correctly separated.\n"
        "2. `|lower| == |upper|` or `|lower| == |upper| + 1`, so the lower half is "
        "never the smaller one.\n\n"
        "Given those, the median follows immediately. When the count is odd the "
        "median is the single middle value, which by property 2 is `max(lower)`. "
        "When the count is even the two middle values are `max(lower)` and "
        "`min(upper)`, and their average is the answer.\n\n"
        "Insertion is where the properties are maintained. A new value is compared "
        "against `max(lower)`: if the lower half is empty, or the value is `<= "
        "max(lower)`, it goes into `lower`; otherwise it goes into `upper`. That "
        "single comparison preserves property 1, because the value is placed on the "
        "correct side of the boundary and the heap's own ordering keeps that half "
        "internally sorted.\n\n"
        "Property 2 then needs at most one move. If `|lower| > |upper| + 1`, move "
        "`max(lower)` into `upper`; if `|lower| < |upper|`, move `min(upper)` into "
        "`lower`. Both moves cross the boundary in the direction that keeps "
        "property 1 true, since the value moved is exactly the extreme of its half. "
        "Only one move can ever be needed, because the sizes were balanced before "
        "the arrival and one insertion shifts the difference by one.\n\n"
        "Each arrival is one heap push, at most one pop and one push, and one "
        "comparison of tops, so it costs O(log n) time. The two heaps together hold "
        "exactly the values seen so far, so the space is O(n)."
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


            def median_stream(values):
                \"\"\"Return the median after every step of the stream.\"\"\"
                return []


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                for answer in median_stream(data[1 : 1 + n]):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            class Heap {
              constructor(compare) {
                this.compare = compare;
                this.values = [];
              }

              get size() {
                return this.values.length;
              }

              peek() {
                return this.values[0];
              }

              push(value) {
                this.values.push(value);
                let child = this.values.length - 1;
                while (child > 0) {
                  const parent = Math.floor((child - 1) / 2);
                  if (this.compare(this.values[parent], this.values[child]) <= 0) {
                    break;
                  }
                  const swap = this.values[parent];
                  this.values[parent] = this.values[child];
                  this.values[child] = swap;
                  child = parent;
                }
              }

              pop() {
                const top = this.values[0];
                const last = this.values.pop();
                if (this.values.length > 0) {
                  this.values[0] = last;
                  let parent = 0;
                  for (;;) {
                    const left = parent * 2 + 1;
                    const right = left + 1;
                    let best = left;
                    if (right < this.values.length && this.compare(this.values[right], this.values[left]) < 0) {
                      best = right;
                    }
                    if (best >= this.values.length) {
                      break;
                    }
                    if (this.compare(this.values[parent], this.values[best]) <= 0) {
                      break;
                    }
                    const swap = this.values[parent];
                    this.values[parent] = this.values[best];
                    this.values[best] = swap;
                    parent = best;
                  }
                }
                return top;
              }
            }

            function medianStream(values) {
              // Return the median after every step of the stream.
              return [];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const n = data[0];
              for (const answer of medianStream(data.slice(1, 1 + n))) {
                console.log(answer);
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.ArrayList;
            import java.util.Collections;
            import java.util.List;
            import java.util.PriorityQueue;
            import java.util.Scanner;

            public class Main {
                static List<Integer> medianStream(int[] values) {
                    // Return the median after every step of the stream.
                    return new ArrayList<>();
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    for (int answer : medianStream(values)) {
                        System.out.println(answer);
                    }
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import heapq
            import sys


            def median_stream(values):
                lower = []
                upper = []
                answers = []
                for value in values:
                    if not lower or value <= -lower[0]:
                        heapq.heappush(lower, -value)
                    else:
                        heapq.heappush(upper, value)
                    if len(lower) > len(upper) + 1:
                        heapq.heappush(upper, -heapq.heappop(lower))
                    elif len(lower) < len(upper):
                        heapq.heappush(lower, -heapq.heappop(upper))
                    if len(lower) > len(upper):
                        answers.append(-lower[0])
                    else:
                        answers.append((-lower[0] + upper[0]) // 2)
                return answers


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                for answer in median_stream(data[1 : 1 + n]):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            class Heap {
              constructor(compare) {
                this.compare = compare;
                this.values = [];
              }

              get size() {
                return this.values.length;
              }

              peek() {
                return this.values[0];
              }

              push(value) {
                this.values.push(value);
                let child = this.values.length - 1;
                while (child > 0) {
                  const parent = Math.floor((child - 1) / 2);
                  if (this.compare(this.values[parent], this.values[child]) <= 0) {
                    break;
                  }
                  const swap = this.values[parent];
                  this.values[parent] = this.values[child];
                  this.values[child] = swap;
                  child = parent;
                }
              }

              pop() {
                const top = this.values[0];
                const last = this.values.pop();
                if (this.values.length > 0) {
                  this.values[0] = last;
                  let parent = 0;
                  for (;;) {
                    const left = parent * 2 + 1;
                    const right = left + 1;
                    let best = left;
                    if (right < this.values.length && this.compare(this.values[right], this.values[left]) < 0) {
                      best = right;
                    }
                    if (best >= this.values.length) {
                      break;
                    }
                    if (this.compare(this.values[parent], this.values[best]) <= 0) {
                      break;
                    }
                    const swap = this.values[parent];
                    this.values[parent] = this.values[best];
                    this.values[best] = swap;
                    parent = best;
                  }
                }
                return top;
              }
            }

            function medianStream(values) {
              const lower = new Heap((left, right) => right - left);
              const upper = new Heap((left, right) => left - right);
              const answers = [];
              for (const value of values) {
                if (lower.size === 0 || value <= lower.peek()) {
                  lower.push(value);
                } else {
                  upper.push(value);
                }
                if (lower.size > upper.size + 1) {
                  upper.push(lower.pop());
                } else if (lower.size < upper.size) {
                  lower.push(upper.pop());
                }
                if (lower.size > upper.size) {
                  answers.push(lower.peek());
                } else {
                  answers.push(Math.floor((lower.peek() + upper.peek()) / 2));
                }
              }
              return answers;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const n = data[0];
              for (const answer of medianStream(data.slice(1, 1 + n))) {
                console.log(answer);
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.ArrayList;
            import java.util.Collections;
            import java.util.List;
            import java.util.PriorityQueue;
            import java.util.Scanner;

            public class Main {
                static List<Long> medianStream(int[] values) {
                    PriorityQueue<Integer> lower = new PriorityQueue<>(Collections.reverseOrder());
                    PriorityQueue<Integer> upper = new PriorityQueue<>();
                    List<Long> answers = new ArrayList<>();
                    for (int value : values) {
                        if (lower.isEmpty() || value <= lower.peek()) {
                            lower.add(value);
                        } else {
                            upper.add(value);
                        }
                        if (lower.size() > upper.size() + 1) {
                            upper.add(lower.poll());
                        } else if (lower.size() < upper.size()) {
                            lower.add(upper.poll());
                        }
                        if (lower.size() > upper.size()) {
                            answers.add((long) lower.peek());
                        } else {
                            answers.add(Math.floorDiv((long) lower.peek() + upper.peek(), 2L));
                        }
                    }
                    return answers;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    for (long answer : medianStream(values)) {
                        System.out.println(answer);
                    }
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_median_stream, MEDIAN_STREAM_INPUT),
        judged_case(_median_stream, "4\n2 2 2 2"),
        judged_case(_median_stream, "1\n7"),
        judged_case(_median_stream, "3\n-5 0 5"),
        judged_case(_median_stream, "5\n9 8 7 6 5", is_hidden=True),
        judged_case(_median_stream, "6\n-1 -2 -3 -4 -5 -6", is_hidden=True),
        judged_case(_median_stream, "6\n100 -100 100 -100 50 -50", is_hidden=True),
        judged_case(_median_stream, "8\n0 0 0 1 1 1 2 2", is_hidden=True),
        judged_case(_median_stream, MEDIAN_STREAM_BULK_INPUT, is_hidden=True),
    ],
}


HEAPS_PROBLEMS: tuple[dict[str, Any], ...] = (
    KTH_LARGEST_IN_STREAM,
    SLIDING_WINDOW_MAXIMUM,
    FIND_MEDIAN_FROM_STREAM,
)
