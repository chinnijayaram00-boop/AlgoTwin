import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProblemProgressPanel from "./ProblemProgressPanel";
import ProgressPanel from "./ProgressPanel";
import ProgressStatusPill from "./ProgressStatusPill";
import { progressService } from "./progressService";
import { useProgressList, useProgressSummary } from "./useProgress";

vi.mock("./progressService", () => ({
  progressService: {
    summary: vi.fn(),
    problems: vi.fn(),
    problem: vi.fn(),
    setStatus: vi.fn(),
    recordAttempt: vi.fn(),
  },
}));

const SUMMARY = {
  user_id: 7,
  total_problems: 8,
  solved: 3,
  attempted: 2,
  not_started: 3,
  completion_percentage: 37.5,
  current_streak_days: 4,
  total_attempts: 9,
  problems_with_attempts: 4,
  best_runtime_ms: 142,
  best_memory_mb: 18.5,
  total_by_difficulty: { Easy: 4, Medium: 3, Hard: 1 },
  solved_by_difficulty: { Easy: 2, Medium: 1, Hard: 0 },
  total_by_topic: { Arrays: 3, Graphs: 3, "Dynamic programming": 2 },
  solved_by_topic: { Arrays: 2, Graphs: 1 },
  last_attempted_at: "2026-02-10T09:00:00",
  last_solved_at: "2026-02-11T09:00:00",
  updated_at: "2026-02-11T09:00:00",
};

