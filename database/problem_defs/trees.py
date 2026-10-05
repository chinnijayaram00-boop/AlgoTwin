"""Trees: shape, ordering, and the recursive answers that hang off them.

Four problems over binary trees given in level order, which is the serialization
that actually survives a text judge: the nodes are the slots of a complete
binary tree read left to right, and ``0`` marks a slot with no node. Values are
positive and distinct, so ``0`` is unambiguous and "is this a valid search tree"
has exactly one answer.

Between them the four problems cover the four things learners try first on a
tree: prove an ordering invariant by carrying bounds down the recursion, exploit
that same ordering to walk to a single node, fold a subproblem upward with
`max`, and compare two subtrees against each other instead of against a stored
copy of themselves.
"""

from __future__ import annotations

from typing import Any

from database.problem_spec import int_tokens, judged_case, source


class _Node:
    """A binary tree node, shared by the oracles in this module."""

    __slots__ = ("left", "right", "value")

    def __init__(self, value: int) -> None:
        self.value = value
        self.left: _Node | None = None
        self.right: _Node | None = None


def _build(values: list[int]) -> _Node | None:
    """Expand a level-order array into a tree.

    Slot ``i`` of a level-order array is the left child of slot ``(i - 1) // 2``
    when ``i`` is odd and its right child when ``i`` is even, because children
    come in pairs left then right.
    """
    if not values or values[0] == 0:
        return None
    slots: list[_Node | None] = [None] * len(values)
    slots[0] = _Node(values[0])
    for index in range(1, len(values)):
        if values[index] == 0:
            continue
        parent = slots[(index - 1) // 2]
        if parent is None:
            continue
        node = _Node(values[index])
        if index % 2 == 1:
            parent.left = node
        else:
            parent.right = node
        slots[index] = node
    return slots[0]


def _split(stdin: str) -> tuple[list[int], list[int]]:
    """The level-order array and whatever integers follow it."""
    tokens = int_tokens(stdin)
    n = tokens[0]
    return tokens[1 : 1 + n], tokens[1 + n :]


# --------------------------------------------------------------------------- #
# Is this a valid binary search tree?
# --------------------------------------------------------------------------- #

BST_OK_INPUT = "7\n8 4 12 2 6 10 14"


def _valid_bst(stdin: str) -> str:
    root = _build(_split(stdin)[0])

    def within_bounds(node: _Node | None, low: int, high: int) -> bool:
        if node is None:
            return True
        if not low < node.value < high:
            return False
        return within_bounds(node.left, low, node.value) and within_bounds(node.right, node.value, high)

    return "yes" if within_bounds(root, 0, 1 << 40) else "no"


BST_VALID: dict[str, Any] = {
    "slug": "validate-binary-search-tree",
    "title": "Validate a Binary Search Tree",
    "summary": "Decide whether every node sits inside the range set by its ancestors.",
    "difficulty": "Easy",
    "topics": ["Trees", "Binary Search Trees", "Recursion", "Depth-First Search"],
    "description": (
        "You are given a binary tree in level order, with `0` marking an absent "
        "node and every value positive and distinct. Decide whether the tree is a "
        "valid binary search tree.\n\n"
        "It is a valid search tree when, for every node, all values in its left "
        "subtree are smaller than the node's value and all values in its right "
        "subtree are larger. It is not enough for a left child to be smaller than "
        "its parent: the whole subtree must respect the bound the ancestors set."
    ),
    "input_format": (
        "Line 1: `n`, the number of level-order slots.\n"
        "Line 2: `n` integers, the values in level order, where `0` means the "
        "slot holds no node."
    ),
    "output_format": "Print `yes` if the tree is a valid binary search tree, otherwise `no`.",
    "constraints": (
        "1 <= n <= 10^5. Values are distinct and in 1..10^9. Every non-zero slot "
        "has a non-zero parent, so the level-order array always describes a tree."
    ),
    "examples": [
        {
            "input": BST_OK_INPUT,
            "output": _valid_bst(BST_OK_INPUT),
            "explanation": "Every left subtree value is below its node and every right subtree value is above, so the tree is valid.",
        },
        {
            "input": "5\n5 1 4 0 0 3 6",
            "output": _valid_bst("5\n5 1 4 0 0 3 6"),
            "explanation": "3 sits in the left subtree of 5 but is larger than 4, the root of that subtree. A valid tree would need 3 to stay below 4.",
        },
    ],
    "hints": [
        "Comparing each node with its parent catches some mistakes but not all. What is a concrete example where every node beats its parent and the tree is still invalid?",
        "The real invariant involves the whole ancestry chain. A node must satisfy bounds set by every ancestor above it, not just the one immediately above.",
        "Carry two numbers down the recursion: an exclusive lower bound and an exclusive upper bound. A node inside the range becomes the upper bound for its left descent and the lower bound for its right descent.",
        "Start with an open range wider than any possible value, so the root is not artificially constrained. Returning `true` for a null node is what makes an empty subtree vacuously valid.",
        "Both subtrees must be checked, so return the conjunction of the two recursive results. Short-circuiting on `&&` is fine for correctness, but note that returning a bare `or` of the failures is the classic mistake here.",
    ],
    "explanation": (
        "The condition 'smaller than the parent on the left, larger on the right' is "
        "necessary but not sufficient, because a node deep in a subtree is bounded by "
        "every ancestor above it, not just the nearest one. The fix is to make those "
        "bounds part of the recursion.\n\n"
        "`within_bounds(node, low, high)` answers whether the whole subtree rooted at "
        "`node` respects the open interval `(low, high)`. A null node satisfies "
        "anything. A node whose value escapes the interval fails immediately. "
        "Otherwise the node splits the interval: its left subtree must stay below the "
        "node's value, and its right subtree must stay above it.\n\n"
        "The root is called with a range wide enough to contain every value, so the "
        "root is never artificially constrained. Each node is visited once, giving "
        "O(n) time, and the recursion holds one interval per level, so the space is "
        "O(h), which is O(n) for a degenerate tree."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(h)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    // Expand the level-order array into a tree. 0 means no node.
                    return null;
                }

                static boolean withinBounds(TreeNode node, long low, long high) {
                    // Does the whole subtree at node stay strictly inside (low, high)?
                    return true;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    TreeNode root = build(values);
                    System.out.println(withinBounds(root, 0L, 1L << 40) ? "yes" : "no");
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                # Expand the level-order array into a tree. 0 means no node.
                return None


            def within_bounds(node, low, high):
                # Does the whole subtree at node stay strictly inside (low, high)?
                return True


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                root = build(values)
                print("yes" if within_bounds(root, 0, 1 << 40) else "no")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              // Expand the level-order array into a tree. 0 means no node.
              return null;
            }

            function withinBounds(node, low, high) {
              // Does the whole subtree at node stay strictly inside (low, high)?
              return true;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const root = build(values);
              console.log(withinBounds(root, 0, Number.MAX_SAFE_INTEGER) ? "yes" : "no");
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    if (values.length == 0 || values[0] == 0) {
                        return null;
                    }
                    TreeNode[] slots = new TreeNode[values.length];
                    slots[0] = new TreeNode(values[0]);
                    for (int i = 1; i < values.length; i += 1) {
                        if (values[i] == 0) {
                            continue;
                        }
                        TreeNode parent = slots[(i - 1) / 2];
                        if (parent == null) {
                            continue;
                        }
                        TreeNode node = new TreeNode(values[i]);
                        if (i % 2 == 1) {
                            parent.left = node;
                        } else {
                            parent.right = node;
                        }
                        slots[i] = node;
                    }
                    return slots[0];
                }

                static boolean withinBounds(TreeNode node, long low, long high) {
                    if (node == null) {
                        return true;
                    }
                    if (node.value <= low || node.value >= high) {
                        return false;
                    }
                    return withinBounds(node.left, low, node.value)
                            && withinBounds(node.right, node.value, high);
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    TreeNode root = build(values);
                    System.out.println(withinBounds(root, 0L, 1L << 40) ? "yes" : "no");
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                if not values or values[0] == 0:
                    return None
                slots = [None] * len(values)
                slots[0] = TreeNode(values[0])
                for index in range(1, len(values)):
                    if values[index] == 0:
                        continue
                    parent = slots[(index - 1) // 2]
                    if parent is None:
                        continue
                    node = TreeNode(values[index])
                    if index % 2 == 1:
                        parent.left = node
                    else:
                        parent.right = node
                    slots[index] = node
                return slots[0]


            def within_bounds(node, low, high):
                if node is None:
                    return True
                if not low < node.value < high:
                    return False
                return within_bounds(node.left, low, node.value) and within_bounds(
                    node.right, node.value, high
                )


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                root = build(values)
                print("yes" if within_bounds(root, 0, 1 << 40) else "no")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              if (values.length === 0 || values[0] === 0) {
                return null;
              }
              const slots = new Array(values.length).fill(null);
              slots[0] = { value: values[0], left: null, right: null };
              for (let i = 1; i < values.length; i += 1) {
                if (values[i] === 0) {
                  continue;
                }
                const parent = slots[Math.floor((i - 1) / 2)];
                if (parent === null) {
                  continue;
                }
                const node = { value: values[i], left: null, right: null };
                if (i % 2 === 1) {
                  parent.left = node;
                } else {
                  parent.right = node;
                }
                slots[i] = node;
              }
              return slots[0];
            }

            function withinBounds(node, low, high) {
              if (node === null) {
                return true;
              }
              if (!(low < node.value && node.value < high)) {
                return false;
              }
              return (
                withinBounds(node.left, low, node.value) &&
                withinBounds(node.right, node.value, high)
              );
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const root = build(values);
              console.log(withinBounds(root, 0, Number.MAX_SAFE_INTEGER) ? "yes" : "no");
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_valid_bst, BST_OK_INPUT),
        judged_case(_valid_bst, "3\n2 1 3"),
        judged_case(_valid_bst, "5\n5 1 4 0 0 3 6"),
        judged_case(_valid_bst, "1\n7"),
        judged_case(_valid_bst, "4\n10 5 15 6", is_hidden=True),
        judged_case(_valid_bst, "6\n20 10 30 5 15 25 35", is_hidden=True),
        judged_case(_valid_bst, "9\n50 30 70 20 40 60 80 10 35", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Lowest common ancestor in a search tree
# --------------------------------------------------------------------------- #

LCA_INPUT = "7\n5 3 8 1 4 7 9\n1 4"


def _lowest_common_ancestor(stdin: str) -> str:
    tree, rest = _split(stdin)
    first, second = rest[0], rest[1]
    node = _build(tree)
    while node is not None:
        if first < node.value and second < node.value:
            node = node.left
        elif first > node.value and second > node.value:
            node = node.right
        else:
            return str(node.value)
    return "-1"


LOWEST_COMMON_ANCESTOR: dict[str, Any] = {
    "slug": "lowest-common-ancestor-in-a-bst",
    "title": "Lowest Common Ancestor in a Search Tree",
    "summary": "Walk a binary search tree to the deepest node above both given values.",
    "difficulty": "Medium",
    "topics": ["Trees", "Binary Search Trees", "Recursion", "Depth-First Search"],
    "description": (
        "You are given a valid binary search tree in level order, with `0` marking "
        "an absent node, and two values `p` and `q` that both appear in the tree. "
        "Print the value of their lowest common ancestor: the deepest node that has "
        "both of them somewhere below it.\n\n"
        "A node is its own ancestor, so asking for the ancestor of a value with "
        "itself returns that value."
    ),
    "input_format": (
        "Line 1: `n`, the number of level-order slots.\n"
        "Line 2: `n` integers, the values in level order, where `0` means no node.\n"
        "Line 3: `p q`, the two values to look for."
    ),
    "output_format": "Print the value of the lowest common ancestor of `p` and `q`.",
    "constraints": (
        "1 <= n <= 10^5. Values are distinct and in 1..10^9. Both `p` and `q` occur "
        "in the tree."
    ),
    "examples": [
        {
            "input": LCA_INPUT,
            "output": _lowest_common_ancestor(LCA_INPUT),
            "explanation": "1 and 4 both sit under node 3, and 3 is the deepest node that has both below it.",
        }
    ],
    "hints": [
        "You could find both values by two searches and then walk up, but the tree has no parent pointers. Is there information in the ordering that removes the need to walk back up?",
        "At any node, the tree's ordering tells you which side each value is on. If both are on the same side, the answer is somewhere in that subtree.",
        "If both values are smaller than the current node, descend left. If both are larger, descend right. In every other case the current node is the answer.",
        "'Every other case' includes one value below and one above the node, and also a value equal to the node. Handling equality as an answer rather than as a direction is the case that trips people up.",
        "This becomes an iterative loop with a single pointer. A recursive version works too, but every recursive step here answers the same question on a smaller tree, so the loop has nothing to add back.",
    ],
    "explanation": (
        "In a search tree the ordering means that from any node, each value is "
        "unambiguously on one side or the other. So at each node there are only "
        "three situations: both values below, both above, or straddling the node.\n\n"
        "If both are on the same side, that node cannot be the answer, because the "
        "node itself is not below itself -- the answer must lie strictly inside the "
        "child subtree, so the search continues there. If the values straddle the "
        "node, one is in the left subtree and one is in the right, which makes this "
        "node the deepest node above both. That is the answer.\n\n"
        "Because each step both discards the current node and narrows the problem "
        "to a child, no recursion is needed and nothing has to be combined on the "
        "way back up. The walk follows a single root-to-leaf path, so the time is "
        "O(h) and the extra space is O(1)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(h)",
    "expected_space_complexity": "O(1)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    // Expand the level-order array into a tree. 0 means no node.
                    return null;
                }

                static int lowestCommonAncestor(TreeNode root, int p, int q) {
                    // Both p and q are present. Return the ancestor's value.
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    int p = in.nextInt();
                    int q = in.nextInt();
                    TreeNode root = build(values);
                    System.out.println(lowestCommonAncestor(root, p, q));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                # Expand the level-order array into a tree. 0 means no node.
                return None


            def lowest_common_ancestor(root, p, q):
                # Both p and q are present. Return the ancestor's value.
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                p = data[1 + n]
                q = data[2 + n]
                root = build(values)
                print(lowest_common_ancestor(root, p, q))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              // Expand the level-order array into a tree. 0 means no node.
              return null;
            }

            function lowestCommonAncestor(root, p, q) {
              // Both p and q are present. Return the ancestor's value.
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const p = Number(data[1 + n]);
              const q = Number(data[2 + n]);
              const root = build(values);
              console.log(lowestCommonAncestor(root, p, q));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    if (values.length == 0 || values[0] == 0) {
                        return null;
                    }
                    TreeNode[] slots = new TreeNode[values.length];
                    slots[0] = new TreeNode(values[0]);
                    for (int i = 1; i < values.length; i += 1) {
                        if (values[i] == 0) {
                            continue;
                        }
                        TreeNode parent = slots[(i - 1) / 2];
                        if (parent == null) {
                            continue;
                        }
                        TreeNode node = new TreeNode(values[i]);
                        if (i % 2 == 1) {
                            parent.left = node;
                        } else {
                            parent.right = node;
                        }
                        slots[i] = node;
                    }
                    return slots[0];
                }

                static int lowestCommonAncestor(TreeNode root, int p, int q) {
                    TreeNode node = root;
                    while (node != null) {
                        if (p < node.value && q < node.value) {
                            node = node.left;
                        } else if (p > node.value && q > node.value) {
                            node = node.right;
                        } else {
                            return node.value;
                        }
                    }
                    return -1;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    int p = in.nextInt();
                    int q = in.nextInt();
                    TreeNode root = build(values);
                    System.out.println(lowestCommonAncestor(root, p, q));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                if not values or values[0] == 0:
                    return None
                slots = [None] * len(values)
                slots[0] = TreeNode(values[0])
                for index in range(1, len(values)):
                    if values[index] == 0:
                        continue
                    parent = slots[(index - 1) // 2]
                    if parent is None:
                        continue
                    node = TreeNode(values[index])
                    if index % 2 == 1:
                        parent.left = node
                    else:
                        parent.right = node
                    slots[index] = node
                return slots[0]


            def lowest_common_ancestor(root, p, q):
                node = root
                while node is not None:
                    if p < node.value and q < node.value:
                        node = node.left
                    elif p > node.value and q > node.value:
                        node = node.right
                    else:
                        return node.value
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                p = data[1 + n]
                q = data[2 + n]
                root = build(values)
                print(lowest_common_ancestor(root, p, q))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              if (values.length === 0 || values[0] === 0) {
                return null;
              }
              const slots = new Array(values.length).fill(null);
              slots[0] = { value: values[0], left: null, right: null };
              for (let i = 1; i < values.length; i += 1) {
                if (values[i] === 0) {
                  continue;
                }
                const parent = slots[Math.floor((i - 1) / 2)];
                if (parent === null) {
                  continue;
                }
                const node = { value: values[i], left: null, right: null };
                if (i % 2 === 1) {
                  parent.left = node;
                } else {
                  parent.right = node;
                }
                slots[i] = node;
              }
              return slots[0];
            }

            function lowestCommonAncestor(root, p, q) {
              let node = root;
              while (node !== null) {
                if (p < node.value && q < node.value) {
                  node = node.left;
                } else if (p > node.value && q > node.value) {
                  node = node.right;
                } else {
                  return node.value;
                }
              }
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const p = Number(data[1 + n]);
              const q = Number(data[2 + n]);
              const root = build(values);
              console.log(lowestCommonAncestor(root, p, q));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_lowest_common_ancestor, LCA_INPUT),
        judged_case(_lowest_common_ancestor, "7\n5 3 8 1 4 7 9\n3 8"),
        judged_case(_lowest_common_ancestor, "1\n5\n5 5"),
        judged_case(_lowest_common_ancestor, "3\n2 1 3\n1 1"),
        judged_case(_lowest_common_ancestor, "7\n5 3 8 1 4 7 9\n1 9", is_hidden=True),
        judged_case(_lowest_common_ancestor, "6\n20 10 30 5 15 25 35\n15 25", is_hidden=True),
        judged_case(_lowest_common_ancestor, "3\n9 4 13\n4 4", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Maximum root-to-leaf path sum
# --------------------------------------------------------------------------- #

PATH_SUM_INPUT = "7\n10 20 30 40 50 60 70"


def _max_path_sum(stdin: str) -> str:
    root = _build(_split(stdin)[0])

    def best(node: _Node | None) -> int:
        if node is None:
            return 0
        return node.value + max(best(node.left), best(node.right))

    return str(best(root))


MAX_PATH_SUM: dict[str, Any] = {
    "slug": "maximum-root-to-leaf-path-sum",
    "title": "Maximum Root to Leaf Path Sum",
    "summary": "Fold the best downward sum from each node up to the root.",
    "difficulty": "Hard",
    "topics": ["Trees", "Recursion", "Depth-First Search", "Dynamic Programming"],
    "description": (
        "You are given a binary tree in level order, with `0` marking an absent "
        "node. Every value is positive. Print the largest sum you can collect by "
        "following a single path from the root down to a leaf.\n\n"
        "A path must end at a leaf: a node with no children. You cannot stop early "
        "at an interior node and collect its value on top of a better subtree that "
        "you then refuse to finish."
    ),
    "input_format": (
        "Line 1: `n`, the number of level-order slots.\n"
        "Line 2: `n` integers, the values in level order, where `0` means the "
        "slot holds no node."
    ),
    "output_format": "Print the maximum sum of the values along a root-to-leaf path.",
    "constraints": (
        "1 <= n <= 10^5. Non-zero values are in 1..10^9, and the tree always has a "
        "root and at least one leaf."
    ),
    "examples": [
        {
            "input": PATH_SUM_INPUT,
            "output": _max_path_sum(PATH_SUM_INPUT),
            "explanation": "The four root-to-leaf paths sum to 70, 80, 100 and 110. The best is 10 + 30 + 70, since it takes the larger child 30 at the root and then the larger child 70.",
        }
    ],
    "hints": [
        "A global maximum that you update as you go wrong is tempting and almost always over-counts. Ask what a recursive call should return, rather than what it should print.",
        "Return the best sum reachable starting *at* this node and ending at some leaf below it. Then each call answers a self-contained question about its own subtree.",
        "From a node you can only go left or right, so the best downward sum is the node's value plus whichever child offers the larger sum.",
        "An absent child has no value to contribute, so its best sum is 0. That is what makes the single `max` line correct at a leaf, where exactly one child is absent.",
        "Because every value is positive, no special case is needed for negative numbers. If negatives were allowed, a node whose best sum went negative would have to be clamped to 0, which is the extra wrinkle this problem removes on purpose.",
    ],
    "explanation": (
        "The useful change of framing is to stop asking 'what is the best path in "
        "this tree' and start asking 'what is the best path that starts at this "
        "node'. The second question has a local answer, which is what makes it "
        "recursable.\n\n"
        "`best(node)` returns the largest sum along a path from `node` to a leaf "
        "beneath it. An absent node contributes 0. Otherwise a path from `node` "
        "must continue into exactly one child, so the answer is the node's value "
        "plus the larger of the two children's answers. At a leaf both children are "
        "absent and this naturally reduces to the node's own value.\n\n"
        "The result at the root is the answer, because every root-to-leaf path is "
        "root plus one of the paths the recursion considered. Each node is visited "
        "once for O(n) time, and the pending recursive calls occupy at most one "
        "frame per level of the tree, so the space is O(h)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(h)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    // Expand the level-order array into a tree. 0 means no node.
                    return null;
                }

                static long best(TreeNode node) {
                    // The largest sum along a path from node down to a leaf.
                    return 0L;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    TreeNode root = build(values);
                    System.out.println(best(root));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                # Expand the level-order array into a tree. 0 means no node.
                return None


            def best(node):
                # The largest sum along a path from node down to a leaf.
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                root = build(values)
                print(best(root))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              // Expand the level-order array into a tree. 0 means no node.
              return null;
            }

            function best(node) {
              // The largest sum along a path from node down to a leaf.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const root = build(values);
              console.log(best(root));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    if (values.length == 0 || values[0] == 0) {
                        return null;
                    }
                    TreeNode[] slots = new TreeNode[values.length];
                    slots[0] = new TreeNode(values[0]);
                    for (int i = 1; i < values.length; i += 1) {
                        if (values[i] == 0) {
                            continue;
                        }
                        TreeNode parent = slots[(i - 1) / 2];
                        if (parent == null) {
                            continue;
                        }
                        TreeNode node = new TreeNode(values[i]);
                        if (i % 2 == 1) {
                            parent.left = node;
                        } else {
                            parent.right = node;
                        }
                        slots[i] = node;
                    }
                    return slots[0];
                }

                static long best(TreeNode node) {
                    if (node == null) {
                        return 0L;
                    }
                    return node.value + Math.max(best(node.left), best(node.right));
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    TreeNode root = build(values);
                    System.out.println(best(root));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                if not values or values[0] == 0:
                    return None
                slots = [None] * len(values)
                slots[0] = TreeNode(values[0])
                for index in range(1, len(values)):
                    if values[index] == 0:
                        continue
                    parent = slots[(index - 1) // 2]
                    if parent is None:
                        continue
                    node = TreeNode(values[index])
                    if index % 2 == 1:
                        parent.left = node
                    else:
                        parent.right = node
                    slots[index] = node
                return slots[0]


            def best(node):
                if node is None:
                    return 0
                return node.value + max(best(node.left), best(node.right))


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                root = build(values)
                print(best(root))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              if (values.length === 0 || values[0] === 0) {
                return null;
              }
              const slots = new Array(values.length).fill(null);
              slots[0] = { value: values[0], left: null, right: null };
              for (let i = 1; i < values.length; i += 1) {
                if (values[i] === 0) {
                  continue;
                }
                const parent = slots[Math.floor((i - 1) / 2)];
                if (parent === null) {
                  continue;
                }
                const node = { value: values[i], left: null, right: null };
                if (i % 2 === 1) {
                  parent.left = node;
                } else {
                  parent.right = node;
                }
                slots[i] = node;
              }
              return slots[0];
            }

            function best(node) {
              if (node === null) {
                return 0;
              }
              return node.value + Math.max(best(node.left), best(node.right));
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const root = build(values);
              console.log(best(root));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_max_path_sum, PATH_SUM_INPUT),
        judged_case(_max_path_sum, "1\n7"),
        judged_case(_max_path_sum, "3\n1 2 3"),
        judged_case(_max_path_sum, "3\n5 9 3"),
        judged_case(_max_path_sum, "4\n3 5 2 1", is_hidden=True),
        judged_case(_max_path_sum, "7\n1 2 3 4 5 6 7", is_hidden=True),
        judged_case(_max_path_sum, "5\n100 50 60 55 65", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Is the tree a mirror image?
# --------------------------------------------------------------------------- #

SYMMETRY_INPUT = "3\n1 2 3"


def _symmetric(stdin: str) -> str:
    root = _build(_split(stdin)[0])

    def mirrored(left: _Node | None, right: _Node | None) -> bool:
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return (
            left.value == right.value
            and mirrored(left.left, right.right)
            and mirrored(left.right, right.left)
        )

    return "yes" if mirrored(root.left if root else None, root.right if root else None) else "no"


TREE_SYMMETRY: dict[str, Any] = {
    "slug": "check-tree-symmetry",
    "title": "Check Tree Symmetry",
    "summary": "Compare the left and right subtrees against each other, mirrored.",
    "difficulty": "Medium",
    "topics": ["Trees", "Recursion", "Depth-First Search"],
    "description": (
        "You are given a binary tree in level order, with `0` marking an absent "
        "node. Decide whether the tree is a mirror image of itself about its "
        "centre: the root itself must be ignored, its left subtree must be the "
        "mirror of its right subtree, and so on.\n\n"
        "Note that the comparison is mirrored. A node's left child is checked "
        "against the other side's *right* child, not its left."
    ),
    "input_format": (
        "Line 1: `n`, the number of level-order slots.\n"
        "Line 2: `n` integers, the values in level order, where `0` means the "
        "slot holds no node."
    ),
    "output_format": "Print `yes` if the tree is symmetric, otherwise `no`.",
    "constraints": "1 <= n <= 10^5. Non-zero values are in 1..10^9, and the tree always has a root.",
    "examples": [
        {
            "input": SYMMETRY_INPUT,
            "output": _symmetric(SYMMETRY_INPUT),
            "explanation": "The left child 2 and the right child 3 are different, so the mirror fails immediately.",
        },
        {
            "input": "7\n1 2 2 3 3 0 0",
            "output": _symmetric("7\n1 2 2 3 3 0 0"),
            "explanation": "Both sides have a node 2 with children 3 and 3, and 3's opposite partners are both absent, so every mirrored pair agrees.",
        },
    ],
    "hints": [
        "Comparing the tree with a copy of itself stored somewhere is a way to solve it, but it doubles the memory and adds a data structure the problem never mentions. Is there anything in the tree to compare against?",
        "The root is trivially symmetric with itself, so it carries no information. The whole question is whether its left and right subtrees are each other's mirror.",
        "Write one helper that takes two nodes and answers whether they are mirrors of each other. Then the top-level answer is that helper applied to the root's two children.",
        "The recursion must cross over: `a`'s left child faces `b`'s right child, and `a`'s right child faces `b`'s left child. Comparing left to left is the bug that makes the function accept every tree whose two subtrees are identical.",
        "Three exit cases, in order: both absent is symmetric, exactly one absent is not, and both present must match on value and on both mirrored children. Handling the 'both absent' case before touching any field is what keeps the null checks from dereferencing null.",
    ],
    "explanation": (
        "A tree is symmetric when reflecting it left to right leaves it unchanged. "
        "The reflection fixes the root and swaps the two subtrees, so the problem "
        "reduces to asking whether those two subtrees are mirrors of each other.\n\n"
        "`mirrored(a, b)` answers that for one pair of nodes. Both absent means the "
        "reflections agree. Exactly one absent means they differ, because a node "
        "cannot reflect into nothing. Both present requires equal values and, "
        "crucially, crosswise recursion: `a`'s left child against `b`'s right child, "
        "and `a`'s right child against `b`'s left child. That crossing is what a "
        "reflection actually does.\n\n"
        "Each node is visited once, so the time is O(n). The recursion holds one "
        "pair of pending comparisons per level, so the space is O(h) rather than "
        "the O(n) a stored copy would cost."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n)",
    "expected_space_complexity": "O(h)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    // Expand the level-order array into a tree. 0 means no node.
                    return null;
                }

                static boolean mirrored(TreeNode a, TreeNode b) {
                    // Are these two subtrees reflections of each other?
                    return true;
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    TreeNode root = build(values);
                    boolean ok = root != null && mirrored(root.left, root.right);
                    System.out.println(ok ? "yes" : "no");
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                # Expand the level-order array into a tree. 0 means no node.
                return None


            def mirrored(a, b):
                # Are these two subtrees reflections of each other?
                return True


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                root = build(values)
                print("yes" if root is not None and mirrored(root.left, root.right) else "no")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              // Expand the level-order array into a tree. 0 means no node.
              return null;
            }

            function mirrored(a, b) {
              // Are these two subtrees reflections of each other?
              return true;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const root = build(values);
              const ok = root !== null && mirrored(root.left, root.right);
              console.log(ok ? "yes" : "no");
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.util.Scanner;

            public class Main {
                static class TreeNode {
                    int value;
                    TreeNode left;
                    TreeNode right;

                    TreeNode(int value) {
                        this.value = value;
                    }
                }

                static TreeNode build(int[] values) {
                    if (values.length == 0 || values[0] == 0) {
                        return null;
                    }
                    TreeNode[] slots = new TreeNode[values.length];
                    slots[0] = new TreeNode(values[0]);
                    for (int i = 1; i < values.length; i += 1) {
                        if (values[i] == 0) {
                            continue;
                        }
                        TreeNode parent = slots[(i - 1) / 2];
                        if (parent == null) {
                            continue;
                        }
                        TreeNode node = new TreeNode(values[i]);
                        if (i % 2 == 1) {
                            parent.left = node;
                        } else {
                            parent.right = node;
                        }
                        slots[i] = node;
                    }
                    return slots[0];
                }

                static boolean mirrored(TreeNode a, TreeNode b) {
                    if (a == null && b == null) {
                        return true;
                    }
                    if (a == null || b == null) {
                        return false;
                    }
                    return a.value == b.value
                            && mirrored(a.left, b.right)
                            && mirrored(a.right, b.left);
                }

                public static void main(String[] args) {
                    Scanner in = new Scanner(System.in);
                    int n = in.nextInt();
                    int[] values = new int[n];
                    for (int i = 0; i < n; i += 1) {
                        values[i] = in.nextInt();
                    }
                    TreeNode root = build(values);
                    boolean ok = root != null && mirrored(root.left, root.right);
                    System.out.println(ok ? "yes" : "no");
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            class TreeNode:
                def __init__(self, value):
                    self.value = value
                    self.left = None
                    self.right = None


            def build(values):
                if not values or values[0] == 0:
                    return None
                slots = [None] * len(values)
                slots[0] = TreeNode(values[0])
                for index in range(1, len(values)):
                    if values[index] == 0:
                        continue
                    parent = slots[(index - 1) // 2]
                    if parent is None:
                        continue
                    node = TreeNode(values[index])
                    if index % 2 == 1:
                        parent.left = node
                    else:
                        parent.right = node
                    slots[index] = node
                return slots[0]


            def mirrored(a, b):
                if a is None and b is None:
                    return True
                if a is None or b is None:
                    return False
                return (
                    a.value == b.value
                    and mirrored(a.left, b.right)
                    and mirrored(a.right, b.left)
                )


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n = data[0]
                values = data[1 : 1 + n]
                root = build(values)
                print("yes" if root is not None and mirrored(root.left, root.right) else "no")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function build(values) {
              if (values.length === 0 || values[0] === 0) {
                return null;
              }
              const slots = new Array(values.length).fill(null);
              slots[0] = { value: values[0], left: null, right: null };
              for (let i = 1; i < values.length; i += 1) {
                if (values[i] === 0) {
                  continue;
                }
                const parent = slots[Math.floor((i - 1) / 2)];
                if (parent === null) {
                  continue;
                }
                const node = { value: values[i], left: null, right: null };
                if (i % 2 === 1) {
                  parent.left = node;
                } else {
                  parent.right = node;
                }
                slots[i] = node;
              }
              return slots[0];
            }

            function mirrored(a, b) {
              if (a === null && b === null) {
                return true;
              }
              if (a === null || b === null) {
                return false;
              }
              return (
                a.value === b.value &&
                mirrored(a.left, b.right) &&
                mirrored(a.right, b.left)
              );
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const values = data.slice(1, 1 + n).map(Number);
              const root = build(values);
              const ok = root !== null && mirrored(root.left, root.right);
              console.log(ok ? "yes" : "no");
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_symmetric, SYMMETRY_INPUT),
        judged_case(_symmetric, "1\n1"),
        judged_case(_symmetric, "7\n1 2 2 3 3 0 0"),
        judged_case(_symmetric, "5\n1 2 2 0 3"),
        judged_case(_symmetric, "4\n1 2 3 4", is_hidden=True),
        judged_case(_symmetric, "7\n5 3 8 1 4 7 9", is_hidden=True),
        judged_case(_symmetric, "9\n1 2 2 3 3 0 0 0 0", is_hidden=True),
    ],
}


TREES_PROBLEMS: list[dict[str, Any]] = [
    BST_VALID,
    LOWEST_COMMON_ANCESTOR,
    MAX_PATH_SUM,
    TREE_SYMMETRY,
]

__all__ = ["TREES_PROBLEMS"]