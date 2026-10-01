import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import JudgeResultPanel from "./JudgeResultPanel";
import WorkspacePage from "../../pages/WorkspacePage";
import { judgeService } from "./judgeService";
import {
  AD_HOC_NOTE,
  RUN_NOTE,
  formatCaseCounts,
  formatPeakMemory,
  verdictLabel,
  verdictTone,
} from "./judgeStatus";
import { problemApi } from "../../services/platformService";
import { progressService } from "../progress/progressService";
import { submissionService } from "../submissions/submissionService";
import { useAuth } from "../auth/useAuth";

/**
 * The run feature reports what an execution actually did, so the assertions that
 * matter most are the negative ones: that the UI never reports a verdict for a run
 * that compared nothing, never renders a partial run as a complete one, and never
 * invents a language or a measurement the API did not send.
 *
 * `judgeService` is mocked, so nothing here executes anything. What the panel
 * renders is judged, not what a program does.
 */

vi.mock("./judgeService", () => ({
  RUN_TIMEOUT_MS: 60000,
  judgeService: { languages: vi.fn(), run: vi.fn() },
}));

// The workspace test renders the real page, so its collaborators are replaced
// rather than stubbed by hand: Monaco needs a real layout engine.
vi.mock("../problems/CodeEditor", () => ({
  default: ({ onChange, value }) => (
    <textarea aria-label="Code editor" onChange={(event) => onChange(event.target.value)} value={value} />
  ),
}));
vi.mock("../../services/platformService", () => ({
  problemApi: { get: vi.fn() },
}));
vi.mock("../progress/progressService", () => ({
  progressService: { problem: vi.fn(), setStatus: vi.fn(), recordAttempt: vi.fn() },
}));
vi.mock("../submissions/submissionService", () => ({
  submissionService: { create: vi.fn(), list: vi.fn(), detail: vi.fn(), forProblem: vi.fn() },
}));
vi.mock("../auth/useAuth", () => ({ useAuth: vi.fn() }));

const PAGE_PROBLEM = {
  id: 2,
  slug: "two-sum",
  title: "Two Sum",
  summary: "Find the pair that adds up.",
  difficulty: "Easy",
  topics: ["Arrays", "Two Pointers"],
  examples: [{ input: "[2,7,11,15]\n2", output: "[0,1]" }],
  constraints: "1 <= nums.length <= 10^4",
  time_limit_ms: 1000,
  memory_limit_mb: 256,
  starter_code: { javascript: "function solve() {}", python: "def solve():\n    pass\n" },
};

const PROGRESS_RECORD = {
  problem_id: 2,
  slug: "two-sum",
  title: "Two Sum",
  difficulty: "Easy",
  topics: ["Arrays", "Two Pointers"],
  status: "not_started",
  attempts_count: 0,
  best_runtime_ms: null,
  best_memory_mb: null,
  last_attempted_at: null,
  solved_at: null,
  created_at: "2026-02-09T09:00:00Z",
  updated_at: "2026-02-09T09:00:00Z",
};

function gradedRun(overrides = {}) {
  return {
    problem_id: 2,
    problem_slug: "two-sum",
    language: "python",
    verdict: "accepted",
    cases_run: 2,
    cases_passed: 2,
    cases_total: 2,
    error_message: null,
    total_runtime_ms: 42,
    peak_memory_mb: 18.25,
    truncated: false,
    time_limit_ms: 1000,
    memory_limit_mb: 256,
    ad_hoc: null,
    cases: [
      {
        index: 0,
        is_hidden: false,
        passed: true,
        verdict: "accepted",
        error_message: null,
        duration_ms: 20,
        case_input: "2 2 7\n9\n",
        expected_output: "0 1",
        actual_output: "0 1",
      },
      {
        index: 1,
        is_hidden: false,
        passed: true,
        verdict: "accepted",
        error_message: null,
        duration_ms: 22,
        case_input: "2 3 4\n6\n",
        expected_output: "1 2",
        actual_output: "1 2",
      },
    ],
    ...overrides,
  };
}