const RECORD = {
  user_id: 7,
  problem_id: 12,
  slug: "two-sum",
  title: "Two Sum",
  difficulty: "Easy",
  topics: ["Arrays"],
  status: "attempted",
  attempts_count: 2,
  best_runtime_ms: null,
  best_memory_mb: null,
  best_time_ms: null,
  last_attempted_at: "2026-02-10T09:00:00",
  solved_at: null,
  updated_at: "2026-02-10T09:00:00",
  created_at: "2026-02-09T09:00:00",
};

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProgressPanel", () => {
  it("shows a loading state before the summary arrives", () => {
    renderInRouter(<ProgressPanel loading summary={null} />);
    expect(screen.getByText(/loading your progress/i)).toBeInTheDocument();
  });

  it("renders the summary counts, streak, and breakdowns", () => {
    renderInRouter(<ProgressPanel summary={SUMMARY} />);

    expect(screen.getByText("37.5%")).toBeInTheDocument();
    expect(screen.getByText("3 of 8 solved")).toBeInTheDocument();
    expect(screen.getByText(/day streak/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /3 solved, 2 attempted, 3 not started/i })).toBeInTheDocument();

    expect(screen.getByText("By difficulty")).toBeInTheDocument();
    expect(screen.getByText("Easy")).toBeInTheDocument();
    expect(screen.getByText("2/4")).toBeInTheDocument();
    expect(screen.getByText("By topic")).toBeInTheDocument();
    expect(screen.getByText("Arrays")).toBeInTheDocument();
  });

  it("shows an empty state when the catalog has no problems", () => {
    renderInRouter(
      <ProgressPanel
        summary={{ ...SUMMARY, total_problems: 0, solved: 0, attempted: 0, not_started: 0 }}
      />,
    );
    expect(screen.getByText(/no problems to track/i)).toBeInTheDocument();
  });

  it("shows an empty state when there is no summary at all", () => {
    renderInRouter(<ProgressPanel summary={null} />);
    expect(screen.getByText(/no progress yet/i)).toBeInTheDocument();
  });

  it("surfaces a load failure with a retry affordance", async () => {
    const onRetry = vi.fn();
    renderInRouter(<ProgressPanel error="Progress is unavailable." onRetry={onRetry} />);

    expect(screen.getByText(/progress is unavailable/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("explains an expired session instead of a generic error", () => {
    renderInRouter(<ProgressPanel error="Not authenticated" errorStatus={401} />);
    expect(screen.getByText(/sign in again to load your progress/i)).toBeInTheDocument();
  });
});

describe("ProgressStatusPill", () => {
  it("labels every known status", () => {
    const solved = renderInRouter(<ProgressStatusPill status="solved" />);
    expect(screen.getByText("Solved")).toBeInTheDocument();
    solved.unmount();

    const attempted = renderInRouter(<ProgressStatusPill status="attempted" />);
    expect(screen.getByText("Attempted")).toBeInTheDocument();
    attempted.unmount();

    const notStarted = renderInRouter(<ProgressStatusPill status="not_started" />);
    expect(screen.getByText("Not Started")).toBeInTheDocument();
    notStarted.unmount();
  });

  it("falls back to Not Started for an unknown status", () => {
    renderInRouter(<ProgressStatusPill status="archived_by_a_future_version" />);
    expect(screen.getByText("Not Started")).toBeInTheDocument();
  });
});

describe("ProblemProgressPanel", () => {
  it("shows the current status, facts, and a self-reported disclaimer", async () => {
    progressService.problem.mockResolvedValue(RECORD);
    renderInRouter(<ProblemProgressPanel problemId={12} />);

    expect(await screen.findByText("Attempted")).toBeInTheDocument();
    expect(screen.getByText(/started, not solved/i)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/recorded by you, not verified by a judge/i)).toBeInTheDocument();
  });

  it("marks a problem as solved through the status endpoint", async () => {
    progressService.problem.mockResolvedValue(RECORD);
    progressService.setStatus.mockResolvedValue({ ...RECORD, status: "solved" });
    renderInRouter(<ProblemProgressPanel problemId={12} />);

    await userEvent.click(await screen.findByRole("button", { name: /mark as solved/i }));

    await waitFor(() => expect(progressService.setStatus).toHaveBeenCalledWith(12, "solved"));
    // The panel refetches after a change, so the view cannot drift from storage.
    await waitFor(() => expect(progressService.problem.mock.calls.length).toBeGreaterThan(1));
  });

  it("records an extra attempt", async () => {
    progressService.problem.mockResolvedValue(RECORD);
    progressService.recordAttempt.mockResolvedValue({ ...RECORD, attempts_count: 3 });
    renderInRouter(<ProblemProgressPanel problemId={12} />);

    await userEvent.click(await screen.findByRole("button", { name: /i attempted this/i }));
    await waitFor(() => expect(progressService.recordAttempt).toHaveBeenCalledWith(12, {}));
  });

  it("resets a solved problem back to not started", async () => {
    progressService.problem.mockResolvedValue({ ...RECORD, status: "solved" });
    progressService.setStatus.mockResolvedValue({ ...RECORD, status: "not_started" });
    renderInRouter(<ProblemProgressPanel problemId={12} />);

    await userEvent.click(await screen.findByRole("button", { name: /^reset$/i }));
    await waitFor(() =>
      expect(progressService.setStatus).toHaveBeenCalledWith(12, "not_started"),
    );
  });

  it("reports a failed change without losing the loaded record", async () => {
    progressService.problem.mockResolvedValue(RECORD);
    progressService.setStatus.mockRejectedValue(new Error("Could not save progress."));
    renderInRouter(<ProblemProgressPanel problemId={12} />);

    await userEvent.click(await screen.findByRole("button", { name: /mark as solved/i }));
    expect(await screen.findByText(/could not save progress/i)).toBeInTheDocument();
    expect(screen.getByText("Attempted")).toBeInTheDocument();
  });

  it("shows a load failure with a retry affordance", async () => {
    progressService.problem.mockRejectedValue(new Error("Progress is unavailable."));
    renderInRouter(<ProblemProgressPanel problemId={12} />);

    expect(await screen.findByText(/progress is unavailable/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(progressService.problem.mock.calls.length).toBeGreaterThan(1));
  });

  it("does not request progress when disabled", () => {
    renderInRouter(<ProblemProgressPanel enabled={false} problemId={12} />);
    expect(progressService.problem).not.toHaveBeenCalled();
  });
});

describe("useProgressSummary", () => {
  function SummaryProbe() {
    const { data, loading, error } = useProgressSummary();
    if (loading) return <p>loading</p>;
    if (error) return <p>error: {error}</p>;
    return <p>solved {data.solved} of {data.total_problems}</p>;
  }

  it("resolves the learner's own summary", async () => {
    progressService.summary.mockResolvedValue(SUMMARY);
    renderInRouter(<SummaryProbe />);

    expect(await screen.findByText("solved 3 of 8")).toBeInTheDocument();
    expect(progressService.summary).toHaveBeenCalledTimes(1);
  });

  it("reports a failed summary request as an error", async () => {
    progressService.summary.mockRejectedValue(new Error("Progress is unavailable."));
    renderInRouter(<SummaryProbe />);

    expect(await screen.findByText(/error: progress is unavailable/i)).toBeInTheDocument();
  });

  it("makes no request when the learner is not signed in", async () => {
    function SignedOutProbe() {
      const { data } = useProgressSummary({ enabled: false });
      return <p>{data ? "loaded" : "not requested"}</p>;
    }
    renderInRouter(<SignedOutProbe />);

    expect(await screen.findByText("not requested")).toBeInTheDocument();
    expect(progressService.summary).not.toHaveBeenCalled();
  });
});

describe("useProgressList", () => {
  function ListProbe({ params }) {
    const { data, loading, error } = useProgressList(params);
    if (loading) return <p>loading</p>;
    if (error) return <p>error: {error}</p>;
    return (
      <ul>
        {data.items.map((problem) => (
          <li key={problem.problem_id}>
            {problem.title} · {problem.status}
          </li>
        ))}
      </ul>
    );
  }

  it("requests the whole published catalog by default", async () => {
    progressService.problems.mockResolvedValue({
      items: [
        { problem_id: 1, title: "Two Sum", status: "attempted" },
        { problem_id: 2, title: "Coin Change", status: "not_started" },
      ],
      total: 2,
      limit: 50,
      offset: 0,
    });
    renderInRouter(<ListProbe />);

    expect(await screen.findByText("Two Sum · attempted")).toBeInTheDocument();
    expect(progressService.problems).toHaveBeenCalledWith({
      status: undefined,
      difficulty: undefined,
      topic: undefined,
      limit: 50,
      offset: 0,
    });
  });

  it("passes the status and difficulty filters to the API", async () => {
    progressService.problems.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    renderInRouter(<ListProbe params={{ status: "solved", difficulty: "Hard" }} />);

    await waitFor(() =>
      expect(progressService.problems).toHaveBeenCalledWith({
        status: "solved",
        difficulty: "Hard",
        topic: undefined,
        limit: 50,
        offset: 0,
      }),
    );
  });

  it("reports a failed list request as an error", async () => {
    progressService.problems.mockRejectedValue(new Error("Progress is unavailable."));
    renderInRouter(<ListProbe />);

    expect(await screen.findByText(/error: progress is unavailable/i)).toBeInTheDocument();
  });
});
