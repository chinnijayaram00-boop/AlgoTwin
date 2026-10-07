import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "../../pages/AnalyticsPage";
import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";
import { activeTopics, shortDay, verdictLabel } from "./analyticsFormat";
import { analyticsService } from "./analyticsService";
import { useAnalytics } from "./useAnalytics";

// Only the transport is faked. The service, hook, formatters, and page under
// test stay real, so these tests exercise the actual request the page builds,
// the real request identity rule, and the real empty/failure states.
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

const OVERVIEW = {
  total_problems: 50,
  solved: 3,
  attempted: 3,
  not_started: 44,
  completion_percentage: 6,
  current_streak_days: 2,
  total_submissions: 9,
  judged_submissions: 5,
  accepted_submissions: 2,
  acceptance_rate: 40,
  problems_submitted: 2,
  average_runtime_ms: 84.5,
  average_memory_mb: 18.6,
};

const DIFFICULTY = [
  {
    difficulty: "Easy",
    total: 10,
    solved: 2,
    attempted: 1,
    not_started: 7,
    completion_percentage: 20,
    submissions: 4,
    judged: 4,
    accepted: 2,
    acceptance_rate: 50,
  },
  {
    difficulty: "Medium",
    total: 27,
    solved: 1,
    attempted: 2,
    not_started: 24,
    completion_percentage: 3.7,
    submissions: 5,
    judged: 5,
    accepted: 1,
    acceptance_rate: 20,
  },
  {
    difficulty: "Hard",
    total: 13,
    solved: 0,
    attempted: 0,
    not_started: 13,
    completion_percentage: 0,
    submissions: 0,
    judged: 0,
    accepted: 0,
    acceptance_rate: 0,
  },
];

const TOPICS = [
  {
    topic: "Arrays",
    total: 9,
    solved: 2,
    attempted: 1,
    not_started: 6,
    completion_percentage: 22.2,
  },
  {
    topic: "Hash Maps",
    total: 5,
    solved: 1,
    attempted: 1,
    not_started: 3,
    completion_percentage: 20,
  },
  {
    topic: "Strings",
    total: 6,
    solved: 0,
    attempted: 0,
    not_started: 6,
    completion_percentage: 0,
  },
];

const VERDICTS = [
  { status: "accepted", count: 2, percentage: 22.2 },
  { status: "wrong_answer", count: 3, percentage: 33.3 },
  { status: "queued", count: 4, percentage: 44.5 },
];

const ACTIVITY = [
  { date: "2026-03-14", submissions: 3, attempts: 1, solves: 1 },
  { date: "2026-03-15", submissions: 0, attempts: 0, solves: 0 },
];

const LEARNING_PATH = {
  total_problems: 5,
  solved_problems: 3,
  attempted_problems: 1,
  completion_percentage: 60,
  stages_total: 3,
  stages_complete: 1,
  current_stage_title: "Strings",
  weak_topics: ["Strings"],
  recommended_problem: "Valid Palindrome",
  recommended_reason: "Continue your Strings progression.",
  stages: [
    {
      index: 0,
      title: "Arrays",
      state: "complete",
      problem_count: 2,
      solved_count: 2,
      attempted_count: 0,
      completion_percentage: 100,
    },
    {
      index: 1,
      title: "Strings",
      state: "current",
      problem_count: 2,
      solved_count: 1,
      attempted_count: 1,
      completion_percentage: 50,
    },
    {
      index: 2,
      title: "Stack",
      state: "upcoming",
      problem_count: 1,
      solved_count: 0,
      attempted_count: 0,
      completion_percentage: 0,
    },
  ],
};

const INTERVIEWS = {
  total: 2,
  completed: 1,
  abandoned: 1,
  active: 0,
  average_score: 75,
  best_score: 75,
  questions_total: 4,
  questions_answered: 3,
  questions_accepted: 1,
  acceptance_rate: 33.3,
  scores: [{ interview_id: 1, score: 75, completed_at: "2026-03-15T10:00:00Z", timed_out: false }],
};

const ANALYTICS = {
  overview: OVERVIEW,
  difficulty: DIFFICULTY,
  topics: TOPICS,
  verdicts: VERDICTS,
  activity: ACTIVITY,
  learning_path: LEARNING_PATH,
  interviews: INTERVIEWS,
  activity_days: 30,
  as_of: "2026-03-15",
};

