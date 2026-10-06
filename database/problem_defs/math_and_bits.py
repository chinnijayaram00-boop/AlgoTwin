"""Math and bits: arithmetic identities, and the machine underneath the syntax.

Three problems that look like numeric computation and are really about
representation:

* **Reverse bits** is a thirty-two-iteration loop that is correct in one language
  and silently wrong in the other two, because only Python's shift is defined for
  negative numbers. `x >> 1` and `x >>> 1` are the same operation in Java on
  non-negative input and completely different operations once the sign bit is
  set, and in JavaScript the sign bit is set constantly.
* **Count set bits** is where the interesting identity lives: clearing the lowest
  set bit with `x & (x - 1)` turns a popcount into a loop whose trip count is the
  answer, rather than one iteration per bit.
* **Power of four** needs a number to be a power of two *and* to have its single
  bit at an even position, and the cheapest way to express "even position" is a
  mask -- which is why the problem exists.

The shared theme is that a value's *bits* are a different thing from its
magnitude, and languages disagree about how to spell the difference. Every one of
these problems is solvable by division and multiplication, and every one of them
has a solution where those are replaced by arithmetic on the representation.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source

# --------------------------------------------------------------------------- #
# Reverse the bits of a 32-bit unsigned integer
# --------------------------------------------------------------------------- #

REVERSE_BITS_INPUT = "4\n1 12 0 255"


def _reverse_bits(stdin: str) -> str:
    """Reverse by rewriting the bit string, which cannot be done by accident.

    The references walk 32 bits with a shift, so this is a genuinely different
    route to the same number: format it, turn the string around, read it back.
    """
    values = int_tokens(stdin)
    m = values[0]
    answers = []
    for n in values[1 : 1 + m]:
        answers.append(str(int(format(n, "032b")[::-1], 2)))
    return "\n".join(answers)


REVERSE_BITS_BULK = [((index * 2654435761) % 2147483648) for index in range(8000)]
REVERSE_BITS_BULK_INPUT = f"{len(REVERSE_BITS_BULK)}\n" + " ".join(
    str(value) for value in REVERSE_BITS_BULK
)


REVERSE_BITS: dict[str, Any] = {
    "slug": "reverse-bits",
    "title": "Reverse the Bits of a 32-bit Unsigned Integer",
    "summary": "Walk 32 bits and rebuild the number from the other end, using unsigned shifts.",
    "difficulty": "Easy",
    "topics": ["Bit Manipulation", "Math", "Number Theory"],
    "description": (
        "Reverse the bits of each given 32-bit unsigned integer.\n\n"
        "Bit 0 is the least significant bit and bit 31 is the most significant one. "
        "The result is read back as an unsigned 32-bit value, so a number with its "
        "top bit set reverses to a number greater than 2^31 - 1.\n\n"
        "Several numbers are given on one input, and each is independent of the "
        "others."
    ),
    "input_format": (
        "Line 1: `m`, the number of values.\n"
        "Line 2: `m` integers, each in the range 0 to 2^32 - 1."
    ),
    "output_format": "Print `m` lines, each the bit-reversed value, in the range 0 to 2^32 - 1.",
    "constraints": (
        "1 <= m <= 10^4 and 0 <= n <= 2^32 - 1. The reversal is over all 32 bits, so "
        "leading zeros of the input are not stripped: `1` reverses to 2147483648."
    ),
    "examples": [
        {
            "input": REVERSE_BITS_INPUT,
            "output": _reverse_bits(REVERSE_BITS_INPUT),
            "explanation": "1 is 00000000000000000000000000000001, so reversing it puts that single bit at position 31 and the answer is 2147483648. 12 is ...00001100, so it reverses to 00001100000000000000000000000000, which is 805306368.",
        },
        {
            "input": "3\n0 255 2147483647",
            "output": _reverse_bits("3\n0 255 2147483647"),
            "explanation": "0 is all zeros so it stays 0. 255 is 00000000000000000000000011111111 and reverses to 4278190080. 2147483647 has every bit set, so it reverses to itself.",
        },
    ],
    "hints": [
        "There are always exactly 32 bits to process, even for small numbers, and that fixed count is the whole trick: padding the input with leading zeros is what makes `1` come out as 2147483648 rather than 1.",
        "A shift takes the value apart from one end and puts it back together from the other. Take the lowest bit, shift the answer left by one to make room, and put that bit in.",
        "Extract the lowest bit with `n & 1`, and move `n` towards its high end by one position per iteration. Do all 32 iterations no matter how small `n` is.",
        "The languages disagree here, and this is the part that catches people. In JavaScript and Java a *signed* right shift fills with the sign bit, so once bit 31 is set it manufactures extra ones. Use the unsigned shift, written `>>>` in both languages.",
        "The answer can exceed 2^31 - 1, so it must be held in something with 33 bits or more. Python's integers and Java's `long` are fine; in JavaScript use the unsigned right shift `>>> 0` to read the low 32 bits back as an unsigned number, because a JavaScript `Number` cannot describe 4294967295 safely in the first place.",
    ],
    "explanation": (
        "Reversal is a fold over the bits from the least significant end. Read one "
        "bit, append it to the answer being built, repeat 32 times.\n\n"
        "Two operations do all the work. `n & 1` extracts the current lowest bit: "
        "the mask has a single 1 at position 0, so the result is that bit alone. "
        "Shifting the answer left by one moves everything already built up one "
        "position, making room, and the `|` then drops the new bit into the vacated "
        "lowest position. Because the answer shifts left on every iteration, the "
        "first bit read ends up in position 31 and the last bit read ends up in "
        "position 0, which is exactly the reversal.\n\n"
        "The loop must run exactly 32 times. Running it only while `n != 0` "
        "reverses only the significant bits and quietly produces 1 for the input "
        "1 instead of 2147483648. Fixed-width reversal is the requirement, so the "
        "iteration count is a constant, not a property of the input.\n\n"
        "The second half of the problem is representation. JavaScript's bitwise "
        "operators and Java's `int` both operate on 32 bits interpreted as signed, "
        "so a value with bit 31 set is *negative*, and a signed right shift would "
        "replicate the sign bit down to the bottom, adding bits that were never in "
        "the number. The unsigned shift `>>>` copies in zeros instead, which is the "
        "correct behaviour, so `n >>>= 1` is required in both languages. "
        "Python's `>>` already replicates nothing for a non-negative input, so the "
        "ordinary shift is right there.\n\n"
        "The accumulated answer has bits in positions 0 to 31 set, which is one bit "
        "more than a signed 32-bit integer can hold. Java's `long` and Python's "
        "arbitrary-precision integers store it directly. JavaScript cannot: `result` "
        "is stored as a signed 32-bit pattern, so it is read back with `>>> 0` to "
        "convert it to the unsigned number of the same bit pattern."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(32) per value",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def reverse_bits(n):
                \"\"\"Return n with all 32 of its bits in the opposite order.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                m = data[0]
                for answer in (reverse_bits(n) for n in data[1 : 1 + m]):
                    print(answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function reverseBits(n) {
              // Return n with all 32 of its bits in the opposite order.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const m = data[0];
              for (const n of data.slice(1, 1 + m)) {
                console.log(reverseBits(n));
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static long reverseBits(long n) {
                    // Return n with all 32 of its bits in the opposite order.
                    return 0L;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int m = in.nextInt();
                    for (int i = 0; i < m; i++) {
                        System.out.println(reverseBits(in.nextLong()));
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


            def reverse_bits(n):
                result = 0
                for _ in range(32):
                    result = (result << 1) | (n & 1)
                    n >>= 1
                return result


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                m = data[0]
                for n in data[1 : 1 + m]:
                    print(reverse_bits(n))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function reverseBits(n) {
              let value = n >>> 0;
              let result = 0;
              for (let bit = 0; bit < 32; bit += 1) {
                result = ((result << 1) | (value & 1)) >>> 0;
                value = value >>> 1;
              }
              return result >>> 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const m = data[0];
              for (const n of data.slice(1, 1 + m)) {
                console.log(reverseBits(n));
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static long reverseBits(long n) {
                    long result = 0L;
                    for (int bit = 0; bit < 32; bit++) {
                        result = (result << 1) | (n & 1L);
                        n >>>= 1;
                    }
                    return result;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int m = in.nextInt();
                    for (int i = 0; i < m; i++) {
                        System.out.println(reverseBits(in.nextLong()));
                    }
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_reverse_bits, REVERSE_BITS_INPUT),
        judged_case(_reverse_bits, "3\n0 255 2147483647"),
        judged_case(_reverse_bits, "2\n1 2"),
        judged_case(_reverse_bits, "1\n4294967295"),
        judged_case(_reverse_bits, "5\n1024 65536 2147483648 1073741824 536870912", is_hidden=True),
        judged_case(_reverse_bits, "6\n1 1 1 1 1 1", is_hidden=True),
        judged_case(_reverse_bits, "4\n3 5 10 15", is_hidden=True),
        judged_case(_reverse_bits, "8\n16909060 252645135 117901063 1437226410 32768 999 123456789 2147483646", is_hidden=True),
        judged_case(_reverse_bits, REVERSE_BITS_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Count the set bits of a number
# --------------------------------------------------------------------------- #

COUNT_SET_BITS_INPUT = "6\n0 1 7 8 255 4294967295"


def _count_set_bits(stdin: str) -> str:
    """Ask the interpreter for the popcount of each value.

    The references clear the lowest set bit one at a time, so a single built-in
    call that answers the same question is a completely separate derivation of
    the same number.
    """
    values = int_tokens(stdin)
    m = values[0]
    answers = []
    for n in values[1 : 1 + m]:
        answers.append(str(n.bit_count()))
    return "\n".join(answers)


COUNT_SET_BITS_BULK = [((index * 40503) % 4294967296) for index in range(20000)]
COUNT_SET_BITS_BULK_INPUT = f"{len(COUNT_SET_BITS_BULK)}\n" + " ".join(
    str(value) for value in COUNT_SET_BITS_BULK
)


COUNT_SET_BITS: dict[str, Any] = {
    "slug": "count-set-bits",
    "title": "Count the Set Bits of an Unsigned Integer",
    "summary": "Clear the lowest set bit repeatedly and count how many times it took.",
    "difficulty": "Medium",
    "topics": ["Bit Manipulation", "Math", "Number Theory"],
    "description": (
        "For each given non-negative 32-bit integer, count how many of its bits are "
        "set to 1.\n\n"
        "A set bit is a digit 1 in the number's binary representation. For example "
        "`13` is `1101` in binary and has three set bits.\n\n"
        "Several numbers are given on one input, and each is independent of the "
        "others."
    ),
    "input_format": (
        "Line 1: `m`, the number of values.\n"
        "Line 2: `m` integers, each in the range 0 to 2^32 - 1."
    ),
    "output_format": "Print `m` lines, each the number of set bits in that value, in the range 0 to 32.",
    "constraints": (
        "1 <= m <= 2 * 10^4 and 0 <= n <= 2^32 - 1. The value 0 has no set bits and "
        "the value 2^32 - 1 has all 32 of them."
    ),
    "examples": [
        {
            "input": COUNT_SET_BITS_INPUT,
            "output": _count_set_bits(COUNT_SET_BITS_INPUT),
            "explanation": "0 has none, 1 has one, 7 is 111 so three, 8 is 1000 so one, 255 is eight ones, and 4294967295 is thirty-two ones.",
        },
        {
            "input": "4\n2 4 1023 65535",
            "output": _count_set_bits("4\n2 4 1023 65535"),
            "explanation": "Every number that is 2^k minus one has all k of its low bits set, which is why 1023 gives 10 and 65535 gives 16.",
        },
    ],
    "hints": [
        "A naive loop that inspects all 32 bit positions does the work, so the question is what would make it better. The answer is to stop looking at positions that are not interesting, and the identity that does that is `x & (x - 1)`.",
        "Subtracting one from a number that is not zero flips its lowest set bit to 0 and every bit below it to 1. Masking with the original then keeps only the bits that were set in both, so exactly one set bit disappears and no new one appears.",
        "So `x & (x - 1)` clears the lowest set bit and leaves every other bit alone. Repeating it drives the number to 0 in exactly as many steps as there are set bits, which means the trip count of that loop is the answer.",
        "The same trap as reversing bits applies here. Subtracting from and masking values above 2^31 - 1 happens in JavaScript and in Java `int` arithmetic, and `x - 1` can come out negative, so keep the value in a `long` or use `>>> 0` in JavaScript before masking.",
        "Python has an even shorter answer available -- `bin(n).count('1')` -- which is a fine thing to write and worth knowing, but it is the *identity* that makes the constant-time-per-set-bit loop worth deriving.",
    ],
    "explanation": (
        "The direct approach is a 32-iteration loop testing each position with a "
        "shift. It is always correct, but its cost is 32 regardless of the input, "
        "including for `n = 0`.\n\n"
        "The identity that improves on it is this: for any `x` that is not zero, "
        "`x & (x - 1)` has exactly one fewer set bit than `x`, and its other set "
        "bits are unchanged. To see it, write `x` as a run of zeros, then a 1, then "
        "arbitrary bits: `... 0 1 bbb`. Subtracting one gives `... 0 0 (bbb - 1)`, "
        "which borrows from that lowest 1, clears it, and turns every bit below it "
        "into 1. Masking with the original `x` keeps only the bits set in both, and "
        "the bits below the cleared one were zero in `x` all along, so they do not "
        "survive the mask. The net effect is that precisely the lowest set bit is "
        "cleared.\n\n"
        "Applying the identity in a loop until the number reaches 0 therefore "
        "iterates once per set bit. For `n = 0` the loop body never runs, and 0 set "
        "bits is exactly the right answer, so no special case is needed. The number "
        "of iterations is at most 32 and at least 0, so the work is bounded by the "
        "answer rather than by the width of the type.\n\n"
        "The language detail matters as much as the identity. In JavaScript every "
        "bitwise operator coerces its operands to *signed* 32-bit integers, so a "
        "value of 4294967295 becomes -1 before `x - 1` is even evaluated, and "
        "`x - 1` on a large value wraps around. Writing `let v = n >>> 0` first "
        "restores the intended unsigned bit pattern and makes the subtraction behave. "
        "In Java the same problem appears if the parameter is an `int`; declaring it "
        "`long` leaves the arithmetic exact.\n\n"
        "Python needs neither precaution, since its integers are arbitrary-precision "
        "and its shifts are defined for non-negative values."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(number of set bits), at most 32 per value",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def count_set_bits(n):
                \"\"\"Return how many bits of n are 1.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                m = data[0]
                for n in data[1 : 1 + m]:
                    print(count_set_bits(n))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countSetBits(n) {
              // Return how many bits of n are 1.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const m = data[0];
              for (const n of data.slice(1, 1 + m)) {
                console.log(countSetBits(n));
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int countSetBits(long n) {
                    // Return how many bits of n are 1.
                    return 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int m = in.nextInt();
                    for (int i = 0; i < m; i++) {
                        System.out.println(countSetBits(in.nextLong()));
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


            def count_set_bits(n):
                count = 0
                while n:
                    n &= n - 1
                    count += 1
                return count


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                m = data[0]
                for n in data[1 : 1 + m]:
                    print(count_set_bits(n))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countSetBits(n) {
              let value = n >>> 0;
              let count = 0;
              while (value !== 0) {
                value = value & (value - 1);
                count += 1;
              }
              return count;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const m = data[0];
              for (const n of data.slice(1, 1 + m)) {
                console.log(countSetBits(n));
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int countSetBits(long n) {
                    int count = 0;
                    while (n != 0L) {
                        n &= n - 1L;
                        count++;
                    }
                    return count;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int m = in.nextInt();
                    for (int i = 0; i < m; i++) {
                        System.out.println(countSetBits(in.nextLong()));
                    }
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_count_set_bits, COUNT_SET_BITS_INPUT),
        judged_case(_count_set_bits, "4\n2 4 1023 65535"),
        judged_case(_count_set_bits, "1\n0"),
        judged_case(_count_set_bits, "2\n4294967295 2147483648"),
        judged_case(_count_set_bits, "5\n1 2147483648 2147483647 4294967294 1431655765", is_hidden=True),
        judged_case(_count_set_bits, "4\n4278190080 4294901760 2147483649 4294967295", is_hidden=True),
        judged_case(_count_set_bits, "6\n999999999 1000000000 2000000000 3000000001 123456789 987654321", is_hidden=True),
        judged_case(_count_set_bits, COUNT_SET_BITS_BULK_INPUT, is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Power of four
# --------------------------------------------------------------------------- #

POWER_OF_FOUR_INPUT = "8\n1 4 16 2 8 0 64 3"


def _power_of_four(stdin: str) -> str:
    """Divide by four until it stops dividing, then check what is left is 1.

    The references test two bit masks instead, so the arithmetic version is a
    separate derivation of the same predicate.
    """
    values = int_tokens(stdin)
    m = values[0]
    answers = []
    for n in values[1 : 1 + m]:
        if n <= 0:
            answers.append("0")
            continue
        while n % 4 == 0:
            n //= 4
        answers.append("1" if n == 1 else "0")
    return "\n".join(answers)


POWER_OF_FOUR_BULK = [((index * 7919) % 2147483648) for index in range(20000)]
POWER_OF_FOUR_BULK_INPUT = f"{len(POWER_OF_FOUR_BULK)}\n" + " ".join(
    str(value) for value in POWER_OF_FOUR_BULK
)


POWER_OF_FOUR: dict[str, Any] = {
    "slug": "power-of-four",
    "title": "Power of Four",
    "summary": "A power of two whose only bit sits at an even position, decided with one mask.",
    "difficulty": "Medium",
    "topics": ["Bit Manipulation", "Math", "Number Theory"],
    "description": (
        "Decide, for each given integer, whether it is a power of four: that is, "
        "whether it equals 4^k for some integer k >= 0.\n\n"
        "The value 1 counts, because 4^0 is 1. Zero does not count, and neither does "
        "a negative number. Every other non-power is reported as 0.\n\n"
        "Several values are given on one input, and each is independent of the "
        "others."
    ),
    "input_format": (
        "Line 1: `m`, the number of values.\n"
        "Line 2: `m` integers, each in the range -10^9 to 10^9."
    ),
    "output_format": "Print `m` lines, each 1 if the value is a power of four and 0 otherwise.",
    "constraints": (
        "1 <= m <= 2 * 10^4 and -10^9 <= n <= 10^9. Only the powers 4^0 to 4^15 fit "
        "in that range."
    ),
    "examples": [
        {
            "input": POWER_OF_FOUR_INPUT,
            "output": _power_of_four(POWER_OF_FOUR_INPUT),
            "explanation": "1, 4, 16 and 64 are 4^0, 4^1, 4^2 and 4^3. The powers of two 2 and 8 land on odd bit positions, and 0 and 3 are not powers of two at all.",
        },
        {
            "input": "6\n256 1024 64 5 -4 0",
            "output": _power_of_four("6\n256 1024 64 5 -4 0"),
            "explanation": "256 is 4^4 and 1024 is 4^5, so both count. 64 is 2^6, an odd exponent, so it fails; 5 and -4 are not powers of two, and 0 is excluded explicitly.",
        },
    ],
    "hints": [
        "Rewrite 4^k as (2^2)^k and the problem splits in two: the number must be a power of two, and its exponent must be even. Both halves are easy on their own, so do them one at a time.",
        "A positive number is a power of two exactly when it has a single set bit, because a power of two is one 1 followed by zeros. The test is `n & (n - 1)` being zero, which holds for a power of two and for nothing else.",
        "To check that the single bit sits at an even position, count the trailing zeros. The test is `n & 0x55555555` being non-zero, since that mask has a 1 at every even position 0, 2, 4, ..., 30.",
        "The combined test is three conditions joined: `n > 0`, `(n & (n - 1)) == 0`, and `(n & 0x55555555) != 0`. The first is not optional, because 0 satisfies `0 & -1 == 0` and would otherwise be accepted.",
        "The mask constant is 01010101010101010101010101010101 in binary, which is 1431655765 in decimal. Being able to read it as an alternating pattern is the entire content of this problem's trick.",
    ],
    "explanation": (
        "Since 4 = 2^2, a number is a power of four exactly when it is a power of "
        "two whose exponent is even. Both halves have a constant-cost bitwise test, "
        "so the whole predicate is three comparisons.\n\n"
        "**Power of two.** A power of two has exactly one set bit: the 1 that "
        "represents 2^k, with zeros everywhere else. Subtracting one from it borrows "
        "across all those zeros and produces `1 0 0 ... 0`, and masking that with the "
        "original clears the single 1, leaving 0. Any number with more than one set "
        "bit keeps at least one of them after the same operation. So "
        "`(n & (n - 1)) == 0` is precisely the power-of-two test for positive `n`.\n\n"
        "**Even exponent.** With one bit set, the exponent *is* the bit's position, "
        "counted from 0 at the least significant end. The condition is therefore that "
        "that one bit is at an even position. The mask `0x55555555` is "
        "`01010101010101010101010101010101`: a 1 at positions 0, 2, 4 and so on up to "
        "30, and a 0 at every odd position. Since `n` has a single set bit, "
        "`n & 0x55555555` is non-zero exactly when that bit falls on a position the "
        "mask covers, which is exactly when the exponent is even.\n\n"
        "**Zero.** The power-of-two test accepts 0, because `0 & (0 - 1)` is `0 & "
        "-1` and every bit of -1 is set, so the mask keeps nothing. Since 0 is not a "
        "power of four, `n > 0` has to be a separate condition rather than something "
        "assumed.\n\n"
        "Together the test is `n > 0 && (n & (n - 1)) == 0 && (n & 0x55555555) != 0`, "
        "which is a constant number of machine operations with no loop and no "
        "division. The arithmetic alternative -- divide by 4 while it divides, then "
        "check the remainder is 1 -- is equally correct and easier to see, and it "
        "runs in O(log n); the mask version is O(1), which is why it is the one worth "
        "being able to produce.\n\n"
        "In JavaScript the comparison needs care, because the bitwise result is a "
        "signed 32-bit integer and `=== 0` on the result of `&` behaves correctly "
        "only for values that fit the pattern. Using `>>> 0` on the input keeps the "
        "bit pattern well defined for the whole positive 32-bit range."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(1) per value",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def is_power_of_four(n):
                \"\"\"Return 1 if n equals 4**k for some k >= 0, else 0.\"\"\"
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                m = data[0]
                for n in data[1 : 1 + m]:
                    print(is_power_of_four(n))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function isPowerOfFour(n) {
              // Return 1 if n equals 4^k for some k >= 0, else 0.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const m = data[0];
              for (const n of data.slice(1, 1 + m)) {
                console.log(isPowerOfFour(n));
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int isPowerOfFour(long n) {
                    // Return 1 if n equals 4^k for some k >= 0, else 0.
                    return 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int m = in.nextInt();
                    for (int i = 0; i < m; i++) {
                        System.out.println(isPowerOfFour(in.nextLong()));
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

            EVEN_BITS = 0x55555555


            def is_power_of_four(n):
                if n <= 0:
                    return 0
                if n & (n - 1):
                    return 0
                return 1 if n & EVEN_BITS else 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                m = data[0]
                for n in data[1 : 1 + m]:
                    print(is_power_of_four(n))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            const EVEN_BITS = 0x55555555;

            function isPowerOfFour(n) {
              if (n <= 0) {
                return 0;
              }
              const value = n >>> 0;
              if ((value & (value - 1)) !== 0) {
                return 0;
              }
              return (value & EVEN_BITS) !== 0 ? 1 : 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
              const m = data[0];
              for (const n of data.slice(1, 1 + m)) {
                console.log(isPowerOfFour(n));
              }
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static final long EVEN_BITS = 0x55555555L;

                static int isPowerOfFour(long n) {
                    if (n <= 0L) {
                        return 0;
                    }
                    if ((n & (n - 1L)) != 0L) {
                        return 0;
                    }
                    return (n & EVEN_BITS) != 0L ? 1 : 0;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int m = in.nextInt();
                    for (int i = 0; i < m; i++) {
                        System.out.println(isPowerOfFour(in.nextLong()));
                    }
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_power_of_four, POWER_OF_FOUR_INPUT),
        judged_case(_power_of_four, "6\n256 1024 64 5 -4 0"),
        judged_case(_power_of_four, "1\n1073741824"),
        judged_case(_power_of_four, "7\n1 4 16 64 256 1024 4096"),
        judged_case(_power_of_four, "5\n-1 -2 -4 -1000000000 -999999999", is_hidden=True),
        judged_case(_power_of_four, "6\n2 8 32 128 512 2048", is_hidden=True),
        judged_case(_power_of_four, "5\n999999999 1000000000 1073741823 1073741825 268435456", is_hidden=True),
        judged_case(_power_of_four, POWER_OF_FOUR_BULK_INPUT, is_hidden=True),
    ],
}


MATH_AND_BITS_PROBLEMS: tuple[dict[str, Any], ...] = (
    REVERSE_BITS,
    COUNT_SET_BITS,
    POWER_OF_FOUR,
)