function adHocRun(overrides = {}) {
  return {
    problem_id: 2,
    problem_slug: "two-sum",
    language: "python",
    verdict: null,
    cases_run: 0,
    cases_passed: 0,
    cases_total: 0,
    error_message: null,
    total_runtime_ms: 17,
    peak_memory_mb: 12.5,
    truncated: false,
    time_limit_ms: 1000,
    memory_limit_mb: 256,
    ad_hoc: { stdin: "4 2 7 11 15\n9\n", stdout: "0 1\n", stderr: "", exit_code: 0, timed_out: false },
    cases: [],
    ...overrides,
  };
}

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={["/problems/two-sum"]}>
      <Routes>
        <Route element={<WorkspacePage />} path="/problems/:slug" />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ isAuthenticated: true });
  judgeService.languages.mockResolvedValue({
    items: [
      { id: "javascript", label: "JavaScript" },
      { id: "python", label: "Python" },
    ],
    execution_enabled: true,
  });
});

describe("the verdict vocabulary", () => {
  it("names every verdict the API can report", () => {
    expect(verdictLabel("accepted")).toBe("Accepted");
    expect(verdictLabel("wrong_answer")).toBe("Wrong answer");
    expect(verdictLabel("time_limit_exceeded")).toBe("Time limit exceeded");
    expect(verdictLabel("runtime_error")).toBe("Runtime error");
  });

  it("never presents an absent verdict as a pass", () => {
    expect(verdictLabel(null)).toBe("No verdict");
    expect(verdictLabel(undefined)).toBe("No verdict");
    expect(verdictTone(null)).toBe("neutral");
  });

  it("degrades an unrecognised verdict instead of rendering blank", () => {
    expect(verdictLabel("a_verdict_from_a_future_release")).toBe("Result");
    expect(verdictTone("a_verdict_from_a_future_release")).toBe("neutral");
  });

  it("summarises case counts only for a graded run", () => {
    expect(formatCaseCounts(gradedRun())).toBe("2 of 2 test cases passed");
    // "0 of 0 test cases passed" would read as a failing result, so an ungraded
    // run reports nothing rather than a count.
    expect(formatCaseCounts(adHocRun())).toBeNull();
    expect(formatCaseCounts(null)).toBeNull();
  });

  it("reports an unmeasurable peak as absent rather than zero", () => {
    expect(formatPeakMemory(18.25)).toBe("18.3 MB");
    expect(formatPeakMemory(null)).toBeNull();
    expect(formatPeakMemory(0)).toBeNull();
  });
});

