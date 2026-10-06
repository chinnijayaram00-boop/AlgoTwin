"""Greedy: commit to a choice because the constraint structure forbids regret.

Three problems where the answer comes from taking the locally best available
action, and where the interesting part is proving the local choice is not merely
*plausible*.

* **Assign cookies** pairs the least demanding child with the smallest cookie
  that satisfies them. The proof is an exchange argument: any matching that
  gives a child a bigger cookie can be rearranged to give them this one instead
  without making anyone worse off, so the greedy pair survives inside some
  optimal answer.
* **Gas station** asks for a starting index, and the insight is that a prefix
  where the tank runs dry rules out every index inside it at once. Written as
  prefix sums, the whole problem becomes "which prefix sum is smallest".
* **Minimum refuelling stops** is where greedy needs a data structure rather
  than a comparison: at each moment the question is not "which station next" but
  "of the stations already passed, which is the best one to have used", and the
  answer is a max-heap over fuel amounts.

The through-line: a greedy algorithm is a claim that the problem's structure
admits an exchange argument. Where it does not, the same code shape is a trap,
which is why each of these problems states its structure tightly.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source, text_lines

# --------------------------------------------------------------------------- #
# Assign cookies
# --------------------------------------------------------------------------- #

COOKIES_INPUT = "2 3\n1 2\n1 2 3"


def _assign_cookies(stdin: str) -> str:
    """Match greedily but search for each cookie from scratch: O(g * s).

    Deliberately the slow version. The reference solutions use a single shared
    index, which is the whole point of the problem, so an oracle written a
    different way is worth more than a fast one.
    """
    values = int_tokens(stdin)
    g = values[0]
    s = values[1]
    greed = sorted(values[2 : 2 + g])
    cookies = sorted(values[2 + g : 2 + g + s])
    used = [False] * s
    satisfied = 0
    for want in greed:
        for index, size in enumerate(cookies):
            if not used[index] and size >= want:
                used[index] = True
                satisfied += 1
                break
    return str(satisfied)


COOKIES_BULK_GREED = [((index * 37) % 2000) + 1 for index in range(2000)]
COOKIES_BULK_SIZES = [((index * 53) % 1500) + 1 for index in range(2000)]
COOKIES_BULK_INPUT = (
    f"{len(COOKIES_BULK_GREED)} {len(COOKIES_BULK_SIZES)}\n"
    + " ".join(str(value) for value in COOKIES_BULK_GREED)
    + "\n"
    + " ".join(str(value) for value in COOKIES_BULK_SIZES)
)


ASSIGN_COOKIES: dict[str, Any] = {
    "slug": "assign-cookies",
    "title": "Assign Cookies",
    "summary": "Satisfy as many children as possible by pairing the easiest child with the smallest cookie that fits.",
    "difficulty": "Easy",
    "topics": ["Greedy", "Sorting", "Two Pointers"],
    "description": (
        "Each of the `g` children wants a cookie of at least `greed[i]` units, and "
        "each of the `s` cookies has a single size. One cookie satisfies at most "
        "one child, and one child takes at most one cookie.\n\n"
        "Return the largest number of children that can be satisfied. Both lists "
        "may be in any order and the values need not be distinct."
    ),
    "input_format": (
        "Line 1: `g s`.\n"
        "Line 2: `g` integers, the minimum size each child wants.\n"
        "Line 3: `s` integers, the cookie sizes."
    ),
    "output_format": "Print the maximum number of children that can be satisfied.",
    "constraints": (
        "0 <= g, s <= 2 * 10^4 and 1 <= greed[i], cookies[j] <= 10^9. An empty "
        "greed list or an empty cookie list has the answer 0."
    ),
    "examples": [
        {
            "input": COOKIES_INPUT,
            "output": _assign_cookies(COOKIES_INPUT),
            "explanation": "The child wanting 2 takes the size 2 cookie and the child wanting 1 takes the size 1 cookie, so both are satisfied.",
        },
        {
            "input": "2 2\n2 3\n1 1",
            "output": _assign_cookies("2 2\n2 3\n1 1"),
            "explanation": "Neither cookie is large enough for either child, so the answer is 0.",
        },
    ],
    "hints": [
        "Serving the child who wants the most whenever a big cookie appears is a trap: it can waste the only cookie that would have satisfied somebody else. Try the other end of the problem.",
        "Sort both lists. Now ask which pair is safe to commit to first. The least demanding child is the one nobody else competes for, because every other child needs a cookie at least as big.",
        "Give the least demanding child the *smallest* remaining cookie that satisfies them, then move on to the next child. Any cookie too small for this child is too small for every later child, so those cookies can be discarded for good instead of reconsidered.",
        "Keep one index into the sorted cookie list and only ever move it forward. Every cookie you step over was too small for the current child and therefore too small for all the rest, which is what makes the scan linear once the sorting is done.",
        "The argument that makes this correct is an exchange. Any optimal matching can be rearranged to contain the pair the greedy just chose without reducing how many children are satisfied, so taking it never costs anything.",
    ],
    "explanation": (
        "Sort both lists ascending, then walk them together with a single index "
        "into the cookies. For each child, in order of increasing greediness:\n\n"
        "* Skip cookies smaller than this child wants. They cannot satisfy this "
        "child, and they cannot satisfy any later child either, because later "
        "children want at least as much. Skipping is permanent.\n"
        "* If a cookie is still available, it fits: give it to this child and "
        "consume it.\n"
        "* If none is left, stop. Every remaining child wants at least as much as "
        "this one, so nothing further can be satisfied.\n\n"
        "The correctness argument is an exchange argument. Consider the least "
        "demanding unserved child `c` and the smallest remaining cookie `k` that "
        "satisfies them, and take an optimal matching. Three cases:\n\n"
        "1. `c` is satisfied there, by some cookie `k' >= k`. If `k` is unused, hand "
        "`k` to `c` and free `k'`. If `k` went to another child `d`, then `d` wanted "
        "at most `k <= k'`, so `d` accepts `k'` just as well. The count is unchanged.\n"
        "2. `c` is unsatisfied and `k` is unused. Giving `k` to `c` improves the "
        "matching, which cannot happen to an optimal one.\n"
        "3. `c` is unsatisfied and `k` is given to another child. Give `k` to `c` "
        "instead: same count, and the displaced child becomes unsatisfied.\n\n"
        "In every case an optimal matching exists that contains the greedy pair, "
        "so taking it never costs anything. Remove the pair and the argument "
        "repeats, which is induction over the children.\n\n"
        "After the sort each cookie is visited at most once, so the scan is "
        "O(g + s) and the two sorts dominate."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(g log g + s log s)",
    "expected_space_complexity": "O(g + s)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def assign_cookies(greed, cookies):
                \"\"\"Return the largest number of children that can be satisfied.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                g = data[0]
                s = data[1]
                print(assign_cookies(data[2 : 2 + g], data[2 + g : 2 + g + s]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function assignCookies(greed, cookies) {
              // Return the largest number of children that can be satisfied.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const g = data[0];
              const s = data[1];
              const greed = data.slice(2, 2 + g);
              const cookies = data.slice(2 + g, 2 + g + s);
              console.log(assignCookies(greed, cookies));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int assignCookies(int[] greed, int[] cookies) {
                    // Return the largest number of children that can be satisfied.
                    return 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int g = in.nextInt();
                    int s = in.nextInt();
                    int[] greed = new int[g];
                    for (int i = 0; i < g; i += 1) {
                        greed[i] = in.nextInt();
                    }
                    int[] cookies = new int[s];
                    for (int j = 0; j < s; j += 1) {
                        cookies[j] = in.nextInt();
                    }
                    System.out.println(assignCookies(greed, cookies));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def assign_cookies(greed, cookies):
                greed = sorted(greed)
                cookies = sorted(cookies)
                satisfied = 0
                cookie = 0
                for want in greed:
                    while cookie < len(cookies) and cookies[cookie] < want:
                        cookie += 1
                    if cookie == len(cookies):
                        break
                    satisfied += 1
                    cookie += 1
                return satisfied


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                g = data[0]
                s = data[1]
                print(assign_cookies(data[2 : 2 + g], data[2 + g : 2 + g + s]))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function assignCookies(greed, cookies) {
              const sortedGreed = [...greed].sort((left, right) => left - right);
              const sortedCookies = [...cookies].sort((left, right) => left - right);
              let satisfied = 0;
              let cookie = 0;
              for (const want of sortedGreed) {
                while (cookie < sortedCookies.length && sortedCookies[cookie] < want) {
                  cookie += 1;
                }
                if (cookie === sortedCookies.length) {
                  break;
                }
                satisfied += 1;
                cookie += 1;
              }
              return satisfied;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const g = data[0];
              const s = data[1];
              const greed = data.slice(2, 2 + g);
              const cookies = data.slice(2 + g, 2 + g + s);
              console.log(assignCookies(greed, cookies));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Arrays;
            import java.util.Scanner;

            public class Main {
                static int assignCookies(int[] greed, int[] cookies) {
                    int[] sortedGreed = greed.clone();
                    int[] sortedCookies = cookies.clone();
                    Arrays.sort(sortedGreed);
                    Arrays.sort(sortedCookies);
                    int satisfied = 0;
                    int cookie = 0;
                    for (int want : sortedGreed) {
                        while (cookie < sortedCookies.length && sortedCookies[cookie] < want) {
                            cookie += 1;
                        }
                        if (cookie == sortedCookies.length) {
                            break;
                        }
                        satisfied += 1;
                        cookie += 1;
                    }
                    return satisfied;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int g = in.nextInt();
                    int s = in.nextInt();
                    int[] greed = new int[g];
                    for (int i = 0; i < g; i += 1) {
                        greed[i] = in.nextInt();
                    }
                    int[] cookies = new int[s];
                    for (int j = 0; j < s; j += 1) {
                        cookies[j] = in.nextInt();
                    }
                    System.out.println(assignCookies(greed, cookies));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_assign_cookies, COOKIES_INPUT),
        judged_case(_assign_cookies, "2 2\n2 3\n1 1"),
        judged_case(_assign_cookies, "1 1\n5\n5"),
        judged_case(_assign_cookies, "3 3\n3 2 1\n1 1 1"),
        judged_case(_assign_cookies, "3 2\n1 2 3\n1 1", is_hidden=True),
        judged_case(_assign_cookies, "4 4\n4 3 2 1\n1 2 3 4", is_hidden=True),
        judged_case(_assign_cookies, "5 5\n10 20 30 40 50\n5 15 25 35 45", is_hidden=True),
        judged_case(_assign_cookies, "0 3\n\n1 2 3", is_hidden=True),
        judged_case(_assign_cookies, "3 0\n1 2 3\n", is_hidden=True),
        judged_case(_assign_cookies, COOKIES_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Gas station
# --------------------------------------------------------------------------- #

GAS_INPUT = "5\n1 2 3 4 5\n3 4 5 1 2"


def _gas_station(stdin: str) -> str:
    """Try every starting station and simulate the whole lap: O(n^2).

    Slow on purpose. The reference solution reads the array as prefix sums, and
    an oracle that shares no structure with it is what makes agreement mean
    something.
    """
    values = int_tokens(stdin)
    n = values[0]
    gas = values[1 : 1 + n]
    cost = values[1 + n : 1 + 2 * n]
    for start in range(n):
        tank = 0
        feasible = True
        for step in range(n):
            index = (start + step) % n
            tank += gas[index] - cost[index]
            if tank < 0:
                feasible = False
                break
        if feasible:
            return str(start)
    return "-1"


GAS_BULK_GAS = [((index * 61) % 4001) for index in range(1200)]
GAS_BULK_COST = [((index * 89) % 4001) for index in range(1200)]
GAS_BULK_INPUT = (
    f"{len(GAS_BULK_GAS)}\n"
    + " ".join(str(value) for value in GAS_BULK_GAS)
    + "\n"
    + " ".join(str(value) for value in GAS_BULK_COST)
)


GAS_STATION: dict[str, Any] = {
    "slug": "gas-station",
    "title": "Gas Station",
    "summary": "Find the smallest station index the lap can start from, using one pass over the net gains.",
    "difficulty": "Medium",
    "topics": ["Greedy", "Arrays", "Prefix Sums"],
    "description": (
        "There are `n` stations in a circle. Station `i` holds `gas[i]` units of "
        "fuel, and driving from station `i` to station `(i + 1) % n` consumes "
        "`cost[i]` units.\n\n"
        "Start at one station with an empty tank and drive all the way round, back "
        "to where you started, without the tank ever going below zero. Return the "
        "**smallest** such index, or `-1` when no lap is possible."
    ),
    "input_format": (
        "Line 1: `n`.\n"
        "Line 2: `n` integers, the fuel available at each station.\n"
        "Line 3: `n` integers, the fuel needed to reach the next station."
    ),
    "output_format": "Print the smallest index a valid lap can start from, or `-1` when there is none.",
    "constraints": (
        "1 <= n <= 2 * 10^4 and 0 <= gas[i], cost[i] <= 10^4. Several indices may "
        "be valid, and the smallest of them is what must be printed."
    ),
    "examples": [
        {
            "input": GAS_INPUT,
            "output": _gas_station(GAS_INPUT),
            "explanation": "The net gains are -2, -2, -2, +3, +3, so the running sum is 0, -2, -4, -6, -3, 0. Its smallest value is -6, reached just before index 3, so index 3 is the first start that survives.",
        },
        {
            "input": "4\n1 2 3 4\n4 3 2 1",
            "output": _gas_station("4\n1 2 3 4\n4 3 2 1"),
            "explanation": "The gains are -3, -1, +1, +3, so the running sum is 0, -3, -4, -3, 0 and is smallest just before index 2. From there the tank reads 1, 4, 1, 0, never negative.",
        },
    ],
    "hints": [
        "Brute force works and is worth writing once: for each start, simulate the lap. That is O(n^2), and its output is what the fast version has to reproduce.",
        "Total fuel of at least total cost is necessary but not sufficient, because the fuel might all sit at the wrong end of the circle. Rule the impossible case out with the total first, then worry about ordering.",
        "Turn the question into one about prefix sums. `P[k]` is the net fuel after driving from station 0 through station `k - 1`. Starting at `s` fails exactly when some later prefix sum dips below `P[s]`.",
        "So the answer is the index whose prefix sum is the smallest of them all, and you want the *first* occurrence: an earlier start would have had to survive the very dip that defines the minimum.",
        "Careful with the index arithmetic. `P[s]` is the fuel *before* refuelling at station `s`, so the start is one position after the prefix sum that was smallest, and `P[0] = 0` has to be in the comparison."
    ],
    "explanation": (
        "Let `delta[i] = gas[i] - cost[i]`, the net fuel gained by driving out of "
        "station `i`, and let `P[k] = delta[0] + ... + delta[k - 1]` with `P[0] = "
        "0`. Driving from station `s` reaches station `j` with exactly `P[j] - P[s]` "
        "units of fuel, so:\n\n"
        "* the lap from `s` is feasible when the total `P[n]` is at least `P[s]`, "
        "because that is the fuel left on returning to `s`;\n"
        "* and it is feasible only when no later prefix sum is smaller than `P[s]`, "
        "because every prefix in between is a point where the tank must not be "
        "negative.\n\n"
        "The second condition says `P[s]` is a minimum of the whole prefix sequence. "
        "That is only possible when `P[n] >= P[s]`, so if `P[n] < 0` no lap exists "
        "and the answer is `-1`. If `P[n] >= 0`, `P[0] = 0` guarantees the minimum "
        "exists at some index in `0..n`, and the answer is the index just after the "
        "*first* occurrence of that minimum.\n\n"
        "First, because the problem asks for the smallest valid index: any `t` "
        "before the first minimum has `P[t] > P[s]`, and since `s > t`, "
        "`P[s] < P[t]`, so some later prefix sum is smaller than `P[t]` and `t` "
        "fails. So no earlier index is valid.\n\n"
        "Second, that `s` itself works. Choose the first occurrence, so `P[s] <= "
        "P[t]` for every `t`, giving no dip anywhere in the array; and `P[n] >= 0 "
        ">= P[s]` because `P[s] <= P[0] = 0`, giving a non-negative return to the "
        "start.\n\n"
        "Both facts come from one pass that keeps the running total and the "
        "smallest prefix sum seen so far together with the index where it occurred, "
        "which is O(n) time and O(1) extra space. No tank needs to be simulated."
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


            def gas_station(gas, cost):
                \"\"\"Return the smallest valid starting index, or -1 when there is none.\"\"\"
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                gas = data[1 : 1 + n]
                cost = data[1 + n : 1 + 2 * n]
                print(gas_station(gas, cost))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function gasStation(gas, cost) {
              // Return the smallest valid starting index, or -1 when there is none.
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const n = data[0];
              const gas = data.slice(1, 1 + n);
              const cost = data.slice(1 + n, 1 + 2 * n);
              console.log(gasStation(gas, cost));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int gasStation(int[] gas, int[] cost) {
                    // Return the smallest valid starting index, or -1 when there is none.
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] gas = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        gas[i] = in.nextInt();
                    }
                    int[] cost = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        cost[i] = in.nextInt();
                    }
                    System.out.println(gasStation(gas, cost));
                }
            }
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def gas_station(gas, cost):
                total = 0
                lowest = 0
                lowest_at = 0
                for index in range(len(gas)):
                    total += gas[index] - cost[index]
                    if total < lowest:
                        lowest = total
                        lowest_at = index + 1
                if total < 0:
                    return -1
                return lowest_at


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                gas = data[1 : 1 + n]
                cost = data[1 + n : 1 + 2 * n]
                print(gas_station(gas, cost))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function gasStation(gas, cost) {
              let total = 0;
              let lowest = 0;
              let lowestAt = 0;
              for (let index = 0; index < gas.length; index += 1) {
                total += gas[index] - cost[index];
                if (total < lowest) {
                  lowest = total;
                  lowestAt = index + 1;
                }
              }
              if (total < 0) {
                return -1;
              }
              return lowestAt;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const n = data[0];
              const gas = data.slice(1, 1 + n);
              const cost = data.slice(1 + n, 1 + 2 * n);
              console.log(gasStation(gas, cost));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int gasStation(int[] gas, int[] cost) {
                    long total = 0;
                    long lowest = 0;
                    int lowestAt = 0;
                    for (int index = 0; index < gas.length; index += 1) {
                        total += gas[index] - cost[index];
                        if (total < lowest) {
                            lowest = total;
                            lowestAt = index + 1;
                        }
                    }
                    if (total < 0) {
                        return -1;
                    }
                    return lowestAt;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] gas = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        gas[i] = in.nextInt();
                    }
                    int[] cost = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        cost[i] = in.nextInt();
                    }
                    System.out.println(gasStation(gas, cost));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_gas_station, GAS_INPUT),
        judged_case(_gas_station, "4\n1 2 3 4\n4 3 2 1"),
        judged_case(_gas_station, "1\n5\n4"),
        judged_case(_gas_station, "3\n2 3 4\n3 4 3"),
        judged_case(_gas_station, "5\n4 1 2 3 3\n2 2 3 1 2", is_hidden=True),
        judged_case(_gas_station, "4\n3 3 1 1\n1 2 2 3", is_hidden=True),
        judged_case(_gas_station, "2\n5 5\n4 4", is_hidden=True),
        judged_case(_gas_station, "6\n2 3 4 5 6 1\n1 2 3 4 5 6", is_hidden=True),
        judged_case(_gas_station, GAS_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Minimum refuelling stops
# --------------------------------------------------------------------------- #

REFUEL_INPUT = "10 25 2\n10 10\n20 5"


def _min_refuel(stdin: str) -> str:
    """Level-by-level reach: how far can k stops get us? O(n * stops).

    A different shape from the reference's max-heap, and independent of it: this
    one never simulates a tank, it just keeps the furthest point reachable with
    each number of stops.
    """
    lines = text_lines(stdin)
    head = [int(token) for token in lines[0].split()]
    fuel = head[0]
    distance = head[1]
    n = head[2]
    stations = sorted(
        (int(line.split()[0]), int(line.split()[1])) for line in lines[1 : 1 + n]
    )
    reach = [fuel]
    for position, amount in stations:
        if position > reach[-1]:
            break
        for stops in range(len(reach) - 1, -1, -1):
            if reach[stops] >= position:
                candidate = reach[stops] + amount
                if stops + 1 == len(reach):
                    reach.append(candidate)
                elif candidate > reach[stops + 1]:
                    reach[stops + 1] = candidate
    for stops, covered in enumerate(reach):
        if covered >= distance:
            return str(stops)
    return "-1"


REFUEL_BULK_CAPACITY = 1000
REFUEL_BULK_DISTANCE = 100_000
REFUEL_BULK_STATIONS = [
    ((index * 1543) % REFUEL_BULK_DISTANCE, ((index * 3571) % 4000) + 1000)
    for index in range(500)
]
REFUEL_BULK_INPUT = (
    f"{REFUEL_BULK_CAPACITY} {REFUEL_BULK_DISTANCE} {len(REFUEL_BULK_STATIONS)}\n"
    + "\n".join(f"{position} {amount}" for position, amount in REFUEL_BULK_STATIONS)
)


MINIMUM_REFUELING_STOPS: dict[str, Any] = {
    "slug": "minimum-refueling-stops",
    "title": "Minimum Refuelling Stops",
    "summary": "Buy from the richest station already passed, keeping the candidates in a max-heap.",
    "difficulty": "Hard",
    "topics": ["Greedy", "Heap", "Sorting"],
    "description": (
        "A car starts at position 0 holding `fuel` units of fuel and burns one unit "
        "per unit of distance. It must reach position `distance`. There are `n` fuel "
        "stations; station `i` sits at `position[i]` and refuelling there adds "
        "`amount[i]` units of fuel to the tank.\n\n"
        "Return the minimum number of refuelling stops needed, or `-1` when the "
        "destination cannot be reached. The tank holds as much as you like, a "
        "station may be used at most once, and you can only refuel at a station "
        "once you have arrived there."
    ),
    "input_format": (
        "Line 1: `fuel distance n`.\n"
        "Lines 2 to n + 1: `position amount`, one station each. Any order."
    ),
    "output_format": "Print the minimum number of refuelling stops, or `-1` if the destination is unreachable.",
    "constraints": (
        "1 <= n <= 2 * 10^4, 1 <= fuel <= 10^5, 1 <= distance <= 10^5, "
        "0 <= position[i] <= distance and 1 <= amount[i] <= 10^5. Stations may share "
        "a position and may be listed in any order."
    ),
    "examples": [
        {
            "input": REFUEL_INPUT,
            "output": _min_refuel(REFUEL_INPUT),
            "explanation": "The tank reaches position 10, then refuelling there adds 10 to reach 20, and refuelling at 20 adds 5 to reach 25: two stops.",
        },
        {
            "input": "5 5 1\n1 5",
            "output": _min_refuel("5 5 1\n1 5"),
            "explanation": "The fuel already on board reaches the destination, so no station is used and the answer is 0.",
        },
    ],
    "hints": [
        "Choosing a station before you know you need one is the trap. A stop cannot be undone, so a choice made early is a choice made without the information that would justify it.",
        "Sort the stations by position and drive forward. At any moment every station you have already passed but not yet used is a candidate, and none of them can become better later: later you could only have reached further ones.",
        "Keep the passed-but-unused stations in a max-heap by amount. When the fuel runs out, using the station with the most fuel is never worse than any other: both cost exactly one stop, and the richer one leaves you further along.",
        "The reach test is `position[i] <= furthest`, where `furthest` is how far the fuel bought so far takes you. Push every station that becomes reachable and pop the largest only when the fuel is actually needed, never before.",
        "The count is the number of pops, and `-1` is the moment the fuel runs dry with an empty heap: no station you could have used remains, so no ordering of stops would have saved the trip."
    ],
    "explanation": (
        "The greedy idea is to postpone the decision. Refuelling early can only "
        "waste stops, because a station you have not reached yet might be richer. So "
        "the algorithm never commits until the fuel has actually run out, and then "
        "it commits to the richest station it has already passed.\n\n"
        "That second half needs an exchange argument. Suppose the fuel runs out and "
        "the algorithm picks the richest passed station `S`. Take any plan for the "
        "rest of the trip:\n\n"
        "1. If it uses `S`, there is nothing to prove.\n"
        "2. If it does not, let `T` be the first station it does use. `T` was passed "
        "too, so `S` was reachable, and `amount[S] >= amount[T]` because `S` was the "
        "largest available. Refuelling at `S` instead of `T` gives at least as much "
        "fuel for the same one stop, so every later station that plan used is still "
        "reachable and the plan is no worse.\n\n"
        "So an optimal plan exists that agrees with the greedy choice, and the "
        "argument repeats for each pop.\n\n"
        "The implementation keeps a pointer into the sorted stations and a max-heap "
        "of the amounts of the stations already passed. Each iteration adds every "
        "station the current fuel reaches and, if the destination is still out of "
        "reach, pops the largest amount and adds it. Every station is pushed once "
        "and popped at most once, so the cost is O(n log n) after the sort and the "
        "heap holds O(n) amounts.\n\n"
        "The trip needs no stops when the initial fuel already covers the distance, "
        "and it is impossible rather than merely expensive when the fuel runs out "
        "with an empty heap."
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


            def min_refueling_stops(fuel, distance, stations):
                \"\"\"Return the minimum number of refuelling stops, or -1.\"\"\"
                return -1


            def main():
                lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
                head = [int(token) for token in lines[0].split()]
                fuel, distance, n = head[0], head[1], head[2]
                stations = []
                for line in lines[1 : 1 + n]:
                    position, amount = (int(token) for token in line.split())
                    stations.append((position, amount))
                print(min_refueling_stops(fuel, distance, stations))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function minRefuelingStops(fuel, distance, stations) {
              // Return the minimum number of refuelling stops, or -1.
              return -1;
            }

            function main() {
              const lines = fs
                .readFileSync(0, "utf8")
                .split(/\\r?\\n/)
                .filter((line) => line.trim().length > 0)
                .map((line) => line.trim().split(/\\s+/).map(Number));
              const [fuel, distance, n] = lines[0];
              const stations = lines
                .slice(1, 1 + n)
                .map(([position, amount]) => ({ position, amount }));
              console.log(minRefuelingStops(fuel, distance, stations));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int minRefuelingStops(int fuel, int distance, int[][] stations) {
                    // Return the minimum number of refuelling stops, or -1.
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int fuel = in.nextInt();
                    int distance = in.nextInt();
                    int n = in.nextInt();
                    int[][] stations = new int[n][2];
                    for (int i = 0; i < n; i += 1) {
                        stations[i][0] = in.nextInt();
                        stations[i][1] = in.nextInt();
                    }
                    System.out.println(minRefuelingStops(fuel, distance, stations));
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


            def min_refueling_stops(fuel, distance, stations):
                stations = sorted(stations)
                available = []
                furthest = fuel
                stops = 0
                index = 0
                while furthest < distance:
                    while index < len(stations) and stations[index][0] <= furthest:
                        heapq.heappush(available, -stations[index][1])
                        index += 1
                    if not available:
                        return -1
                    furthest -= heapq.heappop(available)
                    stops += 1
                return stops


            def main():
                lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
                head = [int(token) for token in lines[0].split()]
                fuel, distance, n = head[0], head[1], head[2]
                stations = []
                for line in lines[1 : 1 + n]:
                    position, amount = (int(token) for token in line.split())
                    stations.append((position, amount))
                print(min_refueling_stops(fuel, distance, stations))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function minRefuelingStops(fuel, distance, stations) {
              const sorted = [...stations].sort((left, right) => left.position - right.position);
              const available = [];
              let furthest = fuel;
              let stops = 0;
              let index = 0;
              while (furthest < distance) {
                while (index < sorted.length && sorted[index].position <= furthest) {
                  available.push(sorted[index].amount);
                  index += 1;
                }
                if (available.length === 0) {
                  return -1;
                }
                let best = 0;
                for (let scan = 1; scan < available.length; scan += 1) {
                  if (available[scan] > available[best]) {
                    best = scan;
                  }
                }
                furthest += available.splice(best, 1)[0];
                stops += 1;
              }
              return stops;
            }

            function main() {
              const lines = fs
                .readFileSync(0, "utf8")
                .split(/\\r?\\n/)
                .filter((line) => line.trim().length > 0)
                .map((line) => line.trim().split(/\\s+/).map(Number));
              const [fuel, distance, n] = lines[0];
              const stations = lines
                .slice(1, 1 + n)
                .map(([position, amount]) => ({ position, amount }));
              console.log(minRefuelingStops(fuel, distance, stations));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Arrays;
            import java.util.Comparator;
            import java.util.PriorityQueue;
            import java.util.Scanner;

            public class Main {
                static int minRefuelingStops(int fuel, int distance, int[][] stations) {
                    int[][] sorted = stations.clone();
                    Arrays.sort(sorted, Comparator.comparingInt((int[] station) -> station[0]));
                    PriorityQueue<Integer> available = new PriorityQueue<>(Comparator.reverseOrder());
                    int furthest = fuel;
                    int stops = 0;
                    int index = 0;
                    while (furthest < distance) {
                        while (index < sorted.length && sorted[index][0] <= furthest) {
                            available.add(sorted[index][1]);
                            index += 1;
                        }
                        if (available.isEmpty()) {
                            return -1;
                        }
                        furthest += available.poll();
                        stops += 1;
                    }
                    return stops;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int fuel = in.nextInt();
                    int distance = in.nextInt();
                    int n = in.nextInt();
                    int[][] stations = new int[n][2];
                    for (int i = 0; i < n; i += 1) {
                        stations[i][0] = in.nextInt();
                        stations[i][1] = in.nextInt();
                    }
                    System.out.println(minRefuelingStops(fuel, distance, stations));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_min_refuel, REFUEL_INPUT),
        judged_case(_min_refuel, "5 5 1\n1 5"),
        judged_case(_min_refuel, "4 4 2\n2 2\n3 3"),
        judged_case(_min_refuel, "5 5 1\n1 9"),
        judged_case(_min_refuel, "10 10 3\n1 3\n5 2\n9 1", is_hidden=True),
        judged_case(_min_refuel, "3 10 2\n2 4\n5 2", is_hidden=True),
        judged_case(_min_refuel, "6 6 3\n1 5\n3 4\n5 3", is_hidden=True),
        judged_case(_min_refuel, "5 20 2\n4 1\n9 1", is_hidden=True),
        judged_case(_min_refuel, REFUEL_BULK_INPUT, is_hidden=True),
    ],
}


GREEDY_PROBLEMS: tuple[dict[str, Any], ...] = (
    ASSIGN_COOKIES,
    GAS_STATION,
    MINIMUM_REFUELING_STOPS,
)
