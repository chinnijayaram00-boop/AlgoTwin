"""Searching, and the two dynamic-programming shapes worth learning first.

Binary search, jump game, maximum subarray, and coin change. Between them they
introduce the three ways a learner first meets a table of answers: shrink a
range by halving it, keep a running best while scanning once, and build a table
of best answers for every amount up to a bound.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source

# --------------------------------------------------------------------------- #
# Binary Search
# --------------------------------------------------------------------------- #


def _binary_search(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    target = values[1 + n]
    low, high = 0, n - 1
    while low <= high:
        middle = (low + high) // 2
        if nums[middle] == target:
            return str(middle)
        if nums[middle] < target:
            low = middle + 1
        else:
            high = middle - 1
    return "-1"


BINARY_SEARCH_INPUT = "6\n-1 0 3 5 9 12\n9"

BINARY_SEARCH: dict[str, Any] = {
    "slug": "binary-search",
    "title": "Binary Search",
    "summary": "Find a target in a sorted array in logarithmic time.",
    "difficulty": "Easy",
    "topics": ["Arrays", "Binary Search"],
    "description": (
        "Given a sorted array of distinct integers `nums` and an integer "
        "`target`, return the index of `target`, or `-1` when it is absent.\n\n"
        "You may not look at more than O(log n) elements, which rules out a "
        "linear scan."
    ),
    "input_format": (
        "Line 1: `n`, how many values follow.\n"
        "Line 2: `n` distinct integers in ascending order.\n"
        "Line 3: `target`."
    ),
    "output_format": "Print the 0-based index of target, or `-1` if it is not present.",
    "constraints": (
        "1 <= n <= 10^4, -10^4 <= nums[i] <= 10^4, the values are distinct and "
        "sorted ascending."
    ),
    "examples": [
        {
            "input": BINARY_SEARCH_INPUT,
            "output": _binary_search(BINARY_SEARCH_INPUT),
            "explanation": "9 sits at index 4.",
        }
    ],
    "hints": [
        "Comparing against every element is O(n). What does the sorted order let you conclude after a single comparison?",
        "A comparison against the middle element tells you which half cannot contain the target, so you can discard half the array each time. That is the whole idea.",
        "Keep `low` and `high` as the range that could still hold the target, and set `middle` to the midpoint. If the middle value is too small, move `low` past it; if too large, move `high` before it.",
        "Use `middle = low + (high - low) // 2` rather than `(low + high) // 2`. The two agree in Python, but the first form does not overflow in a language with fixed-width integers.",
        "The loop condition is `low <= high`, not `low < high`: with a single candidate left, `low == high`, and that element still has to be checked. Exiting when the values cross is what makes the missing-target case return -1.",
    ],
    "explanation": (
        "Keep a range `low..high` that is guaranteed to contain the target if the "
        "target is present. Compare the midpoint against the target: if it "
        "matches, the search is done; if the midpoint value is smaller, then "
        "every index at or below the midpoint is also smaller, because the array "
        "is sorted, so `low` moves to `middle + 1`. Otherwise every index at or "
        "above the midpoint is too large, so `high` moves to `middle - 1`.\n\n"
        "Each step discards half the remaining range, so the loop runs at most "
        "ceil(log2(n + 1)) times -- 14 steps for a million elements, against a "
        "million for a scan. When `low` crosses `high` the range is empty, which "
        "means the target was not there, and the answer is -1.\n\n"
        "The `low <= high` condition is what makes the single-candidate case "
        "work: when one element remains it is still possible that it is the "
        "target, so the loop must not exit yet. Space is O(1)."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(log n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def search(nums, target):
                \"\"\"Return the index of target in a sorted array, or -1.\"\"\"
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
              // Return the index of target in a sorted array, or -1.
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
                    if nums[middle] < target:
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
                if (nums[middle] < target) {
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
    },
    "test_cases": [
        judged_case(_binary_search, BINARY_SEARCH_INPUT),
        judged_case(_binary_search, "1\n5\n5"),
        judged_case(_binary_search, "2\n1 2\n3"),
        judged_case(_binary_search, "4\n-7 -3 0 8\n-3"),
        judged_case(_binary_search, "8\n-9 -5 -3 -1 2 4 6 10\n0", is_hidden=True),
        judged_case(_binary_search, "10\n1 2 3 4 5 6 7 8 9 10\n1", is_hidden=True),
        judged_case(_binary_search, "5\n-5 -4 -3 -2 -1\n-5", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Jump Game
# --------------------------------------------------------------------------- #


def _jump_game(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    jumps = values[1 : 1 + n]
    target = values[1 + n]
    reachable = 0
    for index, length in enumerate(jumps):
        if index > reachable:
            return "false"
        reachable = max(reachable, index + length)
        if reachable >= target:
            return "true"
    return "true" if reachable >= target else "false"


JUMP_GAME_INPUT = "5\n2 3 1 1 4\n4"

JUMP_GAME: dict[str, Any] = {
    "slug": "jump-game",
    "title": "Jump Game",
    "summary": "Decide whether the last index of an array is reachable in a fixed number of jumps.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Greedy", "Dynamic Programming"],
    "description": (
        "You are given an integer array `nums`. From index `i` you may jump "
        "forward to any index `j` with `i < j <= i + nums[i]`.\n\n"
        "Decide whether the last index can be reached. Return `true` if it can "
        "and `false` otherwise."
    ),
    "input_format": (
        "Line 1: `n`, how many values follow.\n"
        "Line 2: `n` non-negative integers, the jump length from each index.\n"
        "Line 3: `target`, the index that has to be reached."
    ),
    "output_format": "Print `true` if target is reachable, otherwise `false`, in lower case.",
    "constraints": (
        "1 <= n <= 10^5, 0 <= nums[i] <= 10^3, and target is a valid index from "
        "0 to n - 1."
    ),
    "examples": [
        {
            "input": JUMP_GAME_INPUT,
            "output": _jump_game(JUMP_GAME_INPUT),
            "explanation": "Index 0 jumps 2, index 2 jumps 1, index 3 jumps 1, so index 4 is reached.",
        }
    ],
    "hints": [
        "Dynamic programming works and is O(n^2) if you ask, from every index, which indexes it can reach. Ask what all those sets have in common.",
        "You never need to know the whole reachable set. If you track only the farthest index you can reach, every index before it is reachable too, because jumps never go backwards.",
        "Walk the array keeping `reachable`, the farthest index reached so far. For each index `i`, extend it to `max(reachable, i + nums[i])`.",
        "If you ever meet an index that is beyond `reachable`, you are stuck: every earlier index was already considered and none of them reached this one. Return false there.",
        "Stop as soon as `reachable` covers the target. There is no need to look at the remaining entries, so a greedy early exit is safe and is the difference between useful and wasted work on a large input.",
    ],
    "explanation": (
        "Because a jump only ever moves forward, reaching index `r` means every "
        "index from 0 to `r` is reachable. So the only state worth keeping is the "
        "farthest index reached, not the set of reachable indexes.\n\n"
        "Scan the array. For each index `i`, extend the frontier to "
        "`max(reachable, i + nums[i])`. If `i` is already past `reachable` then "
        "the frontier cannot be extended any further -- every earlier index has "
        "been considered and none of their jumps reach `i` -- so the answer is "
        "false. Otherwise, once `reachable` covers the target, the answer is true.\n\n"
        "One pass, one integer of state: O(n) time and O(1) space. The early exit "
        "matters on a large input, where the answer is usually known long before "
        "the last element."
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


            def can_reach(nums, target):
                \"\"\"Return True when target can be reached from index 0.\"\"\"
                return False


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print("true" if can_reach(data[1 : 1 + n], data[1 + n]) else "false")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function canReach(nums, target) {
              // Return true when target can be reached from index 0.
              return false;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              console.log(canReach(nums, target) ? "true" : "false");
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def can_reach(nums, target):
                reachable = 0
                for index, length in enumerate(nums):
                    if index > reachable:
                        return False
                    reachable = max(reachable, index + length)
                    if reachable >= target:
                        return True
                return reachable >= target


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print("true" if can_reach(data[1 : 1 + n], data[1 + n]) else "false")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function canReach(nums, target) {
              let reachable = 0;
              for (let index = 0; index < nums.length; index += 1) {
                if (index > reachable) {
                  return false;
                }
                reachable = Math.max(reachable, index + nums[index]);
                if (reachable >= target) {
                  return true;
                }
              }
              return reachable >= target;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              const target = Number(data[1 + n]);
              console.log(canReach(nums, target) ? "true" : "false");
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_jump_game, JUMP_GAME_INPUT),
        judged_case(_jump_game, "1\n0\n0"),
        judged_case(_jump_game, "3\n0 1 0\n2"),
        judged_case(_jump_game, "4\n1 1 1 0\n3"),
        judged_case(_jump_game, "5\n2 0 0 0 0\n4", is_hidden=True),
        judged_case(_jump_game, "6\n1 0 1 0 1 0\n5", is_hidden=True),
        judged_case(_jump_game, "8\n2 0 0 0 0 0 0 9\n7", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Maximum Subarray
# --------------------------------------------------------------------------- #


def _maximum_subarray(stdin: str) -> str:
    values = int_tokens(stdin)
    n = values[0]
    nums = values[1 : 1 + n]
    if n == 0:
        return "0"
    best = current = nums[0]
    for value in nums[1:]:
        current = max(value, current + value)
        best = max(best, current)
    return str(best)


MAXIMUM_SUBARRAY_INPUT = "5\n-2 1 -3 4 -1 2"

MAXIMUM_SUBARRAY: dict[str, Any] = {
    "slug": "maximum-subarray",
    "title": "Maximum Subarray",
    "summary": "Find the contiguous subarray with the largest sum.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Dynamic Programming"],
    "description": (
        "Given an integer array `nums`, return the largest sum of a contiguous "
        "non-empty subarray.\n\n"
        "The subarray has to be contiguous, so skipping an element in the middle "
        "is not allowed."
    ),
    "input_format": "Line 1: `n`, how many values follow.\nLine 2: `n` integers.",
    "output_format": "Print the largest sum of any contiguous non-empty subarray.",
    "constraints": "-10^4 <= nums[i] <= 10^4. Return 0 for an empty array.",
    "examples": [
        {
            "input": MAXIMUM_SUBARRAY_INPUT,
            "output": _maximum_subarray(MAXIMUM_SUBARRAY_INPUT),
            "explanation": "The subarray [4, -1, 2] sums to 5, which is the largest.",
        }
    ],
    "hints": [
        "Try every starting index and extend to the end: that is O(n^2). The subarrays that win share a pattern, so find it.",
        "At each index, ask a narrower question: what is the best sum of a subarray that *ends* at this index? Answer that for every index and the overall answer is the largest of them.",
        "A subarray ending at `i` either starts fresh at `i`, or extends the best subarray ending at `i - 1`. So `current = max(nums[i], current + nums[i])`.",
        "Initialise both the running best and the overall best with the first element, not with zero. Starting at zero would let the empty subarray win, and the statement requires a non-empty one.",
        "This is Kadane's algorithm. It works for any operation where extending and combining is associative, which is a useful thing to notice rather than memorise.",
    ],
    "explanation": (
        "The key idea is to stop searching over all subarrays and instead answer "
        "one narrow question per index: what is the largest sum of a subarray "
        "that ends here?\n\n"
        "Any subarray ending at `i` either consists of `nums[i]` alone or extends "
        "the best subarray ending at `i - 1`. That gives the recurrence "
        "`current = max(nums[i], current + nums[i])`, and the answer is the "
        "largest value `current` ever takes. This is Kadane's algorithm.\n\n"
        "Both accumulators start at the first element rather than at zero, so an "
        "all-negative array correctly returns its largest element instead of 0. "
        "The scan is a single pass with two integers of state, so the time is "
        "O(n) and the space is O(1)."
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


            def max_subarray(nums):
                \"\"\"Return the largest sum of a contiguous non-empty subarray.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(max_subarray(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function maxSubarray(nums) {
              // Return the largest sum of a contiguous non-empty subarray.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(maxSubarray(nums));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def max_subarray(nums):
                if not nums:
                    return 0
                best = current = nums[0]
                for value in nums[1:]:
                    current = max(value, current + value)
                    best = max(best, current)
                return best


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                print(max_subarray(data[1 : 1 + n]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function maxSubarray(nums) {
              if (nums.length === 0) {
                return 0;
              }
              let best = nums[0];
              let current = nums[0];
              for (let index = 1; index < nums.length; index += 1) {
                current = Math.max(nums[index], current + nums[index]);
                best = Math.max(best, current);
              }
              return best;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const nums = data.slice(1, 1 + n).map(Number);
              console.log(maxSubarray(nums));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_maximum_subarray, MAXIMUM_SUBARRAY_INPUT),
        judged_case(_maximum_subarray, "1\n7"),
        judged_case(_maximum_subarray, "5\n-3 -1 -4 -1 -5"),
        judged_case(_maximum_subarray, "4\n1 2 3 4"),
        judged_case(_maximum_subarray, "0", is_hidden=True),
        judged_case(_maximum_subarray, "6\n-2 1 -3 4 -1 2", is_hidden=True),
        judged_case(_maximum_subarray, "8\n-5 1 4 -7 8 -3 4 -2", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Coin Change
# --------------------------------------------------------------------------- #


def _coin_change(stdin: str) -> str:
    values = int_tokens(stdin)
    k = values[0]
    amount = values[1]
    coins = values[2 : 2 + k]
    unreachable = amount + 1
    best = [0] + [unreachable] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value and best[value - coin] + 1 < best[value]:
                best[value] = best[value - coin] + 1
    return "-1" if best[amount] == unreachable else str(best[amount])


COIN_CHANGE_INPUT = "4 11\n1 2 5"

COIN_CHANGE: dict[str, Any] = {
    "slug": "coin-change",
    "title": "Coin Change",
    "summary": "Find the fewest coins that add up to an exact amount.",
    "difficulty": "Medium",
    "topics": ["Arrays", "Dynamic Programming"],
    "description": (
        "You are given coins with values `coins` and an amount `amount`. Each "
        "coin may be used any number of times, including none.\n\n"
        "Return the fewest coins that add up exactly to `amount`. If no "
        "combination works, return -1."
    ),
    "input_format": (
        "Line 1: `k amount`, how many coin values follow and the target amount.\n"
        "Line 2: `k` positive integers, the coin values."
    ),
    "output_format": "Print the fewest number of coins, or `-1` if the amount cannot be made.",
    "constraints": "1 <= k <= 12, 1 <= coins[i] <= 10^3, 0 <= amount <= 10^3.",
    "examples": [
        {
            "input": COIN_CHANGE_INPUT,
            "output": _coin_change(COIN_CHANGE_INPUT),
            "explanation": "5 + 5 + 1 makes 11 with three coins, and no two coins reach it.",
        }
    ],
    "hints": [
        "Trying every combination of coins is exponential, and greedy -- always take the largest coin that fits -- is wrong here. Ask what a subproblem would be.",
        "The subproblem is a smaller amount: to make `amount - coin` you need a best answer too. So define the answer for every amount from 0 up to the target.",
        "Build a table where `best[v]` is the fewest coins that make `v`. Set `best[0] = 0`, and for every amount `v` and every coin `c <= v` consider `best[v - c] + 1`.",
        "Fill the table in increasing order of `v`, so every `best[v - coin]` is already final when you read it. Reversing the loops order would read an answer that has not been computed yet.",
        "Use a sentinel larger than any real answer -- `amount + 1` -- for impossible amounts, rather than a large number like infinity that could overflow when you add one to it in a fixed-width integer.",
    ],
    "explanation": (
        "Define `best[v]` as the fewest coins that make exactly `v`. The base "
        "case is `best[0] = 0`; making nothing takes no coins.\n\n"
        "Any way of making `v` ends with some coin `c`, and what came before it "
        "made `v - c`. So the best answer that ends with `c` is `best[v - c] + 1`, "
        "and the answer for `v` is the minimum of that over every coin `c <= v`. "
        "Filling `v` in increasing order guarantees `best[v - c]` is already "
        "computed, since `c` is positive.\n\n"
        "Impossible amounts are stored as the sentinel `amount + 1`, which is "
        "larger than any real answer, so the arithmetic `best[v - c] + 1` never "
        "overflows a fixed-width integer and a real answer always beats the "
        "sentinel. If `best[amount]` is still the sentinel, the amount cannot be "
        "made and the answer is -1.\n\n"
        "The table has `amount` entries and each is filled from at most `k` "
        "predecessors, so the time is O(amount * k) and the space is O(amount)."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(amount * k)",
    "expected_space_complexity": "O(amount)",
    "time_limit_ms": 2_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def fewest_coins(coins, amount):
                \"\"\"Return the fewest coins that make amount, or -1.\"\"\"
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                amount = data[1]
                print(fewest_coins(data[2 : 2 + k], amount))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function fewestCoins(coins, amount) {
              // Return the fewest coins that make amount, or -1.
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              const amount = Number(data[1]);
              const coins = data.slice(2, 2 + k).map(Number);
              console.log(fewestCoins(coins, amount));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def fewest_coins(coins, amount):
                unreachable = amount + 1
                best = [0] + [unreachable] * amount
                for value in range(1, amount + 1):
                    for coin in coins:
                        if coin <= value and best[value - coin] + 1 < best[value]:
                            best[value] = best[value - coin] + 1
                return -1 if best[amount] == unreachable else best[amount]


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                k = data[0]
                amount = data[1]
                print(fewest_coins(data[2 : 2 + k], amount))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function fewestCoins(coins, amount) {
              const unreachable = amount + 1;
              const best = new Array(amount + 1).fill(unreachable);
              best[0] = 0;
              for (let value = 1; value <= amount; value += 1) {
                for (const coin of coins) {
                  if (coin <= value && best[value - coin] + 1 < best[value]) {
                    best[value] = best[value - coin] + 1;
                  }
                }
              }
              return best[amount] === unreachable ? -1 : best[amount];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const k = Number(data[0]);
              const amount = Number(data[1]);
              const coins = data.slice(2, 2 + k).map(Number);
              console.log(fewestCoins(coins, amount));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_coin_change, COIN_CHANGE_INPUT),
        judged_case(_coin_change, "1 0\n7"),
        judged_case(_coin_change, "2 0\n2 3"),
        judged_case(_coin_change, "2 3\n2"),
        judged_case(_coin_change, "2 5\n2 5", is_hidden=True),
        judged_case(_coin_change, "1 7\n2", is_hidden=True),
        judged_case(_coin_change, "3 27\n1 5 10", is_hidden=True),
    ],
}


SEARCHING_AND_DP_PROBLEMS: tuple[dict[str, Any], ...] = (
    BINARY_SEARCH,
    JUMP_GAME,
    MAXIMUM_SUBARRAY,
    COIN_CHANGE,
)