describe("JudgeResultPanel", () => {
  it("says nothing has been run before anything has run", () => {
    renderInRouter(<JudgeResultPanel result={null} running={false} actionError="" />);

    expect(screen.getByText(/nothing has been run yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/accepted/i)).not.toBeInTheDocument();
    expect(RUN_NOTE).toMatch(/visible examples only/i);
    expect(RUN_NOTE).toMatch(/not saved/i);
  });

  it("reports a passing run with its counts, timing, and limits", () => {
    renderInRouter(<JudgeResultPanel result={gradedRun()} running={false} actionError="" />);

    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("2 of 2 test cases passed")).toBeInTheDocument();
    expect(screen.getByText("42 ms")).toBeInTheDocument();
    expect(screen.getByText("18.3 MB")).toBeInTheDocument();
    expect(screen.getByText("1000 ms · 256 MB")).toBeInTheDocument();
    // The qualification belongs next to the green tick, not only in the source: a
    // "visible examples only" run must not read as a cleared hidden suite.
    expect(screen.getByText(/visible examples only/i)).toBeInTheDocument();
  });

  it("shows the input, the expected answer, and the program's output side by side", () => {
    renderInRouter(<JudgeResultPanel result={gradedRun()} running={false} actionError="" />);

    expect(screen.getByText(/2 2 7\s+9/)).toBeInTheDocument();
    expect(screen.getAllByText("0 1").length).toBeGreaterThan(0);
    // The expected answer and the program's own output are shown side by side,
    // so a matching answer legitimately appears twice.
    expect(screen.getAllByText("1 2").length).toBe(2);
    // Every case the run reports is a visible one, so each is labelled with its
    // position in the judge's order.
    expect(screen.getByText(/case 1 · 20 ms/i)).toBeInTheDocument();
    expect(screen.getByText(/case 2 · 22 ms/i)).toBeInTheDocument();
  });

  it("reports a wrong answer with the case that failed, not as a crash", () => {
    const run = gradedRun({
      verdict: "wrong_answer",
      cases_run: 1,
      cases_passed: 0,
      error_message: "The program ran successfully but printed the wrong answer.",
      cases: [
        {
          index: 0,
          is_hidden: false,
          passed: false,
          verdict: "wrong_answer",
          error_message: "The program ran successfully but printed the wrong answer.",
          duration_ms: 20,
          case_input: "2 2 7\n9\n",
          expected_output: "0 1",
          actual_output: "1 1",
        },
      ],
    });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText("Wrong answer")).toBeInTheDocument();
    expect(screen.getByText("1 1")).toBeInTheDocument();
    expect(screen.queryByText("Runtime error")).not.toBeInTheDocument();
  });

  it("marks a truncated run as incomplete, so a partial pass cannot read as a full one", () => {
    const run = gradedRun({
      verdict: "time_limit_exceeded",
      cases_run: 1,
      cases_passed: 1,
      truncated: true,
      error_message: "The judge stopped after 1 of 2 cases to stay inside its own time budget.",
      cases: [gradedRun().cases[0]],
    });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText(/stopped before running every case/i)).toBeInTheDocument();
    expect(screen.getByText(/time budget/i)).toBeInTheDocument();
    expect(screen.getByText("Time limit exceeded")).toBeInTheDocument();
  });

  it("reports a run on the learner's own input with no verdict at all", () => {
    renderInRouter(<JudgeResultPanel result={adHocRun()} running={false} actionError="" />);

    expect(screen.getByText("No verdict")).toBeInTheDocument();
    expect(screen.queryByText("Accepted")).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+ of \d+ test cases passed/i)).not.toBeInTheDocument();
    expect(screen.getByText("Your own, not graded")).toBeInTheDocument();
    expect(screen.getByText("0 1")).toBeInTheDocument();
    expect(screen.getByText("Exit code")).toBeInTheDocument();
    expect(AD_HOC_NOTE).toMatch(/no verdict and no pass count/i);
  });

  it("shows an empty answer, because an empty output is itself the observation", () => {
    const run = adHocRun({ ad_hoc: { stdin: "1\n", stdout: "", stderr: "", exit_code: 0, timed_out: false } });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText("Your output")).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
  });

  it("reports a crash on the learner's own input without inventing a verdict", () => {
    const run = adHocRun({
      error_message: "The program exited with code 1.\nTraceback: bad index",
      ad_hoc: {
        stdin: "1\n",
        stdout: "",
        stderr: "Traceback: bad index",
        exit_code: 1,
        timed_out: false,
      },
    });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText("No verdict")).toBeInTheDocument();
    expect(screen.getByText(/exited with code 1/i)).toBeInTheDocument();
    expect(screen.getByText("Traceback: bad index")).toBeInTheDocument();
  });

  it("marks a timeout on the learner's own input", () => {
    const run = adHocRun({
      error_message: "The program ran longer than the time limit.",
      ad_hoc: { stdin: "1\n", stdout: "", stderr: "", exit_code: null, timed_out: true },
    });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText("Timed out")).toBeInTheDocument();
    expect(screen.getByText("No verdict")).toBeInTheDocument();
  });

  it("says the judge ran no cases rather than showing an empty list", () => {
    const run = gradedRun({ cases: [], cases_run: 0, cases_passed: 0, cases_total: 0 });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText(/executed no cases/i)).toBeInTheDocument();
  });

  it("says the peak was not measurable where the platform cannot measure it", () => {
    const run = gradedRun({ peak_memory_mb: null });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    expect(screen.getByText("Not measurable here")).toBeInTheDocument();
    // Zero would read as a measurement.
    expect(screen.queryByText("0.0 MB")).not.toBeInTheDocument();
  });

  it("shows that a run is in flight", () => {
    renderInRouter(<JudgeResultPanel result={null} running actionError="" />);

    expect(screen.getByText(/running your code in a separate process/i)).toBeInTheDocument();
  });

  it("reports a failed request without claiming a result or clearing the previous one", () => {
    const run = gradedRun();
    renderInRouter(
      <JudgeResultPanel
        actionError="The API request timed out."
        result={run}
        running={false}
      />,
    );

    expect(screen.getByText("The API request timed out.")).toBeInTheDocument();
    // A request that never completed says nothing about whether the program is
    // correct, so the earlier observation stays on screen.
    expect(screen.getByText("2 of 2 test cases passed")).toBeInTheDocument();
  });
});

