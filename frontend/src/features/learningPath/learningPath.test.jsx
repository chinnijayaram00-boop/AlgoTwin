import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LearningPathPage from "../../pages/LearningPathPage";
import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";
import ContinueLearningCard from "./ContinueLearningCard";
import { learningPathService } from "./learningPathService";
import { useLearningPath } from "./useLearningPath";

// Only the transport is faked. The service under test stays real, so these
// tests exercise the actual path it builds and the actual headers it sends.
vi.mock("../../services/apiClient", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("../auth/authStorage", () => ({
  getStoredToken: vi.fn(),
}));

function makeProblem(id, slug, title, difficulty, topic, status) {
  return {
    problem_id: id,
    slug,
    title,
    summary: `Practice ${title}.`,
    difficulty,
    topics: [topic],
    primary_topic: topic,
    status,
    attempts_count: status === "not_started" ? 0 : 1,
    position: id,
  };
}

function makeStage(index, key, title, state, problems) {
  const solved = problems.filter((p) => p.status === "solved").length;
  const attempted = problems.filter((p) => p.status === "attempted").length;
  return {
    index,
    key,
    title,
    state,
    prerequisite_title: index === 0 ? null : "Arrays",
    prerequisite_ready: index === 0 ? null : true,
    problem_count: problems.length,
    solved_count: solved,
    attempted_count: attempted,
    completion_percentage: problems.length ? Math.round((solved / problems.length) * 100) : 0,
    problems,
  };
}

const ARRAYS = [
  makeProblem(1, "two-sum", "Two Sum", "Easy", "Arrays", "solved"),
  makeProblem(2, "single-number", "Single Number", "Easy", "Arrays", "solved"),
];

const STRINGS = [
  makeProblem(3, "valid-anagram", "Valid Anagram", "Easy", "Strings", "solved"),
  makeProblem(4, "valid-palindrome", "Valid Palindrome", "Easy", "Strings", "not_started"),
];

const STACK = [
  makeProblem(5, "valid-parentheses", "Valid Parentheses", "Easy", "Stack", "attempted"),
  makeProblem(6, "min-stack", "Min Stack", "Medium", "Stack", "not_started"),
];

const PATH = {
  total_problems: 6,
  solved_problems: 3,
  attempted_problems: 1,
  completion_percentage: 50,
  stages_total: 3,
  stages_complete: 1,
  current_stage_index: 1,
  current_stage_title: "Strings",
  weak_topics: ["Strings"],
  recommendation: {
    reason_code: "continue_stage",
    reason: "Continue your Strings progression.",
    score: 70,
    stage_index: 1,
    stage_title: "Strings",
    problem: STRINGS[1],
  },
  stages: [
    makeStage(0, "arrays", "Arrays", "complete", ARRAYS),
    makeStage(1, "strings", "Strings", "current", STRINGS),
    makeStage(2, "stack", "Stack", "upcoming", STACK),
  ],
};

const COMPLETE_PATH = {
  ...PATH,
  solved_problems: 6,
  attempted_problems: 0,
  completion_percentage: 100,
  stages_complete: 3,
  current_stage_index: null,
  current_stage_title: null,
  weak_topics: [],
  recommendation: null,
  stages: PATH.stages.map((stage) => ({
    ...stage,
    state: "complete",
    solved_count: stage.problem_count,
    attempted_count: 0,
    completion_percentage: 100,
    problems: stage.problems.map((p) => ({ ...p, status: "solved" })),
  })),
};

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

/** The last thing a loaded path renders, so it doubles as a settle point. */
function waitForPath() {
  return screen.findByRole("heading", { name: "Path stages" });
}

beforeEach(() => {
  vi.clearAllMocks();
  getStoredToken.mockReturnValue("token-123");
});

describe("learningPathService", () => {
  it("reads the path from the one endpoint, carrying the session token", async () => {
    apiClient.get.mockResolvedValue(PATH);

    await learningPathService.path();

    expect(apiClient.get).toHaveBeenCalledWith("/learning-path", { token: "token-123" });
    const [path, options] = apiClient.get.mock.calls[0];
    expect(path).toBe("/learning-path");
    // The learner is identified by the token alone: no user id is placed in the
    // request, so the client cannot ask for somebody else's path.
    expect(options).not.toHaveProperty("userId");
    expect(options).not.toHaveProperty("user_id");
  });

  it("sends no token when the session is empty", async () => {
    getStoredToken.mockReturnValue("");
    apiClient.get.mockResolvedValue(PATH);

    await learningPathService.path();

    expect(apiClient.get).toHaveBeenCalledWith("/learning-path", {});
  });
});

describe("useLearningPath", () => {
  function PathProbe({ enabled = true }) {
    const { data, loading, error } = useLearningPath({ enabled });
    if (loading) return <p>loading</p>;
    if (error) return <p>error: {error}</p>;
    return <p>{data ? data.current_stage_title : "no data"}</p>;
  }

  it("resolves the learner's path", async () => {
    apiClient.get.mockResolvedValue(PATH);
    renderInRouter(<PathProbe />);

    expect(await screen.findByText("Strings")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/learning-path", { token: "token-123" });
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("reports a failed request as an error", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request failed (500)."));
    renderInRouter(<PathProbe />);

    expect(await screen.findByText(/error: the api request failed/i)).toBeInTheDocument();
  });

  it("makes no request while the session is still restoring", async () => {
    renderInRouter(<PathProbe enabled={false} />);

    expect(await screen.findByText("no data")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

describe("LearningPathPage", () => {
  it("shows a loading state before the path arrives", () => {
    renderInRouter(<LearningPathPage />);
    expect(screen.getByText(/building your learning path/i)).toBeInTheDocument();
  });

  it("renders the metrics, the recommendation, and the reason", async () => {
    apiClient.get.mockResolvedValue(PATH);
    renderInRouter(<LearningPathPage />);

    await waitForPath();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("3 of 6 solved")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument();
    expect(screen.getAllByText("Valid Palindrome")).not.toHaveLength(0);
    expect(screen.getByText("Continue your Strings progression.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start problem/i })).toHaveAttribute(
      "href",
      "/problems/valid-palindrome",
    );
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("lists every stage exactly once, in curriculum order, with its state", async () => {
    apiClient.get.mockResolvedValue(PATH);
    const { container } = renderInRouter(<LearningPathPage />);
    await waitForPath();

    const rows = container.querySelectorAll(".stage-list .stage-row");
    expect(rows).toHaveLength(3);
    const titles = Array.from(rows).map((row) => row.querySelector("strong")?.textContent);
    expect(titles).toEqual(["Arrays", "Strings", "Stack"]);
    const states = Array.from(rows).map((row) => row.getAttribute("data-state"));
    expect(states).toEqual(["complete", "current", "upcoming"]);
    expect(rows[0]).toHaveTextContent("2/2 solved · Complete");
    expect(rows[1]).toHaveTextContent("1/2 solved · In progress");
    expect(rows[2]).toHaveTextContent("0/2 solved · Upcoming");

    // Only the current stage gets its own practice section.
    expect(screen.getByRole("heading", { name: "Stage 2 · Strings" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Stage 1 · Arrays" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Stage 3 · Stack" })).not.toBeInTheDocument();
  });

  it("offers only the current stage's problems in the practice grid", async () => {
    apiClient.get.mockResolvedValue(PATH);
    const { container } = renderInRouter(<LearningPathPage />);
    await waitForPath();

    const cards = container.querySelectorAll(".problem-grid .problem-card");
    expect(cards).toHaveLength(2);
    for (const card of cards) {
      expect(card.getAttribute("href")).toMatch(/^\/problems\//);
      expect(card.getAttribute("href")).not.toMatch(/user|token/i);
    }
    expect(container).toHaveTextContent("Valid Anagram");
    expect(container).not.toHaveTextContent("Min Stack");
  });

  it("surfaces the weak topics without a second request", async () => {
    apiClient.get.mockResolvedValue(PATH);
    const { container } = renderInRouter(<LearningPathPage />);
    await waitForPath();

    expect(screen.getAllByText("Topics to shore up")).toHaveLength(2);
    const pills = container.querySelectorAll(".path-topic-list .status-pill");
    expect(pills).toHaveLength(1);
    expect(pills[0]).toHaveTextContent("Strings");
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("explains an expired session instead of a generic error", async () => {
    const failure = new Error("Not authenticated");
    failure.status = 401;
    apiClient.get.mockRejectedValue(failure);
    renderInRouter(<LearningPathPage />);

    expect(
      await screen.findByText(/sign in again to load your learning path/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/something needs attention/i)).not.toBeInTheDocument();
  });

  it("surfaces a load failure with a retry affordance", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request timed out."));
    renderInRouter(<LearningPathPage />);

    expect(await screen.findByText(/the api request timed out/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(apiClient.get.mock.calls.length).toBeGreaterThan(1));
  });

  it("shows the path-complete state when nothing is left to recommend", async () => {
    apiClient.get.mockResolvedValue(COMPLETE_PATH);
    renderInRouter(<LearningPathPage />);

    expect(await screen.findByText(/path complete/i)).toBeInTheDocument();
    expect(screen.getByText("Every published problem is solved.")).toBeInTheDocument();
    expect(screen.queryByText("Valid Palindrome")).not.toBeInTheDocument();
    expect(screen.getByText(/nothing to shore up/i)).toBeInTheDocument();
  });

  it("leaves the page body empty when no path could be loaded", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request timed out."));
    renderInRouter(<LearningPathPage />);

    await screen.findByText(/the api request timed out/i);
    expect(screen.queryByText("Path stages")).not.toBeInTheDocument();
  });
});

describe("ContinueLearningCard", () => {
  it("shows a loading state before the path arrives", () => {
    renderInRouter(<ContinueLearningCard loading path={null} />);
    expect(screen.getByText(/loading your learning path/i)).toBeInTheDocument();
  });

  it("names the recommended problem and why it was picked", () => {
    renderInRouter(<ContinueLearningCard path={PATH} />);

    expect(screen.getByRole("heading", { name: "Continue learning" })).toBeInTheDocument();
    expect(screen.getByText("Valid Palindrome")).toBeInTheDocument();
    expect(screen.getByText("Continue your Strings progression.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start problem/i })).toHaveAttribute(
      "href",
      "/problems/valid-palindrome",
    );
    expect(screen.getByText("Easy")).toBeInTheDocument();
    expect(screen.getByText("Strings")).toBeInTheDocument();
  });

  it("confirms completion when there is no recommendation left", () => {
    renderInRouter(<ContinueLearningCard path={COMPLETE_PATH} />);

    expect(screen.getByText(/path complete/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view the path/i })).toHaveAttribute(
      "href",
      "/learning-path",
    );
  });

  it("prompts a signed-out learner instead of showing a problem", () => {
    renderInRouter(<ContinueLearningCard path={null} />);
    expect(screen.getByText(/sign in to see your path/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /start problem/i })).not.toBeInTheDocument();
  });

  it("explains an expired session", () => {
    renderInRouter(
      <ContinueLearningCard error="Not authenticated" errorStatus={401} path={null} />,
    );
    expect(screen.getByText(/sign in again to load your learning path/i)).toBeInTheDocument();
  });

  it("surfaces a load failure with a retry affordance", async () => {
    const onRetry = vi.fn();
    renderInRouter(
      <ContinueLearningCard error="The API request timed out." onRetry={onRetry} path={null} />,
    );

    expect(screen.getByText(/the api request timed out/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not fetch its own path; the caller supplies it", () => {
    renderInRouter(<ContinueLearningCard path={PATH} />);
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

describe("navigation wiring", () => {
  it("exposes a Learning Path entry pointing at the registered route", async () => {
    const { navigationItems } = await import("../../app/navigation");
    const item = navigationItems.find((entry) => entry.to === "/learning-path");
    expect(item).toBeTruthy();
    expect(item.label).toBe("Learning Path");
    expect(item.icon).toBe("path");
  });
});
