import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProblemCard from "./ProblemCard";

beforeEach(() => {
  vi.clearAllMocks();
});

const twoSum = {
  problem_id: 1,
  slug: "two-sum",
  title: "Two Sum",
  summary: "Find the pair that adds to the target.",
  difficulty: "Easy",
  topics: ["Arrays", "Hashing"],
  status: "attempted",
  attempts_count: 2,
  solved_at: null,
  last_attempted_at: "2026-02-10T09:00:00",
};

const coinChange = {
  problem_id: 2,
  slug: "coin-change",
  title: "Coin Change",
  summary: "Fewest coins that make up an amount.",
  difficulty: "Medium",
  topics: ["Dynamic programming"],
  status: "not_started",
  attempts_count: 0,
  solved_at: null,
  last_attempted_at: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProblemCard with learner progress", () => {
  it("shows the learner's status instead of the generic practice label", () => {
    render(
      <MemoryRouter>
        <ProblemCard problem={twoSum} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Attempted")).toBeInTheDocument();
    expect(screen.getByText("Practice")).toBeInTheDocument();
  });

  it("shows the solved date once a problem is solved", () => {
    render(
      <MemoryRouter>
        <ProblemCard problem={{ ...coinChange, status: "solved", solved_at: "2026-02-11T09:00:00" }} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Solved")).toBeInTheDocument();
    // The exact date format follows the runtime locale, so match the label.
    expect(screen.getByText(/^Solved\s+\S/)).toBeInTheDocument();
    expect(screen.queryByText("Practice")).not.toBeInTheDocument();
  });

  it("keeps its original presentation when no status is supplied", () => {
    // The public catalog endpoint has no learner fields at all.
    const problem = {
      problem_id: twoSum.problem_id,
      slug: twoSum.slug,
      title: twoSum.title,
      summary: twoSum.summary,
      difficulty: twoSum.difficulty,
      topics: twoSum.topics,
    };
    render(
      <MemoryRouter>
        <ProblemCard problem={problem} />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Attempted")).not.toBeInTheDocument();
    expect(screen.getByText("Practice")).toBeInTheDocument();
  });
});