const EMPTY_ANALYTICS = {
  overview: {
    total_problems: 50,
    solved: 0,
    attempted: 0,
    not_started: 50,
    completion_percentage: 0,
    current_streak_days: 0,
    total_submissions: 0,
    judged_submissions: 0,
    accepted_submissions: 0,
    acceptance_rate: 0,
    problems_submitted: 0,
    average_runtime_ms: null,
    average_memory_mb: null,
  },
  difficulty: DIFFICULTY.map((row) => ({ ...row, solved: 0, attempted: 0, not_started: row.total })),
  topics: TOPICS.map((row) => ({ ...row, solved: 0, attempted: 0, not_started: row.total })),
  verdicts: [],
  activity: [
    { date: "2026-03-14", submissions: 0, attempts: 0, solves: 0 },
    { date: "2026-03-15", submissions: 0, attempts: 0, solves: 0 },
  ],
  learning_path: {
    total_problems: 50,
    solved_problems: 0,
    attempted_problems: 0,
    completion_percentage: 0,
    stages_total: 3,
    stages_complete: 0,
    current_stage_title: "Arrays",
    weak_topics: [],
    recommended_problem: null,
    recommended_reason: null,
    stages: [],
  },
  interviews: {
    total: 0,
    completed: 0,
    abandoned: 0,
    active: 0,
    average_score: null,
    best_score: null,
    questions_total: 0,
    questions_answered: 0,
    questions_accepted: 0,
    acceptance_rate: 0,
    scores: [],
  },
  activity_days: 30,
  as_of: "2026-03-15",
};

beforeEach(() => {
  vi.clearAllMocks();
  getStoredToken.mockReturnValue("token-123");
});

describe("analyticsService", () => {
  it("reads the whole summary carrying the session token, without asking whose it is", async () => {
    apiClient.get.mockResolvedValue(ANALYTICS);

    const summary = await analyticsService.summary({ days: 30 });

    expect(summary).toBe(ANALYTICS);
    expect(apiClient.get).toHaveBeenCalledWith("/analytics/summary?days=30", {
      token: "token-123",
    });
    const [path, options] = apiClient.get.mock.calls[0];
    expect(path).toBe("/analytics/summary?days=30");
    // The learner is identified by the token alone: no user id is placed in
    // the request, so the client cannot ask for somebody else's numbers.
    expect(options).not.toHaveProperty("userId");
    expect(options).not.toHaveProperty("user_id");
  });

  it("sends no token when the session is empty", async () => {
    getStoredToken.mockReturnValue("");
    apiClient.get.mockResolvedValue(ANALYTICS);

    await analyticsService.summary();

    expect(apiClient.get).toHaveBeenCalledWith("/analytics/summary", {});
  });

  it("appends the requested activity window", async () => {
    apiClient.get.mockResolvedValue(ANALYTICS);

    await analyticsService.summary({ days: 7 });

    expect(apiClient.get).toHaveBeenCalledWith("/analytics/summary?days=7", {
      token: "token-123",
    });
  });
});

