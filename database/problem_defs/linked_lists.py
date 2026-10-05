"""Linked lists: the pointer shapes that a learner meets after arrays.

Four problems, chosen so that between them they cover what actually goes wrong
with a singly linked list: forgetting to save `next` before overwriting it,
treating a cycle as a finite walk, assuming two runs are already head-to-tail
aligned, and counting from the wrong end of a list that has no length field.

Every list in this module is given on stdin as its values from head to tail. A
list with no pointers into it cannot express a cycle, so the one problem that
needs a cycle states the link explicitly as an index.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source


def _read_list(stdin: str) -> tuple[list[int], list[int]]:
    """``n``, the values, and whatever integers follow the list."""
    values = int_tokens(stdin)
    n = values[0]
    return values[1 : 1 + n], values[1 + n :]


# --------------------------------------------------------------------------- #
# Reverse a singly linked list
# --------------------------------------------------------------------------- #

REVERSE_INPUT = "5\n1 2 3 4 5"


def _reverse(stdin: str) -> str:
    nodes, _ = _read_list(stdin)
    return " ".join(str(value) for value in reversed(nodes))


REVERSE_LIST: dict[str, Any] = {
    "slug": "reverse-singly-linked-list",
    "title": "Reverse a Singly Linked List",
    "summary": "Reverse the order of a singly linked list's nodes in place.",
    "difficulty": "Easy",
    "topics": ["Linked Lists", "Pointers"],
    "description": (
        "You are given the values of a singly linked list, from the head node to "
        "the last node. Reverse the list so that the last node becomes the head, "
        "and return the values in their new order.\n\n"
        "The reversal must not allocate a second list: every node that exists "
        "before the reversal exists after it, with its `next` pointer rewritten."
    ),
    "input_format": "Line 1: `n`, the number of nodes.\nLine 2: `n` integers, the node values from head to tail.",
    "output_format": "Print the `n` node values after the reversal, separated by single spaces.",
    "constraints": (
        "0 <= n <= 10^5. A list may be empty, in which case nothing is printed "
        "beyond an empty line. Values may repeat and may be negative."
    ),
    "examples": [
        {
            "input": REVERSE_INPUT,
            "output": _reverse(REVERSE_INPUT),
            "explanation": "1 -> 2 -> 3 -> 4 -> 5 becomes 5 -> 4 -> 3 -> 2 -> 1.",
        }
    ],
    "hints": [
        "Drawing the three pointers before you touch anything is worth the ten seconds. You will need the previous node, the current node, and somewhere to keep the rest.",
        "At every step the invariant is: `previous` is the head of the already-reversed prefix, `current` is the first node of the not-yet-reversed suffix.",
        "Save `current.next` into a temporary *before* you overwrite `current.next`. Once you assign `current.next = previous`, the original link is gone and the rest of the list is unreachable.",
        "`previous = current` then `current = saved`. Reversing the order of these two steps gives you a list whose every node points at itself, which is the bug that looks like a correct answer on an empty or one-node list.",
        "You do not need a dummy head. If you prefer one, it must be created *before* the loop and returned as `dummy.next`, because after the loop `previous` and not the dummy is the real head.",
    ],
    "explanation": (
        "Walk the list once with three pointers. `previous` starts null and is the "
        "head of the portion already reversed; `current` is the next node to "
        "process. Before changing anything, stash `current.next` in a temporary. "
        "Then point `current.next` at `previous`, which attaches the node to the "
        "reversed prefix; move `previous` up to `current` and `current` on to the "
        "stashed link.\n\n"
        "When `current` is null the whole list has been consumed and `previous` is "
        "the new head. Each node is visited once and only the `next` pointers are "
        "rewritten, so the time is O(n) and the extra space is O(1). The reason the "
        "temporary is not optional is that the stashed link is the only handle on "
        "the unreversed remainder; destroying it early loses the rest of the list."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class Node {
                    int value;
                    Node next;

                    Node(int value) {
                        this.value = value;
                    }
                }

                static Node reverse(Node head) {
                    // Return the head of the reversed list. Do not build a new list.
                    return head;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    Node head = null;
                    for (int i = n - 1; i >= 0; i -= 1) {
                        Node node = new Node(values[i]);
                        node.next = head;
                        head = node;
                    }
                    head = reverse(head);
                    StringBuilder out = new StringBuilder();
                    for (Node node = head; node != null; node = node.next) {
                        if (out.length() > 0) {
                            out.append(' ');
                        }
                        out.append(node.value);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class Node:
                def __init__(self, value, next=None):
                    self.value = value
                    self.next = next


            def reverse(head):
                # Return the head of the reversed list. Do not build a new list.
                return head


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                head = None
                for value in reversed(values):
                    head = Node(value, head)
                head = reverse(head)
                out = []
                while head is not None:
                    out.append(str(head.value))
                    head = head.next
                print(" ".join(out))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function reverse(head) {
              // Return the head of the reversed list. Do not build a new list.
              return head;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              let head = null;
              for (let i = values.length - 1; i >= 0; i -= 1) {
                head = { value: values[i], next: head };
              }
              head = reverse(head);
              const out = [];
              while (head !== null) {
                out.push(String(head.value));
                head = head.next;
              }
              console.log(out.join(" "));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            class Node:
                def __init__(self, value, next=None):
                    self.value = value
                    self.next = next


            def reverse(head):
                previous = None
                current = head
                while current is not None:
                    saved = current.next
                    current.next = previous
                    previous = current
                    current = saved
                return previous


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                head = None
                for value in reversed(values):
                    head = Node(value, head)
                head = reverse(head)
                out = []
                while head is not None:
                    out.append(str(head.value))
                    head = head.next
                print(" ".join(out))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function reverse(head) {
              let previous = null;
              let current = head;
              while (current !== null) {
                const saved = current.next;
                current.next = previous;
                previous = current;
                current = saved;
              }
              return previous;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              let head = null;
              for (let i = values.length - 1; i >= 0; i -= 1) {
                head = { value: values[i], next: head };
              }
              head = reverse(head);
              const out = [];
              while (head !== null) {
                out.push(String(head.value));
                head = head.next;
              }
              console.log(out.join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class Node {
                    int value;
                    Node next;

                    Node(int value) {
                        this.value = value;
                    }
                }

                static Node reverse(Node head) {
                    Node previous = null;
                    Node current = head;
                    while (current != null) {
                        Node saved = current.next;
                        current.next = previous;
                        previous = current;
                        current = saved;
                    }
                    return previous;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    Node head = null;
                    for (int i = n - 1; i >= 0; i -= 1) {
                        Node node = new Node(values[i]);
                        node.next = head;
                        head = node;
                    }
                    head = reverse(head);
                    StringBuilder out = new StringBuilder();
                    for (Node node = head; node != null; node = node.next) {
                        if (out.length() > 0) {
                            out.append(' ');
                        }
                        out.append(node.value);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_reverse, REVERSE_INPUT),
        judged_case(_reverse, "1\n7"),
        judged_case(_reverse, "2\n4 4"),
        judged_case(_reverse, "0"),
        judged_case(_reverse, "6\n-3 0 -3 7 -1 -1", is_hidden=True),
        judged_case(_reverse, "8\n9 8 7 6 5 4 3 2", is_hidden=True),
        judged_case(_reverse, "3\n100 200 300", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Entry node of a cycle
# --------------------------------------------------------------------------- #

CYCLE_CLEAN_INPUT = "4\n1 2 3 4\n-1"


def _cycle_entry(stdin: str) -> str:
    values, tail = _read_list(stdin)
    n = len(values)
    link = tail[0]
    if link < 0:
        return "-1"
    # `next_index[i]` is where node i points. The last node points at `link`.
    nxt = list(range(1, n)) + [link]
    current = link
    while nxt[current] != link:
        current = nxt[current]
    return str(current)


CYCLE_ENTRY: dict[str, Any] = {
    "slug": "linked-list-cycle-entry",
    "title": "Entry Node of a Linked List Cycle",
    "summary": "Return the index of the first node that lies on a cycle, or -1.",
    "difficulty": "Medium",
    "topics": ["Linked Lists", "Two Pointers", "Hash Maps"],
    "description": (
        "A singly linked list may have a cycle: some node's `next` points back to "
        "an earlier node instead of to null. Given the values of the list from head "
        "to tail, and the index that the last node links to, find the index of the "
        "first node on the cycle.\n\n"
        "If the last node links to -1 the list has no cycle; report -1. Otherwise "
        "the cycle is the path starting at the reported index and following `next` "
        "until it returns to that same index."
    ),
    "input_format": (
        "Line 1: `n`, the number of nodes.\n"
        "Line 2: `n` integers, the node values from head to tail.\n"
        "Line 3: `link`, the 0-based index the last node's `next` points to, or -1 "
        "if the last node points to null."
    ),
    "output_format": "Print the 0-based index of the cycle's entry node, or -1 if there is no cycle.",
    "constraints": (
        "1 <= n <= 10^5 and 0 <= values[i] <= 10^9. `link` is either -1 or an index "
        "strictly less than n. Values are given but the cycle is defined by indices, "
        "so equal values never merge two nodes."
    ),
    "examples": [
        {
            "input": CYCLE_CLEAN_INPUT,
            "output": _cycle_entry(CYCLE_CLEAN_INPUT),
            "explanation": "The last node links to -1, so the list simply ends.",
        },
        {
            "input": "4\n1 2 3 4\n1",
            "output": _cycle_entry("4\n1 2 3 4\n1"),
            "explanation": "Node 3 links to node 1, so 1 -> 2 -> 3 -> 1 repeats. The entry is index 1.",
        },
    ],
    "hints": [
        "Before choosing an algorithm, notice that the cycle is described by indices rather than by values. That means you can decide the answer without ever building the list.",
        "The cycle consists of the nodes on the path from `link` onwards until a node points back to `link`. So start at `link` and ask, at each node, whether its successor is `link` itself.",
        "If you are at the last node, its successor is `link` by definition, so the last node is the answer exactly when `link` is the last index. Handle that case by checking the condition before you advance.",
        "Write the successor rule once: for every index except the last it is `index + 1`, and for the last it is `link`. With that as a single lookup the walk is a loop rather than a special case.",
        "This is O(n) with O(1) space because `link` already tells you where the cycle begins. The general form -- where you are only told that *some* cycle exists -- is the two-pointer or hash-set problem, and it is strictly harder.",
    ],
    "explanation": (
        "The last node's `next` is given as `link`, and every other node's `next` is "
        "simply the next index. Those two facts define the successor of every node, "
        "so the list never has to exist in memory to answer the question.\n\n"
        "If `link` is -1 there is no cycle and the answer is -1. Otherwise start at "
        "`link` and follow successors until the successor is `link` again; the node "
        "you are standing on is the entry, because it is the first node of the loop. "
        "The walk visits each node of the cycle once. Successors are computed with a "
        "single arithmetic test rather than a stored structure, so the space is "
        "constant and the time is O(n).\n\n"
        "The useful observation is that this problem hands over the answer to the "
        "hard part. When the entry point is unknown, the same walk cannot be started, "
        "and detecting the cycle becomes the real work."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int cycleEntry(int[] values, int link) {
                    // Return the index the cycle starts at, or -1 when link is -1.
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    int link = in.nextInt();
                    System.out.println(cycleEntry(values, link));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def cycle_entry(values, link):
                # Return the index the cycle starts at, or -1 when link == -1.
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                link = data[1 + n]
                print(cycle_entry(values, link))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function cycleEntry(values, link) {
              // Return the index the cycle starts at, or -1 when link === -1.
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const link = Number(data[1 + n]);
              console.log(cycleEntry(values, link));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def cycle_entry(values, link):
                if link < 0:
                    return -1
                n = len(values)
                last = n - 1
                current = link
                while True:
                    successor = link if current == last else current + 1
                    if successor == link:
                        return current
                    current = successor


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                link = data[1 + n]
                print(cycle_entry(values, link))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function cycleEntry(values, link) {
              if (link < 0) {
                return -1;
              }
              const last = values.length - 1;
              let current = link;
              for (;;) {
                const successor = current === last ? link : current + 1;
                if (successor === link) {
                  return current;
                }
                current = successor;
              }
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const link = Number(data[1 + n]);
              console.log(cycleEntry(values, link));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static int cycleEntry(int[] values, int link) {
                    if (link < 0) {
                        return -1;
                    }
                    int last = values.length - 1;
                    int current = link;
                    while (true) {
                        int successor = current == last ? link : current + 1;
                        if (successor == link) {
                            return current;
                        }
                        current = successor;
                    }
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    int link = in.nextInt();
                    System.out.println(cycleEntry(values, link));
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_cycle_entry, CYCLE_CLEAN_INPUT),
        judged_case(_cycle_entry, "4\n1 2 3 4\n1"),
        judged_case(_cycle_entry, "1\n5\n0"),
        judged_case(_cycle_entry, "1\n5\n-1"),
        judged_case(_cycle_entry, "5\n1 2 3 4 5\n4", is_hidden=True),
        judged_case(_cycle_entry, "6\n9 8 7 6 5 4\n2", is_hidden=True),
        judged_case(_cycle_entry, "3\n4 4 4\n0", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Merge two sorted lists
# --------------------------------------------------------------------------- #

MERGE_INPUT = "3\n1 3 5\n4\n2 4 6 8"


def _merge(stdin: str) -> str:
    data = int_tokens(stdin)
    n = data[0]
    first = data[1 : 1 + n]
    m = data[1 + n]
    second = data[2 + n : 2 + n + m]
    merged: list[int] = []
    i = j = 0
    while i < n and j < m:
        if first[i] <= second[j]:
            merged.append(first[i])
            i += 1
        else:
            merged.append(second[j])
            j += 1
    merged.extend(first[i:])
    merged.extend(second[j:])
    return " ".join(str(value) for value in merged)


MERGE_SORTED: dict[str, Any] = {
    "slug": "merge-two-sorted-lists",
    "title": "Merge Two Sorted Lists",
    "summary": "Merge two ascending lists into one ascending list.",
    "difficulty": "Easy",
    "topics": ["Linked Lists", "Two Pointers", "Merging"],
    "description": (
        "You are given the values of two singly linked lists, each already sorted "
        "in ascending order. Merge them into a single ascending list and return "
        "its values.\n\n"
        "Neither input list is empty, and neither contains duplicates within "
        "itself. Equal values may appear in both lists, and when they do either "
        "order is acceptable."
    ),
    "input_format": (
        "Line 1: `n`, the length of the first list.\n"
        "Line 2: `n` integers, the first list in ascending order.\n"
        "Line 3: `m`, the length of the second list.\n"
        "Line 4: `m` integers, the second list in ascending order."
    ),
    "output_format": "Print all `n + m` values of the merged list, separated by single spaces.",
    "constraints": (
        "1 <= n, m <= 10^5 and -10^9 <= values <= 10^9. The two inputs are each "
        "already sorted; you do not need to sort them."
    ),
    "examples": [
        {
            "input": MERGE_INPUT,
            "output": _merge(MERGE_INPUT),
            "explanation": "Taking the smaller head at each step gives 1 2 3 4 5 6 8.",
        }
    ],
    "hints": [
        "Sorting the concatenation works and is O((n + m) log(n + m)). The inputs are already sorted, so ask what you can do without reordering anything.",
        "Two sorted lists can be merged by comparing their heads. Exactly one of the two heads is the smallest remaining value, and after taking it that list's head advances.",
        "Keep one pointer per list, plus a tail pointer for the list you are building. A dummy head node removes every special case for the first element, so the loop body never has to ask 'is this the first node yet?'.",
        "The loop can only stop when one list is exhausted. The moment it does, append whatever remains of the *other* list -- it is already in order, so it must not be walked element by element.",
        "Choosing `<=` rather than `<` on the tie is what keeps the merge stable. Either order passes here, but a merge that reorders equal elements breaks the moment someone relies on the input order.",
    ],
    "explanation": (
        "Compare the head of each list and repeatedly move the smaller of the two "
        "onto the tail of the result. Because each input is sorted, the smaller "
        "head is the smallest value still unseen, so the result stays sorted "
        "without a final sort pass.\n\n"
        "Using a dummy head node means the loop never needs to special-case the "
        "first element, and a single `tail` pointer carries the result. When one "
        "list runs out, the remainder of the other is already sorted and is "
        "attached directly. Taking the left value on ties makes the merge stable.\n\n"
        "Each value is visited once and exactly `n + m` values are produced, so the "
        "time is O(n + m). Only a fixed number of pointers are kept, so the extra "
        "space is O(1) beyond the nodes of the result."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n + m)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.ArrayList;
            import java.util.List;
            import java.util.Scanner;

            public class Main {
                static class Node {
                    int value;
                    Node next;

                    Node(int value) {
                        this.value = value;
                    }
                }

                static Node build(List<Integer> values) {
                    Node head = null;
                    for (int i = values.size() - 1; i >= 0; i -= 1) {
                        Node node = new Node(values.get(i));
                        node.next = head;
                        head = node;
                    }
                    return head;
                }

                static Node merge(Node a, Node b) {
                    // Return the head of a list holding every value of a and b, sorted.
                    return null;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    List<Integer> first = new ArrayList<>();
                    for (int i = 0; i < n; i += 1) {
                        first.add(in.nextInt());
                    }
                    int m = in.nextInt();
                    List<Integer> second = new ArrayList<>();
                    for (int i = 0; i < m; i += 1) {
                        second.add(in.nextInt());
                    }
                    Node head = merge(build(first), build(second));
                    StringBuilder out = new StringBuilder();
                    for (Node node = head; node != null; node = node.next) {
                        if (out.length() > 0) {
                            out.append(' ');
                        }
                        out.append(node.value);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class Node:
                def __init__(self, value, next=None):
                    self.value = value
                    self.next = next


            def build(values):
                head = None
                for value in reversed(values):
                    head = Node(value, head)
                return head


            def merge(a, b):
                # Return the head of a list holding every value of a and b, sorted.
                return None


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                first = data[1 : 1 + n]
                m = data[1 + n]
                second = data[2 + n : 2 + n + m]
                head = merge(build(first), build(second))
                out = []
                while head is not None:
                    out.append(str(head.value))
                    head = head.next
                print(" ".join(out))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              let head = null;
              for (let i = values.length - 1; i >= 0; i -= 1) {
                head = { value: values[i], next: head };
              }
              return head;
            }

            function merge(a, b) {
              // Return the head of a list holding every value of a and b, sorted.
              return null;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const first = data.slice(1, 1 + n).map(Number);
              const m = Number(data[1 + n]);
              const second = data.slice(2 + n, 2 + n + m).map(Number);
              let head = merge(build(first), build(second));
              const out = [];
              while (head !== null) {
                out.push(String(head.value));
                head = head.next;
              }
              console.log(out.join(" "));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            class Node:
                def __init__(self, value, next=None):
                    self.value = value
                    self.next = next


            def build(values):
                head = None
                for value in reversed(values):
                    head = Node(value, head)
                return head


            def merge(a, b):
                dummy = Node(0)
                tail = dummy
                while a is not None and b is not None:
                    if a.value <= b.value:
                        tail.next = a
                        a = a.next
                    else:
                        tail.next = b
                        b = b.next
                    tail = tail.next
                tail.next = a if b is None else b
                return dummy.next


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                first = data[1 : 1 + n]
                m = data[1 + n]
                second = data[2 + n : 2 + n + m]
                head = merge(build(first), build(second))
                out = []
                while head is not None:
                    out.append(str(head.value))
                    head = head.next
                print(" ".join(out))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              let head = null;
              for (let i = values.length - 1; i >= 0; i -= 1) {
                head = { value: values[i], next: head };
              }
              return head;
            }

            function merge(a, b) {
              const dummy = { value: 0, next: null };
              let tail = dummy;
              while (a !== null && b !== null) {
                if (a.value <= b.value) {
                  tail.next = a;
                  a = a.next;
                } else {
                  tail.next = b;
                  b = b.next;
                }
                tail = tail.next;
              }
              tail.next = a === null ? b : a;
              return dummy.next;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const first = data.slice(1, 1 + n).map(Number);
              const m = Number(data[1 + n]);
              const second = data.slice(2 + n, 2 + n + m).map(Number);
              let head = merge(build(first), build(second));
              const out = [];
              while (head !== null) {
                out.push(String(head.value));
                head = head.next;
              }
              console.log(out.join(" "));
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
                static class Node {
                    int value;
                    Node next;

                    Node(int value) {
                        this.value = value;
                    }
                }

                static Node build(List<Integer> values) {
                    Node head = null;
                    for (int i = values.size() - 1; i >= 0; i -= 1) {
                        Node node = new Node(values.get(i));
                        node.next = head;
                        head = node;
                    }
                    return head;
                }

                static Node merge(Node a, Node b) {
                    Node dummy = new Node(0);
                    Node tail = dummy;
                    while (a != null && b != null) {
                        if (a.value <= b.value) {
                            tail.next = a;
                            a = a.next;
                        } else {
                            tail.next = b;
                            b = b.next;
                        }
                        tail = tail.next;
                    }
                    tail.next = a == null ? b : a;
                    return dummy.next;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    List<Integer> first = new ArrayList<>();
                    for (int i = 0; i < n; i += 1) {
                        first.add(in.nextInt());
                    }
                    int m = in.nextInt();
                    List<Integer> second = new ArrayList<>();
                    for (int i = 0; i < m; i += 1) {
                        second.add(in.nextInt());
                    }
                    Node head = merge(build(first), build(second));
                    StringBuilder out = new StringBuilder();
                    for (Node node = head; node != null; node = node.next) {
                        if (out.length() > 0) {
                            out.append(' ');
                        }
                        out.append(node.value);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_merge, MERGE_INPUT),
        judged_case(_merge, "1\n1\n1\n2"),
        judged_case(_merge, "2\n1 1\n3\n1 1 1"),
        judged_case(_merge, "4\n-9 -4 0 3\n3\n-2 1 6"),
        judged_case(_merge, "5\n1 2 3 4 5\n2\n0 9", is_hidden=True),
        judged_case(_merge, "3\n10 30 50\n4\n10 20 40 60", is_hidden=True),
        judged_case(_merge, "6\n-5 -3 -1 1 3 5\n2\n-4 7", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Remove the n-th node from the end
# --------------------------------------------------------------------------- #

REMOVE_INPUT = "5\n1 2 3 4 5\n2"


def _remove_nth(stdin: str) -> str:
    values, tail = _read_list(stdin)
    k = tail[0]
    del values[len(values) - k]
    return " ".join(str(value) for value in values)


REMOVE_NTH: dict[str, Any] = {
    "slug": "remove-nth-node-from-end",
    "title": "Remove the Nth Node From the End",
    "summary": "Delete the node k positions from the end of a singly linked list.",
    "difficulty": "Medium",
    "topics": ["Linked Lists", "Two Pointers"],
    "description": (
        "Given the values of a singly linked list from head to tail, and an "
        "integer `k`, remove the node that is `k` positions from the end and "
        "return the values of the remaining list.\n\n"
        "Counting from the end: the last node is 1 position from the end. It is "
        "guaranteed that `k` names an existing node, so the list is never empty "
        "after the removal."
    ),
    "input_format": (
        "Line 1: `n`, the number of nodes.\n"
        "Line 2: `n` integers, the node values from head to tail.\n"
        "Line 3: `k`, counting from 1 at the tail."
    ),
    "output_format": "Print the values of the list after the removal, separated by single spaces.",
    "constraints": "1 <= n <= 10^5, 1 <= k <= n, and -10^9 <= values <= 10^9.",
    "examples": [
        {
            "input": REMOVE_INPUT,
            "output": _remove_nth(REMOVE_INPUT),
            "explanation": "The last node is 1 from the end, so 2 from the end is 4. Removing it leaves 1 2 3 5.",
        }
    ],
    "hints": [
        "If you knew the length you could walk straight to index `n - k`. Getting the length needs a first pass, which is fine, but ask whether one pass can do it.",
        "Place two pointers `k` nodes apart and advance them together. When the front pointer reaches the end, the rear pointer is exactly `k` positions from the end.",
        "To make them `k` apart, first move the front pointer `k` steps. If it runs off the end, `k` equals the list length and the node to remove is the head -- handle that before the main loop.",
        "Removing a node means rewiring its predecessor's `next` to the removed node's successor. The predecessor is the rear pointer, so keep it one node behind rather than at the node itself.",
        "The head case is the only special case, and it is special for a real reason: the node before the head does not exist, so there is nothing to rewire. Deciding `k == n` up front is cleaner than special-casing inside the loop."
    ],
    "explanation": (
        "Two pointers solve this in one pass. Advance a front pointer `k` steps "
        "first; if it leaves the list, the list has exactly `k` nodes and the head "
        "must go. Otherwise the front pointer is `k` positions ahead of a rear "
        "pointer at the head, and that offset is preserved when both move.\n\n"
        "Walk the front pointer to the end. At that moment the rear pointer sits on "
        "the node to delete, and one node behind it sits on the predecessor whose "
        "`next` must be rewired to skip over the doomed node. Doing the rewire "
        "from the predecessor is why the rear pointer is kept one behind rather "
        "than on the target itself.\n\n"
        "Each node is visited at most twice and only a fixed number of pointers are "
        "used, so the time is O(n) and the extra space is O(1)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class Node {
                    int value;
                    Node next;

                    Node(int value) {
                        this.value = value;
                    }
                }

                static Node removeNth(Node head, int k) {
                    // Remove the kth node from the end and return the new head.
                    return head;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    Node head = null;
                    for (int i = n - 1; i >= 0; i -= 1) {
                        Node node = new Node(values[i]);
                        node.next = head;
                        head = node;
                    }
                    int k = in.nextInt();
                    head = removeNth(head, k);
                    StringBuilder out = new StringBuilder();
                    for (Node node = head; node != null; node = node.next) {
                        if (out.length() > 0) {
                            out.append(' ');
                        }
                        out.append(node.value);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class Node:
                def __init__(self, value, next=None):
                    self.value = value
                    self.next = next


            def remove_nth(head, k):
                # Remove the kth node from the end and return the new head.
                return head


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                k = data[1 + n]
                head = None
                for value in reversed(values):
                    head = Node(value, head)
                head = remove_nth(head, k)
                out = []
                while head is not None:
                    out.append(str(head.value))
                    head = head.next
                print(" ".join(out))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function removeNth(head, k) {
              // Remove the kth node from the end and return the new head.
              return head;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const k = Number(data[1 + n]);
              let head = null;
              for (let i = values.length - 1; i >= 0; i -= 1) {
                head = { value: values[i], next: head };
              }
              head = removeNth(head, k);
              const out = [];
              while (head !== null) {
                out.push(String(head.value));
                head = head.next;
              }
              console.log(out.join(" "));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            class Node:
                def __init__(self, value, next=None):
                    self.value = value
                    self.next = next


            def remove_nth(head, k):
                dummy = Node(0, head)
                front = dummy
                for _ in range(k):
                    front = front.next
                rear = dummy
                while front is not None and front.next is not None:
                    front = front.next
                    rear = rear.next
                rear.next = rear.next.next
                return dummy.next


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                k = data[1 + n]
                head = None
                for value in reversed(values):
                    head = Node(value, head)
                head = remove_nth(head, k)
                out = []
                while head is not None:
                    out.append(str(head.value))
                    head = head.next
                print(" ".join(out))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function removeNth(head, k) {
              const dummy = { value: 0, next: head };
              let front = dummy;
              for (let i = 0; i < k; i += 1) {
                front = front.next;
              }
              let rear = dummy;
              while (front !== null && front.next !== null) {
                front = front.next;
                rear = rear.next;
              }
              rear.next = rear.next.next;
              return dummy.next;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const k = Number(data[1 + n]);
              let head = null;
              for (let i = values.length - 1; i >= 0; i -= 1) {
                head = { value: values[i], next: head };
              }
              head = removeNth(head, k);
              const out = [];
              while (head !== null) {
                out.push(String(head.value));
                head = head.next;
              }
              console.log(out.join(" "));
            }

            main();
            """
        ),
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class Node {
                    int value;
                    Node next;

                    Node(int value) {
                        this.value = value;
                    }
                }

                static Node removeNth(Node head, int k) {
                    Node dummy = new Node(0);
                    dummy.next = head;
                    Node front = dummy;
                    for (int i = 0; i < k; i += 1) {
                        front = front.next;
                    }
                    Node rear = dummy;
                    while (front != null && front.next != null) {
                        front = front.next;
                        rear = rear.next;
                    }
                    rear.next = rear.next.next;
                    return dummy.next;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    Node head = null;
                    for (int i = n - 1; i >= 0; i -= 1) {
                        Node node = new Node(values[i]);
                        node.next = head;
                        head = node;
                    }
                    int k = in.nextInt();
                    head = removeNth(head, k);
                    StringBuilder out = new StringBuilder();
                    for (Node node = head; node != null; node = node.next) {
                        if (out.length() > 0) {
                            out.append(' ');
                        }
                        out.append(node.value);
                    }
                    System.out.println(out);
                }
            }
            """
        ),
    },
    "test_cases": [
        judged_case(_remove_nth, REMOVE_INPUT),
        judged_case(_remove_nth, "1\n7\n1"),
        judged_case(_remove_nth, "3\n1 2 3\n3"),
        judged_case(_remove_nth, "4\n9 8 7 6\n2"),
        judged_case(_remove_nth, "6\n-1 -2 -3 -4 -5 -6\n1", is_hidden=True),
        judged_case(_remove_nth, "6\n-1 -2 -3 -4 -5 -6\n6", is_hidden=True),
        judged_case(_remove_nth, "5\n10 20 30 40 50\n3", is_hidden=True),
    ],
}


LINKED_LISTS_PROBLEMS: list[dict[str, Any]] = [
    REVERSE_LIST,
    CYCLE_ENTRY,
    MERGE_SORTED,
    REMOVE_NTH,
]

__all__ = ["LINKED_LISTS_PROBLEMS"]