describe("the workspace run affordance", () => {
  beforeEach(() => {
    PAGE_PROBLEM.starter_code = { javascript: "function solve() {}", python: "def solve():\n    pass\n" };
    PAGE_PROBLEM.time_limit_ms = 1000;
    PAGE_PROBLEM.memory_limit_mb = 256;
    problemApi.get.mockResolvedValue(PAGE_PROBLEM);
    progressService.problem.mockResolvedValue(PROGRESS_RECORD);
    submissionService.forProblem.mockResolvedValue({ items: [], total: 0 });
    submissionService.create.mockResolvedValue({ id: 31, language: "python", status: "queued" });
  });

  it("draws the language tabs from the registry, not from a list in the bundle", async () => {
    judgeService.languages.mockResolvedValue({
      items: [{ id: "python", label: "Python" }],
      execution_enabled: true,
    });
    renderWorkspace();

    // The problem's own starters are shown first, and are then narrowed to what
    // the deployment can run. A language the runner refuses must not be offered:
    // a tab that ends in a 422 is the defect this list exists to prevent.
    await waitFor(() => expect(judgeService.languages).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByRole("tab", { name: /javascript/i })).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("tab", { name: /python/i })).toBeInTheDocument();
  });

  it("falls back to the problem's own languages when the registry cannot be read", async () => {
    judgeService.languages.mockRejectedValue(new Error("The API is unreachable."));
    renderWorkspace();

    // The catalog was validated against the same registry, so the problem's own
    // list is the next most trustworthy answer -- but it is never an invented one.
    await waitFor(() => expect(judgeService.languages).toHaveBeenCalled());
    expect(await screen.findByRole("tab", { name: /python/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /javascript/i })).toBeInTheDocument();
  });

  it("runs the editor's code and reports the result", async () => {
    judgeService.run.mockResolvedValue(gradedRun());
    renderWorkspace();

    const editor = await screen.findByLabelText(/code editor/i);
    await userEvent.clear(editor);
    await userEvent.type(editor, "print(1)");
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));

    expect(await screen.findByText("Accepted")).toBeInTheDocument();
    expect(judgeService.run).toHaveBeenCalledWith({
      problemId: 2,
      language: "javascript",
      sourceCode: "print(1)",
      stdin: undefined,
    });
  });

  it("runs in whichever language tab is selected", async () => {
    judgeService.run.mockResolvedValue(gradedRun({ language: "python" }));
    renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("tab", { name: /python/i }));
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));

    await waitFor(() =>
      expect(judgeService.run).toHaveBeenCalledWith(
        expect.objectContaining({ language: "python" }),
      ),
    );
  });

  it("sends the learner's own input when they ask for it, and claims no verdict", async () => {
    judgeService.run.mockResolvedValue(adHocRun());
    renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("button", { name: /my own input/i }));
    await userEvent.type(screen.getByLabelText(/standard input/i), "4 2 7 11 15\n9");
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));

    expect(await screen.findByText("No verdict")).toBeInTheDocument();
    expect(judgeService.run).toHaveBeenCalledWith(
      expect.objectContaining({ stdin: "4 2 7 11 15\n9" }),
    );
    expect(screen.queryByText("Accepted")).not.toBeInTheDocument();
  });

  it("goes back to the problem's cases when own-input mode is switched off", async () => {
    judgeService.run.mockResolvedValue(gradedRun());
    renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("button", { name: /my own input/i }));
    await userEvent.click(screen.getByRole("button", { name: /visible test cases/i }));
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));

    await waitFor(() =>
      expect(judgeService.run).toHaveBeenCalledWith(expect.objectContaining({ stdin: undefined })),
    );
    expect(screen.queryByLabelText(/standard input/i)).not.toBeInTheDocument();
  });

  it("discards a result when the language changes, because it belonged to other code", async () => {
    judgeService.run.mockResolvedValue(gradedRun());
    renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));
    expect(await screen.findByText("2 of 2 test cases passed")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: /python/i }));

    await waitFor(() => expect(screen.queryByText("2 of 2 test cases passed")).not.toBeInTheDocument());
    expect(screen.getByText(/nothing has been run yet/i)).toBeInTheDocument();
  });

  it("shows the problem's real limits instead of a placeholder", async () => {
    renderWorkspace();

    expect(await screen.findByText("1000 ms · 256 MB")).toBeInTheDocument();
    expect(screen.queryByText(/time limit not configured/i)).not.toBeInTheDocument();
  });

  it("surfaces a rejected run without claiming a verdict", async () => {
    judgeService.run.mockRejectedValue(new Error("Code execution is disabled on this deployment."));
    renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));

    expect(await screen.findByText(/execution is disabled on this deployment/i)).toBeInTheDocument();
    expect(screen.queryByText("Accepted")).not.toBeInTheDocument();
    expect(screen.queryByText("No verdict")).not.toBeInTheDocument();
  });

  it("does not save a run as a submission record", async () => {
    const { submissionService } = await import("../submissions/submissionService");
    judgeService.run.mockResolvedValue(gradedRun());
    renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("button", { name: /run test cases/i }));
    await screen.findByText("Accepted");

    // Run is a debugging aid: it must not create a submission or move progress.
    expect(submissionService.create).not.toHaveBeenCalled();
    const { progressService } = await import("../progress/progressService");
    expect(progressService.setStatus).not.toHaveBeenCalled();
    expect(progressService.recordAttempt).not.toHaveBeenCalled();
  });

  it("states the Run/Submit distinction next to the real Run button", async () => {
    renderWorkspace();

    // Run and Submit sit side by side and grade very differently. A learner
    // reading only the buttons would not know that, so the page has to say it.
    expect(await screen.findAllByText(/hidden ones included/i)).not.toHaveLength(0);
  });
});

describe("the result panel's own accessibility", () => {
  it("labels a failing case for a screen reader, not only by colour", () => {
    const run = gradedRun({
      verdict: "wrong_answer",
      cases_run: 1,
      cases_passed: 0,
      cases: [
        {
          index: 0,
          is_hidden: false,
          passed: false,
          verdict: "wrong_answer",
          error_message: null,
          duration_ms: 20,
          case_input: "1\n",
          expected_output: "0",
          actual_output: "1",
        },
      ],
    });
    renderInRouter(<JudgeResultPanel result={run} running={false} actionError="" />);

    const caseRow = screen.getByText(/case 1/i).closest(".judge-case");
    expect(within(caseRow).getByLabelText("Failed")).toBeInTheDocument();
  });
});