describe("useAnalytics", () => {
  function AnalyticsProbe({ enabled = true }) {
    const { data, loading, error } = useAnalytics({ days: 30, enabled });
    if (loading) return <p>loading</p>;
    if (error) return <p>error: {error}</p>;
    return <p>{data ? `${data.overview.solved}/${data.overview.total_problems}` : "no data"}</p>;
  }

  it("resolves the learner's summary", async () => {
    apiClient.get.mockResolvedValue(ANALYTICS);
    render(<AnalyticsProbe />);

    expect(await screen.findByText("3/50")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/analytics/summary?days=30", {
      token: "token-123",
    });
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("reports a failed request as an error", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request failed (500)."));
    render(<AnalyticsProbe />);

    expect(await screen.findByText(/error: the api request failed/i)).toBeInTheDocument();
  });

  it("makes no request while the session is still restoring", async () => {
    render(<AnalyticsProbe enabled={false} />);

    expect(await screen.findByText("no data")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

describe("analyticsFormat", () => {
  it("labels every verdict the judge can write", () => {
    expect(verdictLabel("accepted")).toBe("Accepted");
    expect(verdictLabel("time_limit_exceeded")).toBe("Time limit exceeded");
    expect(verdictLabel("memory_limit_exceeded")).toBe("Memory limit exceeded");
    expect(verdictLabel("queued")).toBe("Queued");
  });

  it("falls back to a decapitalised slug for a label it has never heard of", () => {
    expect(verdictLabel("compilation_error")).toBe("Compilation error");
  });

  it("shortens a stored day without shifting it across a timezone", () => {
    expect(shortDay("2026-03-14")).toBe("Mar 14");
    expect(shortDay("2026-10-07")).toBe("Oct 7");
  });

  it("keeps the busiest touched topics, in most-solved order, without mutating input", () => {
    const input = [...TOPICS];
    const picked = activeTopics(input);

    expect(picked.map((row) => row.topic)).toEqual(["Arrays", "Hash Maps"]);
    expect(input[2]).toEqual(TOPICS[2]);
  });
});

describe("AnalyticsPage", () => {
  it("shows a loading state before the summary arrives", () => {
    apiClient.get.mockReturnValue(new Promise(() => {}));
    render(<AnalyticsPage />);
    expect(screen.getByText(/loading learning signals/i)).toBeInTheDocument();
  });

  it("renders the overview, breakdowns, activity, path, and interviews in one request", async () => {
    apiClient.get.mockResolvedValue(ANALYTICS);
    render(<AnalyticsPage />);

    expect(
      await screen.findByRole("heading", { name: "Mastery by difficulty" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Topic coverage" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Submission verdicts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Activity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Learning path position" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Mock interview performance" }),
    ).toBeInTheDocument();

    // Overview cards, straight from the response.
    expect(screen.getByText("3/50")).toBeInTheDocument();
    expect(screen.getByText("2 days")).toBeInTheDocument();
    expect(screen.getByText("9", { selector: ".metric-card strong" })).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("85 ms")).toBeInTheDocument();

    // Verdict list, with readable counts beside the wedges.
    expect(screen.getByText("Wrong answer", { selector: ".verdict-list strong" })).toBeInTheDocument();
    expect(screen.getByText("2 submissions")).toBeInTheDocument();
    expect(screen.getByText("44.5%")).toBeInTheDocument();

    // Path position and interview panel.
    expect(screen.getByText("Valid Palindrome")).toBeInTheDocument();
    expect(screen.getByText(/continue your strings progression/i)).toBeInTheDocument();
    expect(screen.getByText("Current stage: Strings")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument();

    // One read, not a family of requests.
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("shows the actual activity window and switches it with one request each", async () => {
    apiClient.get.mockResolvedValue(ANALYTICS);
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    await screen.findByRole("heading", { name: "Activity" });
    expect(screen.getByRole("button", { name: "30 days" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "7 days" }));

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/analytics/summary?days=7", {
        token: "token-123",
      }),
    );
    expect(screen.getByRole("button", { name: "7 days" })).toHaveAttribute("aria-pressed", "true");
  });

  it("explains an empty learner instead of drawing zero-width charts", async () => {
    apiClient.get.mockResolvedValue(EMPTY_ANALYTICS);
    render(<AnalyticsPage />);

    expect(
      await screen.findByRole("heading", { name: "Mastery by difficulty" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No topic activity yet")).toBeInTheDocument();
    expect(screen.getByText("No submissions yet")).toBeInTheDocument();
    expect(screen.getByText("No activity in this window")).toBeInTheDocument();
    expect(screen.getByText("No mock interviews yet")).toBeInTheDocument();
    expect(screen.getByText("Every published problem is solved.")).toBeInTheDocument();
    expect(screen.getByText("Nothing to shore up")).toBeInTheDocument();
  });

  it("explains an expired session instead of a generic error", async () => {
    const failure = new Error("Not authenticated");
    failure.status = 401;
    apiClient.get.mockRejectedValue(failure);
    render(<AnalyticsPage />);

    expect(
      await screen.findByText(/sign in again to load your analytics/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/something needs attention/i)).not.toBeInTheDocument();
  });

  it("surfaces a load failure with a retry affordance", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request timed out."));
    render(<AnalyticsPage />);

    expect(await screen.findByText(/the api request timed out/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(apiClient.get.mock.calls.length).toBeGreaterThan(1));
  });
});