"""Graphs: reachability, order, and the walks that cost more than a traversal.

Nine problems over graphs given as edge lists or as a grid. Nodes are numbered
from `0`, and the hard ones -- critical path, Bellman-Ford, and Kruskal --
deliberately share the same groundwork as the easy one so the difference between
"visit each vertex once" and "accumulate a weight along the way" is visible in
the code.

Every output that could have more than one right answer is made unique by the
statement rather than left to the judge: the topological order always takes the
smallest available node, so a correct program has exactly one output to print.
A judge case with several acceptable answers needs special comparison logic
that a text judge does not have, so the problems avoid needing one.
"""

from __future__ import annotations

import heapq
from collections import deque
from typing import Any

from database.problem_spec import (
    int_rows,
    int_tokens,
    judged_case,
    source,
    text_lines,
)


def _undirected(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    adjacency: list[list[int]] = [[] for _ in range(n)]
    for left, right in edges:
        adjacency[left].append(right)
        adjacency[right].append(left)
    return adjacency


# --------------------------------------------------------------------------- #
# How many separate pieces is this graph?
# --------------------------------------------------------------------------- #

COMPONENTS_INPUT = "6 4\n0 1\n2 3\n4 5\n1 2"


def _components(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m = tokens[0], tokens[1]
    edges = [(tokens[2 + 2 * i], tokens[3 + 2 * i]) for i in range(m)]
    adjacency = _undirected(n, edges)
    visited = [False] * n
    groups = 0
    for start in range(n):
        if visited[start]:
            continue
        groups += 1
        visited[start] = True
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbour in adjacency[node]:
                if not visited[neighbour]:
                    visited[neighbour] = True
                    stack.append(neighbour)
    return str(groups)


CONNECTED_COMPONENTS: dict[str, Any] = {
    "slug": "count-connected-components",
    "title": "Count Connected Components",
    "summary": "Count the groups of nodes that can all reach one another.",
    "difficulty": "Easy",
    "topics": ["Graphs", "Depth-First Search", "Breadth-First Search", "Union Find"],
    "description": (
        "You are given an undirected graph with nodes numbered `0` to `n - 1`. Two "
        "nodes are in the same component when one can be reached from the other by "
        "following edges. Count how many components the graph has.\n\n"
        "An isolated node is a component of its own. Self-loops and repeated edges "
        "are permitted and never change the answer."
    ),
    "input_format": (
        "Line 1: `n m`, the number of nodes and edges.\n"
        "The next `m` lines each contain `u v`, an undirected edge."
    ),
    "output_format": "Print the number of connected components.",
    "constraints": (
        "1 <= n <= 10^5, 0 <= m <= 2 * 10^5, and 0 <= u, v < n. The graph is not "
        "required to be connected."
    ),
    "examples": [
        {
            "input": COMPONENTS_INPUT,
            "output": _components(COMPONENTS_INPUT),
            "explanation": "The edges form the chain 0-1-2-3 and the pair 4-5, so there are two pieces.",
        }
    ],
    "hints": [
        "Starting a fresh search from a node you have not seen is how components get counted. What is the invariant that stops you from starting a second search inside a component you are already exploring?",
        "Mark a node visited the moment you put it on the stack or the queue, not when you take it off. Marking on the way out lets the same node be queued twice.",
        "Outer loop over every node: if it is unvisited, a new component begins, so increment the counter and flood the whole component from there.",
        "Both a stack and a queue find the components correctly. The difference is only the order the nodes come out in, and here that order is never printed.",
        "A union-find solves this too, and it is the better choice if more edges arrive afterwards. For a static graph read all at once, a flood fill is simpler and needs no array of parents.",
    ],
    "explanation": (
        "A flood fill from any unvisited node reaches exactly the nodes of that "
        "one component, and never leaves it, because every edge it follows stays "
        "inside a component by definition. So the outer loop's first unvisited node "
        "always begins a component nobody has counted yet.\n\n"
        "The implementation marks nodes visited as they are pushed, which "
        "guarantees each node is pushed once and keeps the total work linear. With "
        "that in place, the outer loop runs once per component, incrementing the "
        "answer each time it finds a node nobody has reached.\n\n"
        "Every node is pushed once and every edge is looked at twice, so the time "
        "is O(n + m). The visited array is O(n) and the stack holds at most O(n) "
        "nodes."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n + m)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayList;
            import java.util.List;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int sign = 1;
                        if (c == '-') {
                            sign = -1;
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value * sign;
                    }
                }

                static int countComponents(int n, List<int[]>[] edges) {
                    // Return how many groups of mutually reachable nodes there are.
                    return 0;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] edges = new List[n];
                    for (int i = 0; i < n; i++) {
                        edges[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int u = in.nextInt();
                        int v = in.nextInt();
                        edges[u].add(new int[] { v, 0 });
                        edges[v].add(new int[] { u, 0 });
                    }
                    System.out.println(countComponents(n, edges));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def count_components(n, adjacency):
                # Return how many groups of mutually reachable nodes there are.
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    u, v = data[2 + 2 * i], data[3 + 2 * i]
                    adjacency[u].append(v)
                    adjacency[v].append(u)
                print(count_components(n, adjacency))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countComponents(n, adjacency) {
              // Return how many groups of mutually reachable nodes there are.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const u = Number(data[2 + 2 * i]);
                const v = Number(data[3 + 2 * i]);
                adjacency[u].push(v);
                adjacency[v].push(u);
              }
              console.log(countComponents(n, adjacency));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.ArrayList;
            import java.util.Arrays;
            import java.util.Deque;
            import java.util.List;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int sign = 1;
                        if (c == '-') {
                            sign = -1;
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value * sign;
                    }
                }

                static int countComponents(int n, List<int[]>[] adjacency) {
                    boolean[] visited = new boolean[n];
                    int groups = 0;
                    int[] stack = new int[n];
                    for (int start = 0; start < n; start += 1) {
                        if (visited[start]) {
                            continue;
                        }
                        groups += 1;
                        int top = 0;
                        stack[top++] = start;
                        visited[start] = true;
                        while (top > 0) {
                            int node = stack[--top];
                            for (int[] edge : adjacency[node]) {
                                int neighbour = edge[0];
                                if (!visited[neighbour]) {
                                    visited[neighbour] = true;
                                    stack[top++] = neighbour;
                                }
                            }
                        }
                    }
                    return groups;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int u = in.nextInt();
                        int v = in.nextInt();
                        adjacency[u].add(new int[] { v, 0 });
                        adjacency[v].add(new int[] { u, 0 });
                    }
                    System.out.println(countComponents(n, adjacency));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def count_components(n, adjacency):
                visited = [False] * n
                groups = 0
                for start in range(n):
                    if visited[start]:
                        continue
                    groups += 1
                    visited[start] = True
                    stack = [start]
                    while stack:
                        node = stack.pop()
                        for neighbour in adjacency[node]:
                            if not visited[neighbour]:
                                visited[neighbour] = True
                                stack.append(neighbour)
                return groups


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    u, v = data[2 + 2 * i], data[3 + 2 * i]
                    adjacency[u].append(v)
                    adjacency[v].append(u)
                print(count_components(n, adjacency))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countComponents(n, adjacency) {
              const visited = new Array(n).fill(false);
              let groups = 0;
              for (let start = 0; start < n; start += 1) {
                if (visited[start]) {
                  continue;
                }
                groups += 1;
                visited[start] = true;
                const stack = [start];
                while (stack.length > 0) {
                  const node = stack.pop();
                  for (const neighbour of adjacency[node]) {
                    if (!visited[neighbour]) {
                      visited[neighbour] = true;
                      stack.push(neighbour);
                    }
                  }
                }
              }
              return groups;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const u = Number(data[2 + 2 * i]);
                const v = Number(data[3 + 2 * i]);
                adjacency[u].push(v);
                adjacency[v].push(u);
              }
              console.log(countComponents(n, adjacency));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_components, COMPONENTS_INPUT),
        judged_case(_components, "3 0"),
        judged_case(_components, "1 0"),
        judged_case(_components, "4 1\n0 0"),
        judged_case(_components, "7 5\n0 1\n1 2\n3 4\n4 5\n5 3", is_hidden=True),
        judged_case(_components, "5 6\n0 1\n1 2\n2 0\n3 4\n4 3\n0 3", is_hidden=True),
        judged_case(_components, "9 3\n0 8\n1 7\n2 6", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Shortest path across an open grid
# --------------------------------------------------------------------------- #

GRID_INPUT = "3 3\n...\n...\n..."


def _grid_path(stdin: str) -> str:
    lines = text_lines(stdin)
    header = lines[0].split()
    rows, cols = int(header[0]), int(header[1])
    grid = lines[1 : 1 + rows]
    if grid[0][0] == "#" or grid[rows - 1][cols - 1] == "#":
        return "-1"
    distance = [[-1] * cols for _ in range(rows)]
    distance[0][0] = 0
    queue = deque([(0, 0)])
    while queue:
        row, col = queue.popleft()
        if row == rows - 1 and col == cols - 1:
            return str(distance[row][col])
        for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_row, next_col = row + delta_row, col + delta_col
            if not (0 <= next_row < rows and 0 <= next_col < cols):
                continue
            if grid[next_row][next_col] == "#" or distance[next_row][next_col] != -1:
                continue
            distance[next_row][next_col] = distance[row][col] + 1
            queue.append((next_row, next_col))
    return "-1"


SHORTEST_GRID_PATH: dict[str, Any] = {
    "slug": "shortest-path-in-a-grid",
    "title": "Shortest Path in a Grid",
    "summary": "Find the fewest steps from the top-left to the bottom-right cell.",
    "difficulty": "Medium",
    "topics": ["Graphs", "Breadth-First Search", "Queues"],
    "description": (
        "You are given a grid of `.` for open cell and `#` for wall. From the "
        "top-left cell you may move one cell up, down, left or right, but never "
        "into a wall or off the grid. Find the fewest moves needed to reach the "
        "bottom-right cell.\n\n"
        "The start and the target are both open. If the target cannot be reached, "
        "print -1."
    ),
    "input_format": (
        "Line 1: `rows cols`.\n"
        "The next `rows` lines each contain exactly `cols` characters, either `.` "
        "or `#`, with no spaces between them."
    ),
    "output_format": "Print the minimum number of moves from the top-left to the bottom-right cell, or -1 if unreachable.",
    "constraints": "1 <= rows, cols <= 1000 and both start and target cells are `.`.",
    "examples": [
        {
            "input": GRID_INPUT,
            "output": _grid_path(GRID_INPUT),
            "explanation": "Four moves: two right and two down.",
        },
        {
            "input": "3 3\n.#.\n...\n..#",
            "output": _grid_path("3 3\n.#.\n...\n..#"),
            "explanation": "Going straight down and right is blocked, so the path has to detour and takes six moves.",
        },
    ],
    "hints": [
        "Trying every path fails because the number of paths is exponential. What property of a single move lets you discard most of the possibilities?",
        "Every move costs exactly one, so the problem is unweighted. That means a breadth-first search visits candidates in order of how many moves they took, and the first time it reaches a cell is already the best answer for that cell.",
        "Keep a distance grid initialised to -1, meaning unvisited. Set the start to 0, push it on a queue, and whenever you move into a cell, record its distance as the current cell's distance plus one.",
        "Mark a cell visited as soon as it is queued. If you wait until it is dequeued, the same cell can enter the queue from two directions and be explored twice.",
        "You can return the moment you dequeue the target rather than searching the whole grid. By then every cell dequeued earlier had a smaller distance, so nothing better is waiting behind it.",
    ],
    "explanation": (
        "Treat each open cell as a vertex whose edges are the legal single moves. "
        "Every edge has cost one, which is the condition that makes breadth-first "
        "search correct: it processes the frontier in non-decreasing distance from "
        "the start, so the first time a cell is reached its distance is final.\n\n"
        "A distance grid of -1 doubles as the visited set. The start is marked 0 and "
        "queued; each dequeue looks at the four neighbours, and any open, unvisited "
        "neighbour is marked with one more than the current distance and queued. "
        "Because cells are marked on the way in, no cell is ever queued twice.\n\n"
        "Returning when the target is dequeued is safe: any shorter path would have "
        "had all of its cells dequeued before the target. Each cell is queued at "
        "most once and each dequeue checks four neighbours, so the time is "
        "O(rows * cols) and the distance grid plus the queue use O(rows * cols)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(rows * cols)",
    "expected_space_complexity": "O(rows * cols)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.Deque;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }

                    String next() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        StringBuilder text = new StringBuilder();
                        while (c > ' ') {
                            text.append((char) c);
                            c = read();
                        }
                        return text.toString();
                    }
                }

                static int shortestPath(char[][] grid) {
                    // Minimum moves from the top-left to the bottom-right, or -1.
                    return -1;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int rows = in.nextInt();
                    int cols = in.nextInt();
                    char[][] grid = new char[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        String line = in.next();
                        for (int c = 0; c < cols; c += 1) {
                            grid[r][c] = line.charAt(c);
                        }
                    }
                    System.out.println(shortestPath(grid));
                }
            }
            """
        ),
        "python": source(
            """
            import sys
            from collections import deque


            def shortest_path(grid, rows, cols):
                # Minimum moves from the top-left to the bottom-right, or -1.
                return -1


            def main():
                lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
                rows, cols = (int(value) for value in lines[0].split())
                grid = lines[1 : 1 + rows]
                print(shortest_path(grid, rows, cols))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function shortestPath(grid, rows, cols) {
              // Minimum moves from the top-left to the bottom-right, or -1.
              return -1;
            }

            function main() {
              const lines = fs.readFileSync(0, "utf8").split(/\\s*\\n/).filter((line) => line.trim() !== "");
              const [rows, cols] = lines[0].trim().split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows);
              console.log(shortestPath(grid, rows, cols));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.Arrays;
            import java.util.Deque;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }

                    String next() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        StringBuilder text = new StringBuilder();
                        while (c > ' ') {
                            text.append((char) c);
                            c = read();
                        }
                        return text.toString();
                    }
                }

                static int shortestPath(char[][] grid) {
                    int rows = grid.length;
                    int cols = grid[0].length;
                    int[][] distance = new int[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        Arrays.fill(distance[r], -1);
                    }
                    Deque<int[]> queue = new ArrayDeque<>();
                    distance[0][0] = 0;
                    queue.add(new int[] { 0, 0 });
                    int[] deltas = { 1, 0, -1, 0, 0, 1, 0, -1 };
                    while (!queue.isEmpty()) {
                        int[] cell = queue.poll();
                        int row = cell[0];
                        int col = cell[1];
                        if (row == rows - 1 && col == cols - 1) {
                            return distance[row][col];
                        }
                        for (int step = 0; step < 4; step += 1) {
                            int nextRow = row + deltas[step * 2];
                            int nextCol = col + deltas[step * 2 + 1];
                            if (nextRow < 0 || nextRow >= rows || nextCol < 0 || nextCol >= cols) {
                                continue;
                            }
                            if (grid[nextRow][nextCol] == '#' || distance[nextRow][nextCol] != -1) {
                                continue;
                            }
                            distance[nextRow][nextCol] = distance[row][col] + 1;
                            queue.add(new int[] { nextRow, nextCol });
                        }
                    }
                    return -1;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int rows = in.nextInt();
                    int cols = in.nextInt();
                    char[][] grid = new char[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        String line = in.next();
                        for (int c = 0; c < cols; c += 1) {
                            grid[r][c] = line.charAt(c);
                        }
                    }
                    System.out.println(shortestPath(grid));
                }
            }
            """
        ),
        "python": source(
            """
            import sys
            from collections import deque


            def shortest_path(grid, rows, cols):
                distance = [[-1] * cols for _ in range(rows)]
                distance[0][0] = 0
                queue = deque([(0, 0)])
                while queue:
                    row, col = queue.popleft()
                    if row == rows - 1 and col == cols - 1:
                        return distance[row][col]
                    for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        next_row, next_col = row + delta_row, col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if grid[next_row][next_col] == "#" or distance[next_row][next_col] != -1:
                            continue
                        distance[next_row][next_col] = distance[row][col] + 1
                        queue.append((next_row, next_col))
                return -1


            def main():
                lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
                rows, cols = (int(value) for value in lines[0].split())
                grid = lines[1 : 1 + rows]
                print(shortest_path(grid, rows, cols))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function shortestPath(grid, rows, cols) {
              const distance = Array.from({ length: rows }, () => new Array(cols).fill(-1));
              const queue = [[0, 0]];
              distance[0][0] = 0;
              while (queue.length > 0) {
                const [row, col] = queue.shift();
                if (row === rows - 1 && col === cols - 1) {
                  return distance[row][col];
                }
                const deltas = [
                  [1, 0],
                  [-1, 0],
                  [0, 1],
                  [0, -1],
                ];
                for (const [deltaRow, deltaCol] of deltas) {
                  const nextRow = row + deltaRow;
                  const nextCol = col + deltaCol;
                  if (nextRow < 0 || nextRow >= rows || nextCol < 0 || nextCol >= cols) {
                    continue;
                  }
                  if (grid[nextRow][nextCol] === "#" || distance[nextRow][nextCol] !== -1) {
                    continue;
                  }
                  distance[nextRow][nextCol] = distance[row][col] + 1;
                  queue.push([nextRow, nextCol]);
                }
              }
              return -1;
            }

            function main() {
              const lines = fs.readFileSync(0, "utf8").split(/\\s*\\n/).filter((line) => line.trim() !== "");
              const [rows, cols] = lines[0].trim().split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows);
              console.log(shortestPath(grid, rows, cols));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_grid_path, GRID_INPUT),
        judged_case(_grid_path, "1 1\n."),
        judged_case(_grid_path, "2 2\n..\n.."),
        judged_case(_grid_path, "3 3\n.#.\n...\n..#"),
        judged_case(_grid_path, "3 3\n.#.\n###\n...", is_hidden=True),
        judged_case(_grid_path, "4 4\n....\n.##.\n.##.\n....", is_hidden=True),
        judged_case(_grid_path, "5 5\n.....\n.###.\n.###.\n.###.\n.....", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# A canonical topological order
# --------------------------------------------------------------------------- #

TOPOLOGICAL_INPUT = "6 6\n5 2\n5 0\n4 0\n4 1\n2 3\n3 1"


def _topological(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m = tokens[0], tokens[1]
    adjacency: list[list[int]] = [[] for _ in range(n)]
    indegree = [0] * n
    for i in range(m):
        before, after = tokens[2 + 2 * i], tokens[3 + 2 * i]
        adjacency[before].append(after)
        indegree[after] += 1
    ready = [node for node in range(n) if indegree[node] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for after in adjacency[node]:
            indegree[after] -= 1
            if indegree[after] == 0:
                heapq.heappush(ready, after)
    if len(order) != n:
        return "cycle"
    return " ".join(str(node) for node in order)


TOPOLOGICAL_ORDER: dict[str, Any] = {
    "slug": "canonical-topological-order",
    "title": "Canonical Topological Order",
    "summary": "Order the nodes so every prerequisite comes first, or report a cycle.",
    "difficulty": "Medium",
    "topics": ["Graphs", "Topological Sort", "Breadth-First Search", "Heaps"],
    "description": (
        "You are given a directed graph with nodes `0` to `n - 1`, where an edge "
        "`u -> v` means `u` must come before `v`. Produce an ordering of the nodes "
        "in which every edge points forwards.\n\n"
        "To make the answer unique, repeatedly take the smallest-indexed node that "
        "still has no unmet prerequisite. If no ordering exists because the graph "
        "contains a cycle, print `cycle`.\n\n"
        "Self-loops are not permitted, and the same edge may appear more than once."
    ),
    "input_format": (
        "Line 1: `n m`, the number of nodes and edges.\n"
        "The next `m` lines each contain `before after`, a directed edge."
    ),
    "output_format": (
        "Print the `n` node indices in a valid order separated by single spaces, or "
        "`cycle` if no valid ordering exists."
    ),
    "constraints": "1 <= n <= 10^5, 0 <= m <= 2 * 10^5, 0 <= before, after < n, and no self-loops.",
    "examples": [
        {
            "input": TOPOLOGICAL_INPUT,
            "output": _topological(TOPOLOGICAL_INPUT),
            "explanation": "Only 4 and 5 start with no prerequisites, so 4 goes first; each step then takes the smallest index available.",
        }
    ],
    "hints": [
        "A valid order only requires that a node appears after everything pointing at it. What do you need to know about a node to know whether it is safe to place yet?",
        "Track each node's number of incoming edges from nodes not yet emitted. That count is the node's remaining prerequisite count, and a node is available when the count reaches zero.",
        "Emit a node, then decrement the count of each node it points at. Any count that hits zero becomes available. This is Kahn's algorithm.",
        "If the loop stops with nodes still unemitted, the remaining subgraph must contain a cycle: every node in it still has an unmet incoming edge from within the group.",
        "To always emit the smallest available index, the available set has to be a priority queue or a sorted structure. A plain list and a scan for the minimum also work, but a min-heap keeps it O(m log n).",
    ],
    "explanation": (
        "Maintain an incoming-edge count per node and treat it as the number of "
        "prerequisites still outstanding. A node may be placed exactly when that "
        "count is zero, because every node that must precede it has already been "
        "placed.\n\n"
        "Emitting a node satisfies one prerequisite of each node it points at, so "
        "those counts are decremented and any that reach zero join the available "
        "set. Keeping that set as a min-heap makes 'smallest available index' a "
        "single operation, and because the choice at each step is fully determined, "
        "the output is the same on every run and in every language -- which is what "
        "makes it judgeable as plain text.\n\n"
        "If the loop ends having emitted fewer than `n` nodes, the leftover nodes "
        "each still have an unmet prerequisite among the leftovers. Following those "
        "prerequisites must eventually revisit a node, which is a cycle, so no "
        "ordering exists.\n\n"
        "Every node is emitted at most once and every edge is decremented once, "
        "giving O(m + n log n) time and O(n + m) space."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(m + n log n)",
    "expected_space_complexity": "O(n + m)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayList;
            import java.util.List;
            import java.util.PriorityQueue;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static String topologicalOrder(int n, List<int[]>[] adjacency) {
                    // Space-separated node order, or "cycle".
                    return "";
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int before = in.nextInt();
                        int after = in.nextInt();
                        adjacency[before].add(new int[] { after, 0 });
                    }
                    System.out.println(topologicalOrder(n, adjacency));
                }
            }
            """
        ),
        "python": source(
            """
            import heapq
            import sys


            def topological_order(n, adjacency):
                # Space-separated node order, or "cycle".
                return ""


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    before, after = data[2 + 2 * i], data[3 + 2 * i]
                    adjacency[before].append(after)
                print(topological_order(n, adjacency))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function topologicalOrder(n, adjacency) {
              // Space-separated node order, or "cycle".
              return "";
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const before = Number(data[2 + 2 * i]);
                const after = Number(data[3 + 2 * i]);
                adjacency[before].push(after);
              }
              console.log(topologicalOrder(n, adjacency));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayList;
            import java.util.List;
            import java.util.PriorityQueue;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static String topologicalOrder(int n, List<int[]>[] adjacency) {
                    int[] remaining = new int[n];
                    PriorityQueue<Integer> ready = new PriorityQueue<>();
                    for (int node = 0; node < n; node += 1) {
                        for (int[] edge : adjacency[node]) {
                            remaining[edge[0]] += 1;
                        }
                    }
                    for (int node = 0; node < n; node += 1) {
                        if (remaining[node] == 0) {
                            ready.add(node);
                        }
                    }
                    StringBuilder order = new StringBuilder();
                    int placed = 0;
                    while (!ready.isEmpty()) {
                        int node = ready.poll();
                        if (placed > 0) {
                            order.append(' ');
                        }
                        order.append(node);
                        placed += 1;
                        for (int[] edge : adjacency[node]) {
                            int after = edge[0];
                            remaining[after] -= 1;
                            if (remaining[after] == 0) {
                                ready.add(after);
                            }
                        }
                    }
                    if (placed != n) {
                        return "cycle";
                    }
                    return order.toString();
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int before = in.nextInt();
                        int after = in.nextInt();
                        adjacency[before].add(new int[] { after, 0 });
                    }
                    System.out.println(topologicalOrder(n, adjacency));
                }
            }
            """
        ),
        "python": source(
            """
            import heapq
            import sys


            def topological_order(n, adjacency):
                remaining = [0] * n
                for node in range(n):
                    for after in adjacency[node]:
                        remaining[after] += 1
                ready = [node for node in range(n) if remaining[node] == 0]
                heapq.heapify(ready)
                order = []
                while ready:
                    node = heapq.heappop(ready)
                    order.append(node)
                    for after in adjacency[node]:
                        remaining[after] -= 1
                        if remaining[after] == 0:
                            heapq.heappush(ready, after)
                if len(order) != n:
                    return "cycle"
                return " ".join(str(node) for node in order)


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    before, after = data[2 + 2 * i], data[3 + 2 * i]
                    adjacency[before].append(after)
                print(topological_order(n, adjacency))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function topologicalOrder(n, adjacency) {
              const remaining = new Array(n).fill(0);
              for (let node = 0; node < n; node += 1) {
                for (const after of adjacency[node]) {
                  remaining[after] += 1;
                }
              }
              const ready = [];
              for (let node = 0; node < n; node += 1) {
                if (remaining[node] === 0) {
                  ready.push(node);
                }
              }
              const order = [];
              while (ready.length > 0) {
                ready.sort((a, b) => a - b);
                const node = ready.shift();
                order.push(node);
                for (const after of adjacency[node]) {
                  remaining[after] -= 1;
                  if (remaining[after] === 0) {
                    ready.push(after);
                  }
                }
              }
              if (order.length !== n) {
                return "cycle";
              }
              return order.join(" ");
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const before = Number(data[2 + 2 * i]);
                const after = Number(data[3 + 2 * i]);
                adjacency[before].push(after);
              }
              console.log(topologicalOrder(n, adjacency));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_topological, TOPOLOGICAL_INPUT),
        judged_case(_topological, "1 0"),
        judged_case(_topological, "3 2\n0 1\n1 2"),
        judged_case(_topological, "2 1\n1 0"),
        judged_case(_topological, "4 2\n0 1\n0 1", is_hidden=True),
        judged_case(_topological, "3 1\n1 1", is_hidden=True),
        judged_case(_topological, "5 3\n3 1\n2 4\n0 2", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Critical path in a project graph
# --------------------------------------------------------------------------- #

CRITICAL_INPUT = "5 6\n0 1 3\n0 2 2\n1 3 4\n2 3 1\n3 4 5\n2 4 9\n1 2"


def _critical_path(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m = tokens[0], tokens[1]
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for i in range(m):
        u, v, w = tokens[2 + 3 * i], tokens[3 + 3 * i], tokens[4 + 3 * i]
        adjacency[u].append((v, w))
    cursor = 2 + 3 * m
    count = tokens[cursor]
    sources = tokens[cursor + 1 : cursor + 1 + count]

    indegree = [0] * n
    for node in range(n):
        for after, _ in adjacency[node]:
            indegree[after] += 1
    ready = [node for node in range(n) if indegree[node] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for after, _ in adjacency[node]:
            indegree[after] -= 1
            if indegree[after] == 0:
                heapq.heappush(ready, after)

    best = [-1] * n
    for start in sources:
        best[start] = 0
    for node in order:
        if best[node] < 0:
            continue
        for after, weight in adjacency[node]:
            best[after] = max(best[after], best[node] + weight)
    return str(max(best))


CRITICAL_PATH: dict[str, Any] = {
    "slug": "critical-path-in-a-project-graph",
    "title": "Critical Path in a Project Graph",
    "summary": "Find the heaviest total weight along a dependency chain.",
    "difficulty": "Hard",
    "topics": ["Graphs", "Topological Sort", "Dynamic Programming", "Breadth-First Search"],
    "description": (
        "A project is a directed acyclic graph whose edges are weighted tasks: an "
        "edge `u -> v` with weight `w` means task `v` takes `w` units of time and "
        "cannot begin until `u` finishes. Several tasks start at time zero, given "
        "as a list of source nodes.\n\n"
        "Print the largest total weight of a dependency chain starting from any of "
        "those sources. That is how long the project takes when every task runs as "
        "early as possible."
    ),
    "input_format": (
        "Line 1: `n m`, the number of tasks and dependencies.\n"
        "The next `m` lines each contain `before after weight`.\n"
        "The next line contains `k`, then the `k` source task indices on the same "
        "line."
    ),
    "output_format": "Print the maximum total weight of a dependency chain starting at any listed source.",
    "constraints": (
        "1 <= n <= 10^5, 0 <= m <= 2 * 10^5, 1 <= k <= n, and every weight is in "
        "1..10^6. The graph is guaranteed to be acyclic."
    ),
    "examples": [
        {
            "input": CRITICAL_INPUT,
            "output": _critical_path(CRITICAL_INPUT),
            "explanation": "Two chains start at task 2: 2 -> 4 gives 9, and 2 -> 3 -> 4 gives 1 + 5 = 6. The longest is 9.",
        }
    ],
    "hints": [
        "This is a longest-path question, and longest path is only tractable because the graph is acyclic. What does acyclicity guarantee about the order you can process tasks in?",
        "Compute a topological order first, then answer the question as a forward pass over that order. Every edge goes from an earlier task to a later one, so a task's answer is final before you need it.",
        "Keep one number per task: the largest total weight of a chain that ends at that task. Sources start at 0 and every other task starts at -1, meaning unreachable.",
        "For each edge `u -> v` with weight `w`, the candidate for `v` is `best[u] + w`. Take the maximum over all incoming edges, and skip `u` entirely when `best[u]` is still -1.",
        "Notice that this is a shortest-path algorithm with `min` replaced by `max`, and it works only because there are no cycles to loop forever. Reaching for Dijkstra here is the natural mistake and it cannot terminate on the general case.",
    ],
    "explanation": (
        "The project duration is the longest dependency chain, and it is tractable "
        "only because the graph has no cycles. With cycles, an arbitrarily long "
        "chain could be walked and the question would not be meaningful.\n\n"
        "Compute a topological order with Kahn's algorithm, then make one forward "
        "pass. `best[v]` holds the heaviest chain ending at task `v`, initialised "
        "to 0 for the sources and -1 for everything else. Because tasks are visited "
        "in topological order, every predecessor of `v` has already been final when "
        "`v` is reached, so a single pass suffices -- no revisiting, no fixed-point "
        "iteration.\n\n"
        "For each edge the predecessor offers a candidate `best[u] + w`, and `v` "
        "keeps the largest. Unreachable tasks keep their -1 and are skipped when "
        "they would extend a chain. The largest value across all tasks is the "
        "answer, since a chain may end anywhere.\n\n"
        "The topological sort is O(n + m) and the pass is O(n + m), so the total is "
        "O(n + m) time and O(n + m) space."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n + m)",
    "expected_space_complexity": "O(n + m)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.ArrayList;
            import java.util.Deque;
            import java.util.List;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static long criticalPath(int n, List<int[]>[] adjacency, List<Integer> sources) {
                    // Heaviest chain weight starting at any source.
                    return 0L;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int before = in.nextInt();
                        int after = in.nextInt();
                        int weight = in.nextInt();
                        adjacency[before].add(new int[] { after, weight });
                    }
                    int k = in.nextInt();
                    List<Integer> sources = new ArrayList<>();
                    for (int i = 0; i < k; i++) {
                        sources.add(in.nextInt());
                    }
                    System.out.println(criticalPath(n, adjacency, sources));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def critical_path(n, adjacency, sources):
                # Heaviest chain weight starting at any source.
                return 0


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    before, after, weight = data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]
                    adjacency[before].append((after, weight))
                cursor = 2 + 3 * m
                k = data[cursor]
                sources = data[cursor + 1 : cursor + 1 + k]
                print(critical_path(n, adjacency, sources))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function criticalPath(n, adjacency, sources) {
              // Heaviest chain weight starting at any source.
              return 0;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const before = Number(data[2 + 3 * i]);
                const after = Number(data[3 + 3 * i]);
                const weight = Number(data[4 + 3 * i]);
                adjacency[before].push([after, weight]);
              }
              const cursor = 2 + 3 * m;
              const k = Number(data[cursor]);
              const sources = [];
              for (let i = 0; i < k; i += 1) {
                sources.push(Number(data[cursor + 1 + i]));
              }
              console.log(criticalPath(n, adjacency, sources));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.ArrayList;
            import java.util.Deque;
            import java.util.List;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static long criticalPath(int n, List<int[]>[] adjacency, List<Integer> sources) {
                    int[] indegree = new int[n];
                    for (int node = 0; node < n; node += 1) {
                        for (int[] edge : adjacency[node]) {
                            indegree[edge[0]] += 1;
                        }
                    }
                    Deque<Integer> ready = new ArrayDeque<>();
                    for (int node = 0; node < n; node += 1) {
                        if (indegree[node] == 0) {
                            ready.add(node);
                        }
                    }
                    int[] order = new int[n];
                    int placed = 0;
                    while (!ready.isEmpty()) {
                        int node = ready.poll();
                        order[placed++] = node;
                        for (int[] edge : adjacency[node]) {
                            int after = edge[0];
                            indegree[after] -= 1;
                            if (indegree[after] == 0) {
                                ready.add(after);
                            }
                        }
                    }

                    long[] best = new long[n];
                    for (int node = 0; node < n; node += 1) {
                        best[node] = -1L;
                    }
                    for (int source : sources) {
                        best[source] = 0L;
                    }
                    long answer = 0L;
                    for (int i = 0; i < placed; i += 1) {
                        int node = order[i];
                        if (best[node] > answer) {
                            answer = best[node];
                        }
                        if (best[node] < 0) {
                            continue;
                        }
                        for (int[] edge : adjacency[node]) {
                            int after = edge[0];
                            long candidate = best[node] + edge[1];
                            if (candidate > best[after]) {
                                best[after] = candidate;
                            }
                        }
                    }
                    for (int node = 0; node < n; node += 1) {
                        if (best[node] > answer) {
                            answer = best[node];
                        }
                    }
                    return answer;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int before = in.nextInt();
                        int after = in.nextInt();
                        int weight = in.nextInt();
                        adjacency[before].add(new int[] { after, weight });
                    }
                    int k = in.nextInt();
                    List<Integer> sources = new ArrayList<>();
                    for (int i = 0; i < k; i++) {
                        sources.add(in.nextInt());
                    }
                    System.out.println(criticalPath(n, adjacency, sources));
                }
            }
            """
        ),
        "python": source(
            """
            import sys
            from collections import deque


            def critical_path(n, adjacency, sources):
                indegree = [0] * n
                for node in range(n):
                    for after, _ in adjacency[node]:
                        indegree[after] += 1
                ready = deque(node for node in range(n) if indegree[node] == 0)
                order = []
                while ready:
                    node = ready.popleft()
                    order.append(node)
                    for after, _ in adjacency[node]:
                        indegree[after] -= 1
                        if indegree[after] == 0:
                            ready.append(after)

                best = [-1] * n
                for start in sources:
                    best[start] = 0
                for node in order:
                    if best[node] < 0:
                        continue
                    for after, weight in adjacency[node]:
                        if best[after] < best[node] + weight:
                            best[after] = best[node] + weight
                return max(best)


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    before, after, weight = data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]
                    adjacency[before].append((after, weight))
                cursor = 2 + 3 * m
                k = data[cursor]
                sources = data[cursor + 1 : cursor + 1 + k]
                print(critical_path(n, adjacency, sources))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function criticalPath(n, adjacency, sources) {
              const indegree = new Array(n).fill(0);
              for (let node = 0; node < n; node += 1) {
                for (const [after] of adjacency[node]) {
                  indegree[after] += 1;
                }
              }
              const ready = [];
              for (let node = 0; node < n; node += 1) {
                if (indegree[node] === 0) {
                  ready.push(node);
                }
              }
              const order = [];
              while (ready.length > 0) {
                ready.sort((a, b) => a - b);
                const node = ready.shift();
                order.push(node);
                for (const [after] of adjacency[node]) {
                  indegree[after] -= 1;
                  if (indegree[after] === 0) {
                    ready.push(after);
                  }
                }
              }

              const best = new Array(n).fill(-1);
              for (const source of sources) {
                best[source] = 0;
              }
              for (const node of order) {
                if (best[node] < 0) {
                  continue;
                }
                for (const [after, weight] of adjacency[node]) {
                  const candidate = best[node] + weight;
                  if (candidate > best[after]) {
                    best[after] = candidate;
                  }
                }
              }
              let answer = -1;
              for (const value of best) {
                if (value > answer) {
                  answer = value;
                }
              }
              return answer;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const before = Number(data[2 + 3 * i]);
                const after = Number(data[3 + 3 * i]);
                const weight = Number(data[4 + 3 * i]);
                adjacency[before].push([after, weight]);
              }
              const cursor = 2 + 3 * m;
              const k = Number(data[cursor]);
              const sources = [];
              for (let i = 0; i < k; i += 1) {
                sources.push(Number(data[cursor + 1 + i]));
              }
              console.log(criticalPath(n, adjacency, sources));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_critical_path, CRITICAL_INPUT),
        judged_case(_critical_path, "1 0\n1 0"),
        judged_case(_critical_path, "3 2\n0 1 4\n1 2 5\n1 0"),
        judged_case(_critical_path, "2 1\n1 0 7\n1 1"),
        judged_case(_critical_path, "4 3\n0 1 2\n0 2 3\n1 3 10\n2 0 1", is_hidden=True),
        judged_case(_critical_path, "6 5\n0 1 1\n1 2 1\n2 3 1\n3 4 1\n4 5 1\n1 0", is_hidden=True),
        judged_case(_critical_path, "5 6\n0 1 9\n0 2 8\n1 3 9\n2 3 9\n3 4 9\n1 4 2\n1 0", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Cheapest route with different edge weights
# --------------------------------------------------------------------------- #

DIJKSTRA_INPUT = "5 7\n0 1 4\n0 2 1\n2 1 2\n1 3 1\n2 3 5\n3 4 3\n0 4 10\n0"


def _dijkstra(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m = tokens[0], tokens[1]
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for i in range(m):
        u, v, w = tokens[2 + 3 * i], tokens[3 + 3 * i], tokens[4 + 3 * i]
        adjacency[u].append((v, w))
    source = tokens[2 + 3 * m]

    unreachable = float("inf")
    distance = [unreachable] * n
    distance[source] = 0
    queue = [(0, source)]
    while queue:
        current, node = heapq.heappop(queue)
        if current > distance[node]:
            continue
        for after, weight in adjacency[node]:
            if current + weight < distance[after]:
                distance[after] = current + weight
                heapq.heappush(queue, (distance[after], after))
    return str(distance[n - 1]) if distance[n - 1] != unreachable else "-1"


WEIGHTED_SHORTEST_PATH: dict[str, Any] = {
    "slug": "cheapest-route-with-edge-weights",
    "title": "Cheapest Route With Edge Weights",
    "summary": "Find the minimum total cost from a start node to the last node.",
    "difficulty": "Hard",
    "topics": ["Graphs", "Dijkstra", "Heaps", "Shortest Paths"],
    "description": (
        "You are given a directed graph with non-negative edge weights and a "
        "start node `s`. Find the minimum total weight of a route from `s` to node "
        "`n - 1`. Routes may repeat nodes if that is cheaper, though a minimum "
        "route never needs to.\n\n"
        "If node `n - 1` cannot be reached from `s`, print -1."
    ),
    "input_format": (
        "Line 1: `n m`, the number of nodes and edges.\n"
        "The next `m` lines each contain `from to weight`.\n"
        "The next line contains `s`, the start node."
    ),
    "output_format": "Print the minimum total weight from `s` to node `n - 1`, or -1 if unreachable.",
    "constraints": (
        "1 <= n <= 10^5, 0 <= m <= 2 * 10^5, 0 <= weight <= 10^6, and every weight "
        "is non-negative. The graph may contain cycles and parallel edges."
    ),
    "examples": [
        {
            "input": DIJKSTRA_INPUT,
            "output": _dijkstra(DIJKSTRA_INPUT),
            "explanation": "Going 0 -> 2 -> 1 -> 3 -> 4 costs 1 + 2 + 1 + 3 = 7, beating the direct edge of 10.",
        }
    ],
    "hints": [
        "Exploring routes cheapest-first fails when edge weights differ: a route that starts cheaply can end expensively. What do you actually need to order -- routes, or nodes?",
        "You only ever need the best cost known so far for each node. Order nodes by that best cost, and the first time a node is finalised its cost is proven, because every route that could improve it starts from a node you have not finalised and would have to be more expensive.",
        "Maintain a best-cost per node, all infinity except the start at 0. Repeatedly take the unvisited node with the smallest best cost, relax its outgoing edges, and push any improved node back.",
        "A stale entry can be left in the priority queue after the node was already improved. Check the popped cost against the stored best cost and skip when it is worse -- that check is what keeps the work near linear instead of quadratic.",
        "Negative weights break this algorithm, which is why the constraint says non-negative. With negative edges you would need Bellman-Ford instead, and even then a route could become arbitrarily cheap by looping through a negative cycle.",
    ],
    "explanation": (
        "Keep `distance[v]`, the cheapest cost found so far to reach `v`, "
        "initialised to infinity everywhere except the start node at zero.\n\n"
        "Repeatedly finalise the unfinalised node with the smallest known distance. "
        "That node's cost cannot improve afterwards: any cheaper route to it would "
        "have to come from an unfinalised node, and unfinalised nodes all have costs "
        "at least as large, while every edge weight is non-negative, so no such "
        "route could be cheaper. This is the greedy step that makes the algorithm "
        "correct.\n\n"
        "Finalising a node means relaxing its outgoing edges: each offers the "
        "neighbour `distance[u] + weight`, and any improvement replaces the "
        "neighbour's stored cost and pushes a new entry. Because a node can be "
        "pushed several times before it is finalised, a popped entry whose cost "
        "already exceeds the stored best is stale and is skipped.\n\n"
        "Each node is finalised once and each edge is relaxed once, with one heap "
        "operation per successful relaxation, giving O((n + m) log n) time and "
        "O(n + m) space."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O((n + m) log n)",
    "expected_space_complexity": "O(n + m)",
    "time_limit_ms": 5_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayList;
            import java.util.List;
            import java.util.PriorityQueue;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static long cheapestRoute(int n, List<int[]>[] adjacency, int source) {
                    // Minimum cost from source to node n - 1, or -1.
                    return -1L;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int from = in.nextInt();
                        int to = in.nextInt();
                        int weight = in.nextInt();
                        adjacency[from].add(new int[] { to, weight });
                    }
                    int source = in.nextInt();
                    System.out.println(cheapestRoute(n, adjacency, source));
                }
            }
            """
        ),
        "python": source(
            """
            import heapq
            import sys


            def cheapest_route(n, adjacency, source):
                # Minimum cost from source to node n - 1, or -1.
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    u, v, w = data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]
                    adjacency[u].append((v, w))
                source = data[2 + 3 * m]
                print(cheapest_route(n, adjacency, source))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function cheapestRoute(n, adjacency, source) {
              // Minimum cost from source to node n - 1, or -1.
              return -1;
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const u = Number(data[2 + 3 * i]);
                const v = Number(data[3 + 3 * i]);
                const w = Number(data[4 + 3 * i]);
                adjacency[u].push([v, w]);
              }
              const source = Number(data[2 + 3 * m]);
              console.log(cheapestRoute(n, adjacency, source));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayList;
            import java.util.Arrays;
            import java.util.List;
            import java.util.PriorityQueue;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static long cheapestRoute(int n, List<int[]>[] adjacency, int source) {
                    long infinity = Long.MAX_VALUE / 4;
                    long[] distance = new long[n];
                    Arrays.fill(distance, infinity);
                    boolean[] settled = new boolean[n];
                    distance[source] = 0L;
                    PriorityQueue<long[]> queue = new PriorityQueue<>((a, b) -> Long.compare(a[0], b[0]));
                    queue.add(new long[] { 0L, source });
                    while (!queue.isEmpty()) {
                        long[] entry = queue.poll();
                        long cost = entry[0];
                        int node = (int) entry[1];
                        if (settled[node] || cost > distance[node]) {
                            continue;
                        }
                        settled[node] = true;
                        for (int[] edge : adjacency[node]) {
                            int after = edge[0];
                            long candidate = cost + edge[1];
                            if (candidate < distance[after]) {
                                distance[after] = candidate;
                                queue.add(new long[] { candidate, after });
                            }
                        }
                    }
                    return distance[n - 1] == infinity ? -1L : distance[n - 1];
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<int[]>[] adjacency = new List[n];
                    for (int i = 0; i < n; i++) {
                        adjacency[i] = new ArrayList<>();
                    }
                    for (int i = 0; i < m; i++) {
                        int from = in.nextInt();
                        int to = in.nextInt();
                        int weight = in.nextInt();
                        adjacency[from].add(new int[] { to, weight });
                    }
                    int source = in.nextInt();
                    System.out.println(cheapestRoute(n, adjacency, source));
                }
            }
            """
        ),
        "python": source(
            """
            import heapq
            import sys


            def cheapest_route(n, adjacency, source):
                infinity = float("inf")
                distance = [infinity] * n
                distance[source] = 0
                queue = [(0, source)]
                while queue:
                    cost, node = heapq.heappop(queue)
                    if cost > distance[node]:
                        continue
                    for after, weight in adjacency[node]:
                        if cost + weight < distance[after]:
                            distance[after] = cost + weight
                            heapq.heappush(queue, (distance[after], after))
                if distance[n - 1] == infinity:
                    return -1
                return distance[n - 1]


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for i in range(m):
                    u, v, w = data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]
                    adjacency[u].append((v, w))
                source = data[2 + 3 * m]
                print(cheapest_route(n, adjacency, source))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function cheapestRoute(n, adjacency, source) {
              const distance = new Array(n).fill(Infinity);
              distance[source] = 0;
              const queue = [[0, source]];
              while (queue.length > 0) {
                queue.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
                const [cost, node] = queue.shift();
                if (cost > distance[node]) {
                  continue;
                }
                for (const [after, weight] of adjacency[node]) {
                  const candidate = cost + weight;
                  if (candidate < distance[after]) {
                    distance[after] = candidate;
                    queue.push([candidate, after]);
                  }
                }
              }
              return distance[n - 1] === Infinity ? -1 : distance[n - 1];
            }

            function main() {
              const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
              const n = Number(data[0]);
              const m = Number(data[1]);
              const adjacency = Array.from({ length: n }, () => []);
              for (let i = 0; i < m; i += 1) {
                const u = Number(data[2 + 3 * i]);
                const v = Number(data[3 + 3 * i]);
                const w = Number(data[4 + 3 * i]);
                adjacency[u].push([v, w]);
              }
              const source = Number(data[2 + 3 * m]);
              console.log(cheapestRoute(n, adjacency, source));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_dijkstra, DIJKSTRA_INPUT),
        judged_case(_dijkstra, "1 0\n0"),
        judged_case(_dijkstra, "2 0\n0"),
        judged_case(_dijkstra, "2 1\n0 1 5\n0"),
        judged_case(_dijkstra, "4 5\n0 1 2\n1 2 3\n2 3 4\n0 2 10\n1 3 20\n0", is_hidden=True),
        judged_case(_dijkstra, "5 6\n0 1 1\n1 2 1\n2 3 1\n3 4 1\n0 4 100\n1 4 50\n0", is_hidden=True),
        judged_case(_dijkstra, "4 4\n0 1 0\n1 2 0\n2 3 0\n0 2 7\n0", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# How many islands are in the grid?
# --------------------------------------------------------------------------- #

ISLANDS_INPUT = "3 3\n###\n#.#\n###"


def _islands(stdin: str) -> str:
    lines = text_lines(stdin)
    header = lines[0].split()
    rows, cols = int(header[0]), int(header[1])
    grid = lines[1 : 1 + rows]
    seen = [[False] * cols for _ in range(rows)]
    islands = 0
    for start_row in range(rows):
        for start_col in range(cols):
            if grid[start_row][start_col] != "#" or seen[start_row][start_col]:
                continue
            islands += 1
            stack = [(start_row, start_col)]
            seen[start_row][start_col] = True
            while stack:
                row, col = stack.pop()
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row, next_col = row + delta_row, col + delta_col
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if grid[next_row][next_col] != "#" or seen[next_row][next_col]:
                        continue
                    seen[next_row][next_col] = True
                    stack.append((next_row, next_col))
    return str(islands)


NUMBER_OF_ISLANDS: dict[str, Any] = {
    "slug": "number-of-islands",
    "title": "Number of Islands",
    "summary": "Count the groups of land cells joined up or down.",
    "difficulty": "Medium",
    "topics": ["Graphs", "Depth-First Search", "Breadth-First Search", "Grids"],
    "description": (
        "You are given a grid of `.` for water and `#` for land. Two land cells "
        "belong to the same island when a path of land cells connects them, "
        "moving only up, down, left or right. Diagonals do not connect.\n\n"
        "Count the islands."
    ),
    "input_format": (
        "Line 1: `rows cols`.\n"
        "The next `rows` lines each contain exactly `cols` characters, either `.` "
        "or `#`, with no spaces between them."
    ),
    "output_format": "Print the number of islands.",
    "constraints": (
        "1 <= rows, cols <= 300 and 1 <= rows * cols <= 9 * 10^4."
    ),
    "examples": [
        {
            "input": ISLANDS_INPUT,
            "output": _islands(ISLANDS_INPUT),
            "explanation": "The ring of land is one island: the middle cell is water, but the land all the way round it is connected.",
        }
    ],
    "hints": [
        "This is the connected-components problem wearing a grid instead of an edge list. What does one island correspond to in that problem?",
        "One search. Start a flood fill from an unvisited land cell, and everything it reaches belongs to that one island. Start a second fill only when you meet land nobody has reached yet.",
        "Scan every cell in row-major order. When you find a `#` that has not been seen, increment the answer and flood from it, marking cells seen as you reach them.",
        "Mark a cell seen when you put it on the stack rather than when you take it off. Marking on the way out lets the same cell be pushed from two different directions.",
        "The flood fill must not cross the diagonal. Checking all eight neighbours would merge cells that the statement says are separate, which is the classic mistake here.",
    ],
    "explanation": (
        "Build the graph implicitly: each land cell is a vertex, and two land "
        "cells are joined when they share a side. An island is then exactly a "
        "connected component of that graph.\n\n"
        "Scan the grid in row-major order. Whenever the scan meets a land cell that "
        "has not been seen, no earlier fill could have reached it, so it must start "
        "a new island: increment the answer and flood from it, marking every cell "
        "the flood reaches. Cells are marked as they are pushed onto the stack, so "
        "each is pushed once and a later scan step never re-counts it.\n\n"
        "The flood only steps to a cell sharing a side, so diagonal land is never "
        "joined. Every land cell is pushed once and each checks four neighbours, so "
        "the time is O(rows * cols) and the seen grid and the stack use O(rows * cols)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(rows * cols)",
    "expected_space_complexity": "O(rows * cols)",
    "time_limit_ms": 3_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }

                    String next() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        StringBuilder text = new StringBuilder();
                        while (c > ' ') {
                            text.append((char) c);
                            c = read();
                        }
                        return text.toString();
                    }
                }

                static int countIslands(char[][] grid) {
                    // Return the number of groups of land joined up or down.
                    return 0;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int rows = in.nextInt();
                    int cols = in.nextInt();
                    char[][] grid = new char[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        String line = in.next();
                        for (int c = 0; c < cols; c += 1) {
                            grid[r][c] = line.charAt(c);
                        }
                    }
                    System.out.println(countIslands(grid));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def count_islands(grid, rows, cols):
                # Return the number of groups of land joined up or down.
                return 0


            def main():
                lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
                rows, cols = (int(value) for value in lines[0].split())
                grid = lines[1 : 1 + rows]
                print(count_islands(grid, rows, cols))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countIslands(grid, rows, cols) {
              // Return the number of groups of land joined up or down.
              return 0;
            }

            function main() {
              const lines = fs.readFileSync(0, "utf8").split(/\\s*\\n/).filter((line) => line.trim() !== "");
              const [rows, cols] = lines[0].trim().split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows);
              console.log(countIslands(grid, rows, cols));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.Deque;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }

                    String next() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        StringBuilder text = new StringBuilder();
                        while (c > ' ') {
                            text.append((char) c);
                            c = read();
                        }
                        return text.toString();
                    }
                }

                static int countIslands(char[][] grid) {
                    int rows = grid.length;
                    int cols = grid[0].length;
                    boolean[][] seen = new boolean[rows][cols];
                    int[] deltas = { 1, 0, -1, 0, 0, 1, 0, -1 };
                    int islands = 0;
                    for (int startRow = 0; startRow < rows; startRow += 1) {
                        for (int startCol = 0; startCol < cols; startCol += 1) {
                            if (grid[startRow][startCol] != '#' || seen[startRow][startCol]) {
                                continue;
                            }
                            islands += 1;
                            Deque<int[]> stack = new ArrayDeque<>();
                            stack.push(new int[] { startRow, startCol });
                            seen[startRow][startCol] = true;
                            while (!stack.isEmpty()) {
                                int[] cell = stack.pop();
                                for (int step = 0; step < 4; step += 1) {
                                    int nextRow = cell[0] + deltas[step * 2];
                                    int nextCol = cell[1] + deltas[step * 2 + 1];
                                    if (nextRow < 0 || nextRow >= rows || nextCol < 0 || nextCol >= cols) {
                                        continue;
                                    }
                                    if (grid[nextRow][nextCol] != '#' || seen[nextRow][nextCol]) {
                                        continue;
                                    }
                                    seen[nextRow][nextCol] = true;
                                    stack.push(new int[] { nextRow, nextCol });
                                }
                            }
                        }
                    }
                    return islands;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int rows = in.nextInt();
                    int cols = in.nextInt();
                    char[][] grid = new char[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        String line = in.next();
                        for (int c = 0; c < cols; c += 1) {
                            grid[r][c] = line.charAt(c);
                        }
                    }
                    System.out.println(countIslands(grid));
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def count_islands(grid, rows, cols):
                seen = [[False] * cols for _ in range(rows)]
                islands = 0
                for start_row in range(rows):
                    for start_col in range(cols):
                        if grid[start_row][start_col] != "#" or seen[start_row][start_col]:
                            continue
                        islands += 1
                        stack = [(start_row, start_col)]
                        seen[start_row][start_col] = True
                        while stack:
                            row, col = stack.pop()
                            for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                                next_row, next_col = row + delta_row, col + delta_col
                                if not (0 <= next_row < rows and 0 <= next_col < cols):
                                    continue
                                if grid[next_row][next_col] != "#" or seen[next_row][next_col]:
                                    continue
                                seen[next_row][next_col] = True
                                stack.append((next_row, next_col))
                return islands


            def main():
                lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
                rows, cols = (int(value) for value in lines[0].split())
                grid = lines[1 : 1 + rows]
                print(count_islands(grid, rows, cols))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function countIslands(grid, rows, cols) {
              const seen = Array.from({ length: rows }, () => new Array(cols).fill(false));
              const deltas = [
                [1, 0],
                [-1, 0],
                [0, 1],
                [0, -1],
              ];
              let islands = 0;
              for (let startRow = 0; startRow < rows; startRow += 1) {
                for (let startCol = 0; startCol < cols; startCol += 1) {
                  if (grid[startRow][startCol] !== "#" || seen[startRow][startCol]) {
                    continue;
                  }
                  islands += 1;
                  const stack = [[startRow, startCol]];
                  seen[startRow][startCol] = true;
                  while (stack.length > 0) {
                    const [row, col] = stack.pop();
                    for (const [deltaRow, deltaCol] of deltas) {
                      const nextRow = row + deltaRow;
                      const nextCol = col + deltaCol;
                      if (nextRow < 0 || nextRow >= rows || nextCol < 0 || nextCol >= cols) {
                        continue;
                      }
                      if (grid[nextRow][nextCol] !== "#" || seen[nextRow][nextCol]) {
                        continue;
                      }
                      seen[nextRow][nextCol] = true;
                      stack.push([nextRow, nextCol]);
                    }
                  }
                }
              }
              return islands;
            }

            function main() {
              const lines = fs.readFileSync(0, "utf8").split(/\\s*\\n/).filter((line) => line.trim() !== "");
              const [rows, cols] = lines[0].trim().split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows);
              console.log(countIslands(grid, rows, cols));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_islands, ISLANDS_INPUT),
        judged_case(_islands, "1 1\n#"),
        judged_case(_islands, "1 1\n."),
        judged_case(_islands, "3 4\n.#.#\n..#.\n#..."),
        judged_case(_islands, "4 4\n....\n....\n....\n....", is_hidden=True),
        judged_case(_islands, "4 4\n####\n####\n####\n####", is_hidden=True),
        judged_case(_islands, "2 3\n#.#\n.#.", is_hidden=True),
        judged_case(_islands, "5 5\n.....\n.###.\n.###.\n.###.\n.....", is_hidden=True),
        judged_case(_islands, "3 3\n#.#\n.#.\n#.#", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# How many minutes until every orange rots?
# --------------------------------------------------------------------------- #

ROTTING_INPUT = "3 3\n2 1 1\n1 1 0\n0 1 1"


def _rotting(stdin: str) -> str:
    rows_of_ints = int_rows(stdin)
    rows, cols = rows_of_ints[0][0], rows_of_ints[0][1]
    grid = [list(row) for row in rows_of_ints[1 : 1 + rows]]
    fresh = sum(row.count(0) for row in grid)
    queue = deque(
        (row, col) for row in range(rows) for col in range(cols) if grid[row][col] == 1
    )
    minutes = 0
    while queue and fresh:
        for _ in range(len(queue)):
            row, col = queue.popleft()
            for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                next_row, next_col = row + delta_row, col + delta_col
                if not (0 <= next_row < rows and 0 <= next_col < cols):
                    continue
                if grid[next_row][next_col] != 0:
                    continue
                grid[next_row][next_col] = 1
                fresh -= 1
                queue.append((next_row, next_col))
        minutes += 1
    return "-1" if fresh else str(minutes)


ROTTING_ORANGES: dict[str, Any] = {
    "slug": "rotting-oranges",
    "title": "Rotting Oranges",
    "summary": "Find how many minutes until no fresh orange is left.",
    "difficulty": "Medium",
    "topics": ["Graphs", "Breadth-First Search", "Queues", "Grids"],
    "description": (
        "You are given a grid where `0` is a fresh orange, `1` is a rotten orange "
        "and `2` is an empty cell. Every minute, each rotten orange rots the fresh "
        "orange directly above, below, left and right of it.\n\n"
        "Return the number of minutes until no fresh orange remains, or -1 if some "
        "fresh orange can never rot."
    ),
    "input_format": (
        "Line 1: `rows cols`.\n"
        "The next `rows` lines each contain exactly `cols` integers, each 0, 1 or 2."
    ),
    "output_format": "Print the minutes until no fresh orange remains, or -1 if some can never rot.",
    "constraints": "1 <= rows, cols <= 10^3 and 1 <= rows * cols <= 10^6.",
    "examples": [
        {
            "input": ROTTING_INPUT,
            "output": _rotting(ROTTING_INPUT),
            "explanation": "Both fresh oranges touch a rotten one, so everything is rotten after one minute.",
        }
    ],
    "hints": [
        "Rot spreads out from every rotten orange at once, so this is a breadth-first search with several starting points rather than one. What does the level of a cell in such a search mean?",
        "The level of a cell is the number of minutes it takes to rot. Put all the rotten oranges on the queue first, and only then start consuming it: that way minute one is the wave that leaves the initial oranges.",
        "Count the fresh oranges. Each time a fresh orange is converted, decrement the count. At the end the answer is the number of completed waves, or -1 if fresh oranges are left when the queue empties.",
        "Take the queue's size once per wave with `len(queue)` before the inner loop, and loop exactly that many times. Reading the size inside the loop would let oranges that rotted during this wave be processed in the same wave.",
        "If there are no fresh oranges to begin with, the answer is 0 -- not the number of waves the initial rotten oranges happen to be part of. Guarding the loop on `fresh` handles that case for free.",
    ],
    "explanation": (
        "Rotting is a diffusion, not a cascade: at every minute all the rotten "
        "oranges act simultaneously. Modelling that as a breadth-first search from "
        "a whole frontier rather than as a recursive spread makes the simultaneity "
        "automatic.\n\n"
        "Queue every orange that is already rotten, then process the queue in "
        "waves. Before each wave, read the queue's length; consuming exactly that "
        "many items means the wave contains only oranges that were rotten at the "
        "start of the minute, and anything newly converted joins the next wave. "
        "That is the same rule as a multi-source shortest path, with the wave "
        "index playing the part of the distance.\n\n"
        "A counter of fresh oranges makes the two endings cheap. When the queue "
        "empties with fresh oranges still counted, those oranges are in a region "
        "no rotten orange ever reached, so the answer is -1. Otherwise the number "
        "of completed waves is exactly the minute the last fresh orange rotted.\n\n"
        "Every cell enters the queue at most once and each checks four neighbours, "
        "so the time is O(rows * cols) and the grid and queue use O(rows * cols)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(rows * cols)",
    "expected_space_complexity": "O(rows * cols)",
    "time_limit_ms": 3_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.Deque;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static int minutesUntilAllRotten(int[][] grid) {
                    // Return the minutes until no fresh orange is left, or -1.
                    return -1;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int rows = in.nextInt();
                    int cols = in.nextInt();
                    int[][] grid = new int[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        for (int c = 0; c < cols; c += 1) {
                            grid[r][c] = in.nextInt();
                        }
                    }
                    System.out.println(minutesUntilAllRotten(grid));
                }
            }
            """
        ),
        "python": source(
            """
            import sys
            from collections import deque


            def minutes_until_all_rotten(grid, rows, cols):
                # Return the minutes until no fresh orange is left, or -1.
                return -1


            def main():
                rows_of_ints = [line.split() for line in sys.stdin.read().splitlines() if line.split()]
                header = [int(value) for value in rows_of_ints[0]]
                rows, cols = header[0], header[1]
                grid = [[int(value) for value in row] for row in rows_of_ints[1 : 1 + rows]]
                print(minutes_until_all_rotten(grid, rows, cols))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function minutesUntilAllRotten(grid, rows, cols) {
              // Return the minutes until no fresh orange is left, or -1.
              return -1;
            }

            function main() {
              const lines = fs
                .readFileSync(0, "utf8")
                .split(/\\s*\\n/)
                .filter((line) => line.trim() !== "");
              const [rows, cols] = lines[0].trim().split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows).map((line) => line.trim().split(/\\s+/).map(Number));
              console.log(minutesUntilAllRotten(grid, rows, cols));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.Deque;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static int minutesUntilAllRotten(int[][] grid) {
                    int rows = grid.length;
                    int cols = grid[0].length;
                    int fresh = 0;
                    Deque<int[]> queue = new ArrayDeque<>();
                    for (int r = 0; r < rows; r += 1) {
                        for (int c = 0; c < cols; c += 1) {
                            if (grid[r][c] == 0) {
                                fresh += 1;
                            } else if (grid[r][c] == 1) {
                                queue.add(new int[] { r, c });
                            }
                        }
                    }
                    int[] deltas = { 1, 0, -1, 0, 0, 1, 0, -1 };
                    int minutes = 0;
                    while (!queue.isEmpty() && fresh > 0) {
                        int wave = queue.size();
                        for (int taken = 0; taken < wave; taken += 1) {
                            int[] cell = queue.poll();
                            for (int step = 0; step < 4; step += 1) {
                                int nextRow = cell[0] + deltas[step * 2];
                                int nextCol = cell[1] + deltas[step * 2 + 1];
                                if (nextRow < 0 || nextRow >= rows || nextCol < 0 || nextCol >= cols) {
                                    continue;
                                }
                                if (grid[nextRow][nextCol] != 0) {
                                    continue;
                                }
                                grid[nextRow][nextCol] = 1;
                                fresh -= 1;
                                queue.add(new int[] { nextRow, nextCol });
                            }
                        }
                        minutes += 1;
                    }
                    return fresh == 0 ? minutes : -1;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int rows = in.nextInt();
                    int cols = in.nextInt();
                    int[][] grid = new int[rows][cols];
                    for (int r = 0; r < rows; r += 1) {
                        for (int c = 0; c < cols; c += 1) {
                            grid[r][c] = in.nextInt();
                        }
                    }
                    System.out.println(minutesUntilAllRotten(grid));
                }
            }
            """
        ),
        "python": source(
            """
            import sys
            from collections import deque


            def minutes_until_all_rotten(grid, rows, cols):
                fresh = 0
                queue = deque()
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] == 0:
                            fresh += 1
                        elif grid[r][c] == 1:
                            queue.append((r, c))
                deltas = ((1, 0), (-1, 0), (0, 1), (0, -1))
                minutes = 0
                while queue and fresh:
                    for _ in range(len(queue)):
                        row, col = queue.popleft()
                        for delta_row, delta_col in deltas:
                            next_row, next_col = row + delta_row, col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if grid[next_row][next_col] != 0:
                                continue
                            grid[next_row][next_col] = 1
                            fresh -= 1
                            queue.append((next_row, next_col))
                    minutes += 1
                return -1 if fresh else minutes


            def main():
                rows_of_ints = [line.split() for line in sys.stdin.read().splitlines() if line.split()]
                header = [int(value) for value in rows_of_ints[0]]
                rows, cols = header[0], header[1]
                grid = [[int(value) for value in row] for row in rows_of_ints[1 : 1 + rows]]
                print(minutes_until_all_rotten(grid, rows, cols))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function minutesUntilAllRotten(grid, rows, cols) {
              let fresh = 0;
              const queue = [];
              for (let r = 0; r < rows; r += 1) {
                for (let c = 0; c < cols; c += 1) {
                  if (grid[r][c] === 0) {
                    fresh += 1;
                  } else if (grid[r][c] === 1) {
                    queue.push([r, c]);
                  }
                }
              }
              const deltas = [
                [1, 0],
                [-1, 0],
                [0, 1],
                [0, -1],
              ];
              let minutes = 0;
              let head = 0;
              while (head < queue.length && fresh > 0) {
                const wave = queue.length - head;
                for (let taken = 0; taken < wave; taken += 1) {
                  const [row, col] = queue[head];
                  head += 1;
                  for (const [deltaRow, deltaCol] of deltas) {
                    const nextRow = row + deltaRow;
                    const nextCol = col + deltaCol;
                    if (nextRow < 0 || nextRow >= rows || nextCol < 0 || nextCol >= cols) {
                      continue;
                    }
                    if (grid[nextRow][nextCol] !== 0) {
                      continue;
                    }
                    grid[nextRow][nextCol] = 1;
                    fresh -= 1;
                    queue.push([nextRow, nextCol]);
                  }
                }
                minutes += 1;
              }
              return fresh === 0 ? minutes : -1;
            }

            function main() {
              const lines = fs
                .readFileSync(0, "utf8")
                .split(/\\s*\\n/)
                .filter((line) => line.trim() !== "");
              const [rows, cols] = lines[0].trim().split(/\\s+/).map(Number);
              const grid = lines.slice(1, 1 + rows).map((line) => line.trim().split(/\\s+/).map(Number));
              console.log(minutesUntilAllRotten(grid, rows, cols));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_rotting, ROTTING_INPUT),
        judged_case(_rotting, "1 1\n1"),
        judged_case(_rotting, "1 1\n0"),
        judged_case(_rotting, "3 3\n0 1 0\n1 0 1\n0 1 0"),
        judged_case(_rotting, "1 2\n1 0", is_hidden=True),
        judged_case(_rotting, "2 2\n2 2\n2 2", is_hidden=True),
        judged_case(_rotting, "4 4\n2 1 1 0\n0 1 1 0\n0 0 1 1\n0 0 0 1", is_hidden=True),
        judged_case(_rotting, "3 3\n1 0 0\n0 2 2\n0 0 0", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Can the graph be split into two groups?
# --------------------------------------------------------------------------- #

BIPARTITE_INPUT = "6 6\n0 1\n1 2\n2 3\n3 4\n4 5\n5 0"


def _bipartite(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m = tokens[0], tokens[1]
    adjacency = _undirected(n, [(tokens[2 + 2 * i], tokens[3 + 2 * i]) for i in range(m)])
    colour = [-1] * n
    for start in range(n):
        if colour[start] != -1:
            continue
        colour[start] = 0
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbour in adjacency[node]:
                if colour[neighbour] == -1:
                    colour[neighbour] = 1 - colour[node]
                    stack.append(neighbour)
                elif colour[neighbour] == colour[node]:
                    return "no"
    return "yes"


BIPARTITE_CHECK: dict[str, Any] = {
    "slug": "bipartite-graph-check",
    "title": "Bipartite Graph Check",
    "summary": "Decide whether the nodes can be split into two groups with no edge inside a group.",
    "difficulty": "Medium",
    "topics": ["Graphs", "Depth-First Search", "Breadth-First Search"],
    "description": (
        "You are given an undirected graph with nodes `0` to `n - 1`. Decide "
        "whether its nodes can be split into two groups so that every edge joins a "
        "node in one group to a node in the other.\n\n"
        "Such a graph is called bipartite. Either group may be empty, so a graph "
        "with no edges always is."
    ),
    "input_format": (
        "Line 1: `n m`, the number of nodes and edges.\n"
        "The next `m` lines each contain `u v`, an undirected edge."
    ),
    "output_format": "Print `yes` if the graph is bipartite, otherwise `no`, in lower case.",
    "constraints": (
        "1 <= n <= 2 * 10^5, 0 <= m <= 2 * 10^5, 0 <= u, v < n. Self-loops and "
        "repeated edges are permitted."
    ),
    "examples": [
        {
            "input": BIPARTITE_INPUT,
            "output": _bipartite(BIPARTITE_INPUT),
            "explanation": "Six nodes in a ring can alternate between the two groups, so the graph is bipartite.",
        }
    ],
    "hints": [
        "The two groups are not given to you; finding them is the problem. Ask what has to be true about a node once you have decided which group its neighbour is in.",
        "Picking a node's group forces the colour of every node it touches, and their neighbours, and so on. If that forcing ever asks a node to be in the same group as one it touches, no split exists.",
        "Give the first uncoloured node of each component colour 0 and flood. On reaching an uncoloured neighbour, give it the opposite colour. On reaching a neighbour that already has the same colour, answer no.",
        "Loop over every node, not just node 0. A graph can have several components and a conflict in the second one still makes the whole graph non-bipartite, while a node nobody reached is still a valid starting point.",
        "A self-loop is the cheapest check of all: the edge from a node to itself asks it to be in the other group from itself, so any self-loop means the answer is no without needing the flood at all.",
    ],
    "explanation": (
        "Colour every node with 0 or 1 so that each edge joins different colours. "
        "That is exactly the definition of bipartite, restated as something a "
        "search can check.\n\n"
        "Within one connected component, choosing the colour of a single node "
        "forces every other colour: along any path from the start, each step must "
        "flip the colour, so the colour of a node is determined by the parity of the "
        "path length. If the forcing is consistent, the split exists; if it is not, "
        "no split can work. So the search assigns the opposite colour on every "
        "uncoloured neighbour and fails the moment an edge joins two nodes of equal "
        "colour.\n\n"
        "The outer loop restarts from every node that is still uncoloured, because "
        "the graph need not be connected and each component chooses its own parity "
        "independently. Every node is coloured once and every edge is inspected "
        "twice, so the time is O(n + m) and the adjacency lists and the stack use "
        "O(n + m)."
    ),
    "supported_languages": ["python", "javascript", "java"],
    "expected_time_complexity": "O(n + m)",
    "expected_space_complexity": "O(n + m)",
    "time_limit_ms": 3_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayList;
            import java.util.List;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static boolean isBipartite(List<List<Integer>> adjacency) {
                    // Return true when the nodes split into two edge-free groups.
                    return false;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<List<Integer>> adjacency = new ArrayList<>();
                    for (int i = 0; i < n; i += 1) {
                        adjacency.add(new ArrayList<>());
                    }
                    for (int i = 0; i < m; i += 1) {
                        int u = in.nextInt();
                        int v = in.nextInt();
                        adjacency.get(u).add(v);
                        adjacency.get(v).add(u);
                    }
                    System.out.println(isBipartite(adjacency) ? "yes" : "no");
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def is_bipartite(adjacency, n):
                # Return True when the nodes split into two edge-free groups.
                return False


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for index in range(m):
                    u, v = data[2 + 2 * index], data[3 + 2 * index]
                    adjacency[u].append(v)
                    adjacency[v].append(u)
                print("yes" if is_bipartite(adjacency, n) else "no")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function isBipartite(adjacency) {
              // Return true when the nodes split into two edge-free groups.
              return false;
            }

            function main() {
              const data = fs
                .readFileSync(0, "utf8")
                .trim()
                .split(/\\s+/)
                .map(Number);
              const n = data[0];
              const m = data[1];
              const adjacency = Array.from({ length: n }, () => []);
              for (let index = 0; index < m; index += 1) {
                const u = data[2 + 2 * index];
                const v = data[3 + 2 * index];
                adjacency[u].push(v);
                adjacency[v].push(u);
              }
              console.log(isBipartite(adjacency) ? "yes" : "no");
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "java": source(
            """
            import java.io.IOException;
            import java.util.ArrayDeque;
            import java.util.ArrayList;
            import java.util.Arrays;
            import java.util.Deque;
            import java.util.List;

            public class Main {
                static final class FastScanner {
                    private final byte[] buffer = new byte[1 << 16];
                    private int pos = 0;
                    private int len = 0;

                    private int read() throws IOException {
                        if (pos == len) {
                            len = System.in.read(buffer);
                            pos = 0;
                            if (len <= 0) {
                                return -1;
                            }
                        }
                        return buffer[pos++];
                    }

                    int nextInt() throws IOException {
                        int c = read();
                        while (c != -1 && c <= ' ') {
                            c = read();
                        }
                        int value = 0;
                        while (c > ' ') {
                            value = value * 10 + (c - '0');
                            c = read();
                        }
                        return value;
                    }
                }

                static boolean isBipartite(List<List<Integer>> adjacency) {
                    int n = adjacency.size();
                    int[] colour = new int[n];
                    Arrays.fill(colour, -1);
                    for (int start = 0; start < n; start += 1) {
                        if (colour[start] != -1) {
                            continue;
                        }
                        colour[start] = 0;
                        Deque<Integer> stack = new ArrayDeque<>();
                        stack.push(start);
                        while (!stack.isEmpty()) {
                            int node = stack.pop();
                            for (int neighbour : adjacency.get(node)) {
                                if (colour[neighbour] == -1) {
                                    colour[neighbour] = 1 - colour[node];
                                    stack.push(neighbour);
                                } else if (colour[neighbour] == colour[node]) {
                                    return false;
                                }
                            }
                        }
                    }
                    return true;
                }

                public static void main(String[] args) throws IOException {
                    FastScanner in = new FastScanner();
                    int n = in.nextInt();
                    int m = in.nextInt();
                    List<List<Integer>> adjacency = new ArrayList<>();
                    for (int i = 0; i < n; i += 1) {
                        adjacency.add(new ArrayList<>());
                    }
                    for (int i = 0; i < m; i += 1) {
                        int u = in.nextInt();
                        int v = in.nextInt();
                        adjacency.get(u).add(v);
                        adjacency.get(v).add(u);
                    }
                    System.out.println(isBipartite(adjacency) ? "yes" : "no");
                }
            }
            """
        ),
        "python": source(
            """
            import sys


            def is_bipartite(adjacency, n):
                colour = [-1] * n
                for start in range(n):
                    if colour[start] != -1:
                        continue
                    colour[start] = 0
                    stack = [start]
                    while stack:
                        node = stack.pop()
                        for neighbour in adjacency[node]:
                            if colour[neighbour] == -1:
                                colour[neighbour] = 1 - colour[node]
                                stack.append(neighbour)
                            elif colour[neighbour] == colour[node]:
                                return False
                return True


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                adjacency = [[] for _ in range(n)]
                for index in range(m):
                    u, v = data[2 + 2 * index], data[3 + 2 * index]
                    adjacency[u].append(v)
                    adjacency[v].append(u)
                print("yes" if is_bipartite(adjacency, n) else "no")


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function isBipartite(adjacency) {
              const n = adjacency.length;
              const colour = new Array(n).fill(-1);
              for (let start = 0; start < n; start += 1) {
                if (colour[start] !== -1) {
                  continue;
                }
                colour[start] = 0;
                const stack = [start];
                while (stack.length > 0) {
                  const node = stack.pop();
                  for (const neighbour of adjacency[node]) {
                    if (colour[neighbour] === -1) {
                      colour[neighbour] = 1 - colour[node];
                      stack.push(neighbour);
                    } else if (colour[neighbour] === colour[node]) {
                      return false;
                    }
                  }
                }
              }
              return true;
            }

            function main() {
              const data = fs
                .readFileSync(0, "utf8")
                .trim()
                .split(/\\s+/)
                .map(Number);
              const n = data[0];
              const m = data[1];
              const adjacency = Array.from({ length: n }, () => []);
              for (let index = 0; index < m; index += 1) {
                const u = data[2 + 2 * index];
                const v = data[3 + 2 * index];
                adjacency[u].push(v);
                adjacency[v].push(u);
              }
              console.log(isBipartite(adjacency) ? "yes" : "no");
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_bipartite, BIPARTITE_INPUT),
        judged_case(_bipartite, "1 0"),
        judged_case(_bipartite, "3 3\n0 1\n1 2\n2 0"),
        judged_case(_bipartite, "4 3\n0 1\n1 2\n2 3"),
        judged_case(_bipartite, "2 1\n0 0", is_hidden=True),
        judged_case(_bipartite, "5 4\n0 1\n2 3\n3 4\n1 2", is_hidden=True),
        judged_case(_bipartite, "4 6\n0 1\n1 2\n2 3\n3 0\n0 2\n1 3", is_hidden=True),
        judged_case(_bipartite, "6 5\n0 1\n0 2\n1 3\n2 3\n4 5", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# Shortest path when an edge can cost less than nothing
# --------------------------------------------------------------------------- #

BELLMAN_INPUT = "5 7 0 4\n0 1 4\n0 2 1\n2 1 2\n1 3 1\n2 3 5\n3 4 3\n0 4 10"


def _bellman(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m, source, target = tokens[0], tokens[1], tokens[2], tokens[3]
    reach = [float("inf")] * n
    reach[source] = 0
    for _ in range(n - 1):
        changed = False
        for index in range(m):
            left = tokens[4 + 3 * index]
            right = tokens[5 + 3 * index]
            weight = tokens[6 + 3 * index]
            if reach[left] + weight < reach[right]:
                reach[right] = reach[left] + weight
                changed = True
        if not changed:
            break
    return "unreachable" if reach[target] == float("inf") else str(reach[target])


NEGATIVE_WEIGHTS: dict[str, Any] = {
    "slug": "shortest-path-with-negative-weights",
    "title": "Shortest Path With Negative Weights",
    "summary": "Relax every edge a fixed number of times so negative costs are allowed.",
    "difficulty": "Hard",
    "topics": ["Graphs", "Bellman-Ford", "Dynamic Programming", "Relaxation"],
    "description": (
        "You are given a directed graph with nodes `0` to `n - 1`. Each edge has an "
        "integer weight, and a weight may be negative. Find the smallest total "
        "weight of any path from `s` to `t`.\n\n"
        "It is guaranteed that no negative-weight cycle is reachable from `s`, so "
        "a smallest weight always exists. Print `unreachable` when `t` cannot be "
        "reached from `s` at all.\n\n"
        "A shortest path never needs to repeat a node, because with no reachable "
        "negative cycle removing a cycle cannot make it heavier -- so an answer "
        "uses at most `n - 1` edges."
    ),
    "input_format": (
        "Line 1: `n m s t`, the number of nodes and edges, the start and the "
        "target.\n"
        "The next `m` lines each contain `u v w`, a directed edge from `u` to `v` "
        "with weight `w`."
    ),
    "output_format": "Print the smallest total weight of a path from `s` to `t`, or `unreachable` if there is none.",
    "constraints": (
        "1 <= n <= 10^3, 0 <= m <= 2 * 10^4, 0 <= u, v < n, and "
        "-10^4 <= w <= 10^4. Self-loops and repeated edges are permitted; a "
        "self-loop with negative weight would be a reachable negative cycle and "
        "never occurs."
    ),
    "examples": [
        {
            "input": BELLMAN_INPUT,
            "output": _bellman(BELLMAN_INPUT),
            "explanation": "Going 0 -> 2 -> 1 -> 3 -> 4 costs 1 + 2 + 1 + 3 = 7, which beats both direct routes.",
        }
    ],
    "hints": [
        "Dijkstra decides what to do with a node once it leaves the queue, and it does that by trusting the smallest distance it has seen. What does a negative edge do to that trust?",
        "Relaxation in rounds. `reach[v]` is the best total weight known so far to reach `v`; one round applies `reach[u] + w < reach[v] -> reach[v] = reach[u] + w` to every edge, in any order.",
        "After `k` rounds, `reach[v]` is the cheapest walk from `s` to `v` using at most `k` edges. Since a shortest path uses at most `n - 1` edges, `n - 1` rounds is enough.",
        "Stop early when a whole round changes nothing. Once a round is silent, every edge is satisfied, and further rounds would not change anything -- which makes the common all-positive case as cheap as Dijkstra.",
        "Watch the infinite distance. Relaxing an edge out of a node you have never reached would set its target to infinity plus a negative weight, which is a finite number in floating point and silently invents a path.",
    ],
    "explanation": (
        "The claim that makes round-based relaxation correct is an invariant: "
        "after `k` rounds, `reach[v]` is the cheapest walk from `s` to `v` that "
        "uses at most `k` edges.\n\n"
        "It holds at `k = 0`, when only `s` is reachable at cost zero. Going from "
        "`k` to `k + 1`, any walk with at most `k + 1` edges is either a walk with "
        "at most `k` edges -- already recorded -- or such a walk followed by one "
        "final edge. Sweeping every edge applies exactly those extensions, so the "
        "invariant is preserved. Since a cheapest path uses at most `n - 1` edges, "
        "`n - 1` rounds leave `reach[t]` final.\n\n"
        "Ordering matters within a round and nothing more: relaxing in place means a "
        "single round can extend a path by several edges, which makes rounds finish "
        "sooner but cannot overshoot the true minimum. An infinity sentinel has to "
        "be guarded before adding a weight to it, or a negative weight turns "
        "infinity into a large finite number and the algorithm reports a path "
        "through a node that was never reached.\n\n"
        "An unchanged round proves every edge is already satisfied, so the answer "
        "cannot improve and the remaining rounds are skipped. There are `n - 1` "
        "rounds of at most `m` relaxations, so the time is O(n * m) and the distance "
        "array uses O(n)."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(n * m)",
    "expected_space_complexity": "O(n)",
    "time_limit_ms": 3_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys

            INF = float("inf")


            def shortest_path(n, edges, source, target):
                # Return the smallest total weight from source to target, or None.
                return None


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m, source, target = data[0], data[1], data[2], data[3]
                edges = [(data[4 + 3 * i], data[5 + 3 * i], data[6 + 3 * i]) for i in range(m)]
                answer = shortest_path(n, edges, source, target)
                print("unreachable" if answer is None else answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function shortestPath(n, edges, source, target) {
              // Return the smallest total weight from source to target, or null.
              return null;
            }

            function main() {
              const data = fs
                .readFileSync(0, "utf8")
                .trim()
                .split(/\\s+/)
                .map(Number);
              const n = data[0];
              const m = data[1];
              const source = data[2];
              const target = data[3];
              const edges = [];
              for (let i = 0; i < m; i += 1) {
                edges.push([data[4 + 3 * i], data[5 + 3 * i], data[6 + 3 * i]]);
              }
              const answer = shortestPath(n, edges, source, target);
              console.log(answer === null ? "unreachable" : answer);
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys

            INF = float("inf")


            def shortest_path(n, edges, source, target):
                reach = [INF] * n
                reach[source] = 0
                for _ in range(n - 1):
                    changed = False
                    for left, right, weight in edges:
                        if reach[left] == INF:
                            continue
                        if reach[left] + weight < reach[right]:
                            reach[right] = reach[left] + weight
                            changed = True
                    if not changed:
                        break
                return None if reach[target] == INF else int(reach[target])


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m, source, target = data[0], data[1], data[2], data[3]
                edges = [(data[4 + 3 * i], data[5 + 3 * i], data[6 + 3 * i]) for i in range(m)]
                answer = shortest_path(n, edges, source, target)
                print("unreachable" if answer is None else answer)


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function shortestPath(n, edges, source, target) {
              const reach = new Array(n).fill(null);
              reach[source] = 0;
              for (let round = 0; round < n - 1; round += 1) {
                let changed = false;
                for (const [left, right, weight] of edges) {
                  if (reach[left] === null) {
                    continue;
                  }
                  if (reach[right] === null || reach[left] + weight < reach[right]) {
                    reach[right] = reach[left] + weight;
                    changed = true;
                  }
                }
                if (!changed) {
                  break;
                }
              }
              return reach[target] === null ? null : reach[target];
            }

            function main() {
              const data = fs
                .readFileSync(0, "utf8")
                .trim()
                .split(/\\s+/)
                .map(Number);
              const n = data[0];
              const m = data[1];
              const source = data[2];
              const target = data[3];
              const edges = [];
              for (let i = 0; i < m; i += 1) {
                edges.push([data[4 + 3 * i], data[5 + 3 * i], data[6 + 3 * i]]);
              }
              const answer = shortestPath(n, edges, source, target);
              console.log(answer === null ? "unreachable" : answer);
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_bellman, BELLMAN_INPUT),
        judged_case(_bellman, "1 0 0 0"),
        judged_case(_bellman, "3 0 0 1"),
        judged_case(_bellman, "2 2 0 1\n0 1 5\n0 1 -3"),
        judged_case(_bellman, "4 4 1 3\n0 1 4\n0 2 5\n1 3 4\n2 3 5", is_hidden=True),
        judged_case(_bellman, "4 5 0 3\n0 1 2\n1 2 -3\n2 3 2\n0 2 10\n2 1 7", is_hidden=True),
        judged_case(_bellman, "5 6 1 4\n0 1 1\n1 2 -5\n2 3 1\n3 4 1\n0 4 20\n1 4 50", is_hidden=True),
        judged_case(_bellman, "6 7 0 5\n0 1 1\n1 2 1\n2 3 1\n3 4 1\n4 5 1\n0 5 30\n2 5 -20", is_hidden=True),
    ],
}


# --------------------------------------------------------------------------- #
# The cheapest way to connect everything
# --------------------------------------------------------------------------- #

MST_INPUT = "4 5\n0 1 10\n0 2 6\n0 3 5\n1 3 15\n2 3 4"


def _minimum_spanning_tree(stdin: str) -> str:
    tokens = int_tokens(stdin)
    n, m = tokens[0], tokens[1]
    edges = sorted(
        (tokens[4 + 3 * i], tokens[2 + 3 * i], tokens[3 + 3 * i]) for i in range(m)
    )
    parent = list(range(n))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    total = 0
    chosen = 0
    for weight, left, right in edges:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            continue
        parent[root_left] = root_right
        total += weight
        chosen += 1
        if chosen == n - 1:
            break
    return "-1" if chosen != n - 1 else str(total)


SPANNING_TREE: dict[str, Any] = {
    "slug": "minimum-spanning-tree-weight",
    "title": "Minimum Spanning Tree Weight",
    "summary": "Take the cheapest edges that still connect, using union-find to reject cycles.",
    "difficulty": "Hard",
    "topics": ["Graphs", "Union Find", "Greedy", "Minimum Spanning Tree"],
    "description": (
        "You are given an undirected graph with nodes `0` to `n - 1` and a weight "
        "on every edge. Find the smallest possible total weight of a set of edges "
        "that connects every node and contains no cycle.\n\n"
        "A spanning tree exists only when the graph is connected, so print -1 when "
        "it is not."
    ),
    "input_format": (
        "Line 1: `n m`, the number of nodes and edges.\n"
        "The next `m` lines each contain `u v w`, an undirected edge with weight `w`."
    ),
    "output_format": "Print the total weight of a minimum spanning tree, or -1 if the graph is not connected.",
    "constraints": "1 <= n <= 10^5, 0 <= m <= 3 * 10^5, 0 <= u, v < n, and 0 <= w <= 10^6.",
    "examples": [
        {
            "input": MST_INPUT,
            "output": _minimum_spanning_tree(MST_INPUT),
            "explanation": "Edges 2-3 (4), 0-3 (5) and 0-2 (6) would cycle, so the tree takes 4 + 5 + 10 = 19.",
        }
    ],
    "hints": [
        "A spanning tree on `n` nodes has exactly `n - 1` edges, so any greedy method has to be able to say no to an edge. When is an edge the right thing to skip?",
        "Sort the edges cheapest first and consider them in that order. Take an edge unless its two ends are already connected -- that keeps the partial answer a forest, never a cycle.",
        "The question 'are these two ends already connected?' is answered by a disjoint-set structure. Union-find answers it in almost constant time, and 'take this edge' is just a union of the two components.",
        "After taking an edge you have merged two components, so the number of components drops by one. Stop after `n - 1` accepted edges, and if the edges run out sooner the graph was not connected.",
        "Path compression alone (halving the parent as you walk) is enough for a union-find used only for 'same component?' queries; you never need the union by rank.",
    ],
    "explanation": (
        "Sort the edges by weight and consider them from cheapest to dearest. Take "
        "an edge unless it would close a cycle, meaning its two ends are already in "
        "the same component. This is Kruskal's algorithm, and it is optimal by the "
        "cut property: for the edge crossing the boundary of some component with "
        "the smallest weight leaving it, every spanning tree must cross that cut, "
        "and no tree can cross it with a cheaper edge.\n\n"
        "Cycle detection needs repeated 'are `u` and `v` in the same component?' "
        "queries, which is exactly what a disjoint-set structure is for. Accepting "
        "an edge merges its two components, so the only operation on a successful "
        "check is a union.\n\n"
        "Each accepted edge reduces the component count by one, so the loop ends "
        "after exactly `n - 1` acceptances. Taking a shorter edge list as given -- "
        "that is, stopping as soon as `n - 1` edges have been taken -- is safe and "
        "is what the code does, because nothing later can be cheaper. If the list "
        "runs out with fewer than `n - 1` accepted, more than one component "
        "survived and the graph is not connected.\n\n"
        "The time is O(m log m) for the sort, and the union-find passes over `m` "
        "edges with almost constant amortized work per query, so they do not change "
        "that bound. The parent array uses O(n) and the sorted edge list O(m)."
    ),
    "supported_languages": ["python", "javascript"],
    "expected_time_complexity": "O(m log m)",
    "expected_space_complexity": "O(n + m)",
    "time_limit_ms": 4_000,
    "memory_limit_mb": 256,
    "starter_code": {
        "python": source(
            """
            import sys


            def spanning_tree_weight(n, edges):
                # Return the cheapest total weight connecting every node, or -1.
                return -1


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                edges = [(data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]) for i in range(m)]
                print(spanning_tree_weight(n, edges))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function spanningTreeWeight(n, edges) {
              // Return the cheapest total weight connecting every node, or -1.
              return -1;
            }

            function main() {
              const data = fs
                .readFileSync(0, "utf8")
                .trim()
                .split(/\\s+/)
                .map(Number);
              const n = data[0];
              const m = data[1];
              const edges = [];
              for (let i = 0; i < m; i += 1) {
                edges.push([data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]]);
              }
              console.log(spanningTreeWeight(n, edges));
            }

            main();
            """
        ),
    },
    "reference_solutions": {
        "python": source(
            """
            import sys


            def spanning_tree_weight(n, edges):
                ordered = sorted((weight, left, right) for left, right, weight in edges)
                parent = list(range(n))

                def find(node):
                    while parent[node] != node:
                        parent[node] = parent[parent[node]]
                        node = parent[node]
                    return node

                total = 0
                chosen = 0
                for weight, left, right in ordered:
                    root_left = find(left)
                    root_right = find(right)
                    if root_left == root_right:
                        continue
                    parent[root_left] = root_right
                    total += weight
                    chosen += 1
                    if chosen == n - 1:
                        break
                return -1 if chosen != n - 1 else total


            def main():
                data = [int(token) for token in sys.stdin.read().split()]
                n, m = data[0], data[1]
                edges = [(data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]) for i in range(m)]
                print(spanning_tree_weight(n, edges))


            if __name__ == "__main__":
                main()
            """
        ),
        "javascript": source(
            """
            const fs = require("fs");

            function spanningTreeWeight(n, edges) {
              const ordered = edges.slice().sort((a, b) => a[2] - b[2]);
              const parent = new Array(n);
              for (let i = 0; i < n; i += 1) {
                parent[i] = i;
              }
              function find(node) {
                while (parent[node] !== node) {
                  parent[node] = parent[parent[node]];
                  node = parent[node];
                }
                return node;
              }
              let total = 0;
              let chosen = 0;
              for (const [left, right, weight] of ordered) {
                const rootLeft = find(left);
                const rootRight = find(right);
                if (rootLeft === rootRight) {
                  continue;
                }
                parent[rootLeft] = rootRight;
                total += weight;
                chosen += 1;
                if (chosen === n - 1) {
                  break;
                }
              }
              return chosen === n - 1 ? total : -1;
            }

            function main() {
              const data = fs
                .readFileSync(0, "utf8")
                .trim()
                .split(/\\s+/)
                .map(Number);
              const n = data[0];
              const m = data[1];
              const edges = [];
              for (let i = 0; i < m; i += 1) {
                edges.push([data[2 + 3 * i], data[3 + 3 * i], data[4 + 3 * i]]);
              }
              console.log(spanningTreeWeight(n, edges));
            }

            main();
            """
        ),
    },
    "test_cases": [
        judged_case(_minimum_spanning_tree, MST_INPUT),
        judged_case(_minimum_spanning_tree, "1 0"),
        judged_case(_minimum_spanning_tree, "3 2\n0 1 1\n1 2 2"),
        judged_case(_minimum_spanning_tree, "4 2\n0 1 1\n1 2 2"),
        judged_case(_minimum_spanning_tree, "5 4\n0 1 2\n1 2 3\n3 4 4\n0 4 100", is_hidden=True),
        judged_case(_minimum_spanning_tree, "4 6\n0 1 4\n1 2 5\n2 3 6\n0 3 7\n1 3 8\n2 3 9", is_hidden=True),
        judged_case(_minimum_spanning_tree, "6 7\n0 1 1\n1 2 2\n2 3 3\n3 4 4\n4 5 5\n0 5 50\n1 5 60", is_hidden=True),
        judged_case(_minimum_spanning_tree, "6 8\n0 1 3\n0 2 3\n0 3 3\n1 4 3\n2 4 3\n3 4 3\n4 5 3\n5 0 3", is_hidden=True),
    ],
}


GRAPHS_PROBLEMS: list[dict[str, Any]] = [
    CONNECTED_COMPONENTS,
    NUMBER_OF_ISLANDS,
    ROTTING_ORANGES,
    BIPARTITE_CHECK,
    SHORTEST_GRID_PATH,
    NEGATIVE_WEIGHTS,
    SPANNING_TREE,
    TOPOLOGICAL_ORDER,
    CRITICAL_PATH,
    WEIGHTED_SHORTEST_PATH,
]

__all__ = ["GRAPHS_PROBLEMS"]