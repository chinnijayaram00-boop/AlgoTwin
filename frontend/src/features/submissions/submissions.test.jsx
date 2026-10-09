import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProblemSubmissionPanel from "./ProblemSubmissionPanel";
import SubmissionDetail from "./SubmissionDetail";
import SubmissionHistory from "./SubmissionHistory";
import SubmissionStatusPill from "./SubmissionStatusPill";
import WorkspacePage from "../../pages/WorkspacePage";
import { progressService } from "../progress/progressService";
import { submissionService } from "./submissionService";
import { useProblemSubmissions, useSubmissionList } from "./useSubmissions";
import { problemApi } from "../../services/platformService";
import { useAuth } from "../auth/useAuth";
import { judgeService } from "../judge/judgeService";

/**
 * The submission feature is judged, so the assertions that matter most are about
 * what the UI claims: that a verdict is shown as the judge's verdict, that a
 * measurement the judge did not take is never implied, and that the UI cannot
 * tell "missing" from "not yours".
 */

vi.mock("./submissionService", () => ({
  submissionService: {
    create: vi.fn(),
    list: vi.fn(),
    detail: vi.fn(),
    forProblem: vi.fn(),
  },
}));

// The workspace test below renders the real page, so its collaborators are
// replaced rather than stubbed by hand: Monaco needs a real layout engine, and
// the problem and progress payloads are not what this file is about.
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
// The workspace now runs code. Its collaborator is replaced like the others, so
// this file keeps testing what a *record* is and not what a run reports.
vi.mock("../judge/judgeService", () => ({
  judgeService: { languages: vi.fn(), run: vi.fn() },
}));
vi.mock("../auth/useAuth", () => ({ useAuth: vi.fn() }));

function submission(overrides = {}) {
  return {
    id: 31,
    problem_id: 2,
    problem_slug: "two-sum",
    problem_title: "Two Sum",
    language: "python",
    status: "queued",
    test_cases_passed: null,
    test_cases_total: null,
    runtime_ms: null,
    memory_mb: null,
    error_message: null,
    submitted_at: "2026-02-10T09:00:00Z",
    judged_at: null,
    ...overrides,
  };
}

/** A graded record, as `POST /submissions` now returns it. */
function judged(overrides = {}) {
  return submission({
    status: "accepted",
    test_cases_passed: 7,
    test_cases_total: 7,
    runtime_ms: 412,
    memory_mb: 18,
    error_message: null,
    judged_at: "2026-02-10T09:00:04Z",
    ...overrides,
  });
}

function page(items, overrides = {}) {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 0, ...overrides };
}

const PAGE_PROBLEM = {
  id: 2,
  slug: "two-sum",
  title: "Two Sum",
  summary: "Find the pair that adds up.",
  difficulty: "Easy",
  topics: ["Arrays"],
  examples: [{ input: "[2,7,11,15]\n2", output: "[0,1]" }],
  constraints: "1 <= nums.length <= 10^4",
  starter_code: { javascript: "function solve() {}", python: "def solve():\n    pass\n" },
};

const PROGRESS_RECORD = {
  problem_id: 2,
  slug: "two-sum",
  title: "Two Sum",
  difficulty: "Easy",
  topics: ["Arrays"],
  status: "attempted",
  attempts_count: 1,
  best_runtime_ms: null,
  best_memory_mb: null,
  last_attempted_at: "2026-02-10T09:00:00Z",
  solved_at: null,
  created_at: "2026-02-09T09:00:00Z",
  updated_at: "2026-02-10T09:00:00Z",
};

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

async function renderWorkspace() {
  const view = render(
    <MemoryRouter initialEntries={["/problems/two-sum"]}>
      <Routes>
        <Route element={<WorkspacePage />} path="/problems/:slug" />
      </Routes>
    </MemoryRouter>,
  );
  // The problem loads asynchronously and the starter code is applied by an
  // effect after that render. Wait for the editor to hold the starter code
  // before a test clears or types, otherwise the interaction can race that
  // initial write and leave the editor holding the starter code plus the
  // typed text (or an empty editor the test never cleared).
  await screen.findByDisplayValue("function solve() {}");
  return view;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SubmissionStatusPill", () => {
  it("labels a stored record as queued", () => {
    renderInRouter(<SubmissionStatusPill status="queued" />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
  });

  it("describes a judged status in terms of what a judge reported", () => {
    renderInRouter(<SubmissionStatusPill status="accepted" />);
    expect(screen.getByText("Accepted")).toBeInTheDocument();
  });

  it("falls back to Queued for an unknown status instead of rendering blank", () => {
    renderInRouter(<SubmissionStatusPill status="invented_by_a_future_version" />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
  });
});

describe("SubmissionHistory", () => {
  it("shows a loading state before the history arrives", () => {
    submissionService.list.mockReturnValue(new Promise(() => {}));
    renderInRouter(<SubmissionHistory />);
    expect(screen.getByText(/loading your submission history/i)).toBeInTheDocument();
  });

  it("lists the learner's own verdicts with a count and a judged note", async () => {
    submissionService.list.mockResolvedValue(
      page(
        [
          judged(),
          submission({ id: 30, language: "javascript", problem_title: "Binary Search", status: "wrong_answer", test_cases_passed: 0, test_cases_total: 5 }),
        ],
        { total: 2 },
      ),
    );
    renderInRouter(<SubmissionHistory />);

    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    expect(screen.getByText("Binary Search")).toBeInTheDocument();
    expect(screen.getByText("2 submitted")).toBeInTheDocument();
    expect(screen.getByText(/hidden ones included/i)).toBeInTheDocument();
    // The verdict and its pass count are what the learner came back for.
    expect(screen.getByText("7 of 7 test cases passed")).toBeInTheDocument();
    expect(screen.getByText("0 of 5 test cases passed")).toBeInTheDocument();
  });

  it("opens a submission when its row is selected", async () => {
    submissionService.list.mockResolvedValue(page([submission()]));
    const onSelect = vi.fn();
    renderInRouter(<SubmissionHistory onSelect={onSelect} />);

    await userEvent.click(await screen.findByRole("button", { name: /two sum/i }));

    expect(onSelect).toHaveBeenCalledWith(31);
  });

  it("marks the selected row for the reader", async () => {
    submissionService.list.mockResolvedValue(page([submission()]));
    renderInRouter(<SubmissionHistory onSelect={() => {}} selectedId={31} />);

    expect(await screen.findByRole("button", { name: /two sum/i })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("shows an empty state before anything has been recorded", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<SubmissionHistory />);

    expect(await screen.findByText(/no submissions yet/i)).toBeInTheDocument();
  });

  it("offers a way out of a language filter that matched nothing", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<SubmissionHistory />);

    await userEvent.click(await screen.findByRole("button", { name: /python/i }));

    expect(await screen.findByText(/no submissions match/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /clear the filters/i }));
    await waitFor(() =>
      expect(submissionService.list).toHaveBeenLastCalledWith({
        language: undefined,
        status: undefined,
        page: 1,
        page_size: 20,
      }),
    );
  });

  it("passes the language filter to the API and returns to the first page", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<SubmissionHistory />);

    await userEvent.click(await screen.findByRole("button", { name: /^javascript$/i }));

    await waitFor(() =>
      expect(submissionService.list).toHaveBeenLastCalledWith({
        language: "javascript",
        status: undefined,
        page: 1,
        page_size: 20,
      }),
    );
  });

  it("passes a verdict filter to the API and returns to the first page", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<SubmissionHistory />);

    await userEvent.click(await screen.findByRole("button", { name: /^wrong answer$/i }));

    await waitFor(() =>
      expect(submissionService.list).toHaveBeenLastCalledWith({
        language: undefined,
        status: "wrong_answer",
        page: 1,
        page_size: 20,
      }),
    );
  });

  it("offers every verdict as a filter, because every verdict is reachable", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<SubmissionHistory />);

    await screen.findByText(/no submissions yet/i);
    for (const label of ["Queued", "Accepted", "Wrong Answer", "Runtime Error", "Compilation Error"]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${label}$`, "i") })).toBeInTheDocument();
    }
  });

  it("surfaces a load failure with a retry affordance", async () => {
    submissionService.list.mockRejectedValue(new Error("Submissions are unavailable."));
    renderInRouter(<SubmissionHistory />);

    expect(await screen.findByText(/submissions are unavailable/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(submissionService.list.mock.calls.length).toBeGreaterThan(1));
  });

  it("explains an expired session instead of a generic error", async () => {
    const unauthorized = new Error("Could not validate credentials.");
    unauthorized.status = 401;
    submissionService.list.mockRejectedValue(unauthorized);
    renderInRouter(<SubmissionHistory />);

    expect(
      await screen.findByText(/sign in again to load your submissions/i),
    ).toBeInTheDocument();
  });

  it("pages through a longer history", async () => {
    submissionService.list.mockResolvedValue(page([submission()], { total: 40, total_pages: 2 }));
    renderInRouter(<SubmissionHistory pageSize={20} />);

    await userEvent.click(await screen.findByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(submissionService.list).toHaveBeenLastCalledWith({
        language: undefined,
        status: undefined,
        page: 2,
        page_size: 20,
      }),
    );
  });
});

describe("SubmissionDetail", () => {
  it("asks for a selection when no submission is open", () => {
    renderInRouter(<SubmissionDetail submissionId={null} />);
    expect(screen.getByText(/no submission selected/i)).toBeInTheDocument();
  });

  it("shows a loading state while the record is read", () => {
    submissionService.detail.mockReturnValue(new Promise(() => {}));
    renderInRouter(<SubmissionDetail submissionId={31} />);
    expect(screen.getByText(/loading this submission/i)).toBeInTheDocument();
  });

  it("shows the source and says a never-judged row was never judged", async () => {
    submissionService.detail.mockResolvedValue(submission({ source_code: "MARKER = 'find me'" }));
    renderInRouter(<SubmissionDetail submissionId={31} />);

    expect(await screen.findByText("MARKER = 'find me'")).toBeInTheDocument();
    expect(screen.getByText("Not judged")).toBeInTheDocument();
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText(/stored, never judged/i)).toBeInTheDocument();
  });

  it("shows the judge's verdict, pass count, runtime, and memory", async () => {
    submissionService.detail.mockResolvedValue(
      judged({ source_code: "x = 1" }),
    );
    renderInRouter(<SubmissionDetail submissionId={31} />);

    await screen.findByText("x = 1");
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("Passed every test case")).toBeInTheDocument();
    expect(screen.getByText("7 of 7 test cases passed")).toBeInTheDocument();
    expect(screen.getByText("412 ms")).toBeInTheDocument();
    expect(screen.getByText("18 MB")).toBeInTheDocument();
  });

  it("shows what the judge reported went wrong on a failing submission", async () => {
    submissionService.detail.mockResolvedValue(
      judged({
        status: "time_limit_exceeded",
        test_cases_passed: 0,
        test_cases_total: 7,
        runtime_ms: 2000,
        memory_mb: null,
        error_message: "The program ran longer than the time limit.",
      }),
    );
    renderInRouter(<SubmissionDetail submissionId={31} />);

    expect(
      await screen.findByText("The program ran longer than the time limit."),
    ).toBeInTheDocument();
    expect(screen.getByText("Time Limit Exceeded")).toBeInTheDocument();
    expect(screen.getByText("0 of 7 test cases passed")).toBeInTheDocument();
  });

  it("shows a zero-pass count, which is a real result rather than a missing one", async () => {
    submissionService.detail.mockResolvedValue(
      judged({ status: "wrong_answer", test_cases_passed: 0, test_cases_total: 7 }),
    );
    renderInRouter(<SubmissionDetail submissionId={31} />);

    // "0 of 7" tells the learner the program ran and was wrong everywhere. It
    // must not be suppressed the way an absent measurement is.
    expect(await screen.findByText("0 of 7 test cases passed")).toBeInTheDocument();
  });

  it("omits a measurement the platform could not take instead of showing zero", async () => {
    // Peak memory is not observable on Windows, so the API reports null. A "0
    // MB" there would read as "used no memory", which is a different claim.
    submissionService.detail.mockResolvedValue(judged({ memory_mb: null }));
    renderInRouter(<SubmissionDetail submissionId={31} />);

    await screen.findByText("7 of 7 test cases passed");
    expect(screen.queryByText(/MB$/)).not.toBeInTheDocument();
    expect(screen.queryByText("0 ms")).not.toBeInTheDocument();
  });

  it("never renders a hidden test case, because the API stores none", async () => {
    submissionService.detail.mockResolvedValue(judged());
    const { container } = renderInRouter(<SubmissionDetail submissionId={31} />);

    await screen.findByText("7 of 7 test cases passed");
    // The graded record carries counts, not per-case data, so there is nothing
    // for the hidden suite to leak through. Asserted so a future change that
    // adds a cases array to the row has to confront this.
    expect(container.textContent).not.toMatch(/expected_output|case_input|is_hidden/);
  });

  it("reports a 404 without claiming to know whose record it was", async () => {
    const notFound = new Error("Submission not found.");
    notFound.status = 404;
    submissionService.detail.mockRejectedValue(notFound);
    renderInRouter(<SubmissionDetail submissionId={999} />);

    expect(await screen.findByText(/not in your history/i)).toBeInTheDocument();
    expect(screen.getByText(/never have been yours to open/i)).toBeInTheDocument();
  });

  it("explains an expired session", async () => {
    const unauthorized = new Error("Could not validate credentials.");
    unauthorized.status = 401;
    submissionService.detail.mockRejectedValue(unauthorized);
    renderInRouter(<SubmissionDetail submissionId={31} />);

    expect(await screen.findByText(/sign in again to open this submission/i)).toBeInTheDocument();
  });

  it("surfaces any other failure with a retry affordance", async () => {
    submissionService.detail.mockRejectedValue(new Error("Submissions are unavailable."));
    renderInRouter(<SubmissionDetail submissionId={31} />);

    expect(await screen.findByText(/submissions are unavailable/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(submissionService.detail.mock.calls.length).toBeGreaterThan(1));
  });

  it("links back to the workspace the attempt came from", async () => {
    submissionService.detail.mockResolvedValue(submission());
    renderInRouter(<SubmissionDetail submissionId={31} />);

    expect(await screen.findByRole("link", { name: /open the workspace/i })).toHaveAttribute(
      "href",
      "/problems/two-sum",
    );
  });
});

describe("ProblemSubmissionPanel", () => {
  const empty = {
    data: page([]),
    error: "",
    errorStatus: null,
    loading: false,
    reload: vi.fn(),
    saving: false,
    actionError: "",
    created: null,
  };

  it("invites a first submission when the problem has none", () => {
    renderInRouter(<ProblemSubmissionPanel {...empty} />);
    expect(screen.getByText(/nothing submitted for this problem/i)).toBeInTheDocument();
  });

  it("counts the attempts submitted for this problem", () => {
    renderInRouter(<ProblemSubmissionPanel {...empty} data={page([judged()], { total: 1 })} />);
    expect(screen.getByText("1 attempt submitted")).toBeInTheDocument();
  });

  it("confirms a submission with its id, language, and the judge's verdict", () => {
    renderInRouter(<ProblemSubmissionPanel {...empty} created={judged()} />);

    expect(screen.getByText(/submission #31 in python/i)).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
  });

  it("reports the verdict and its measurements after a submit", () => {
    renderInRouter(<ProblemSubmissionPanel {...empty} created={judged()} />);

    expect(screen.getByText("Passed every test case")).toBeInTheDocument();
    expect(screen.getByText("7 of 7 test cases passed")).toBeInTheDocument();
    expect(screen.getByText("412 ms")).toBeInTheDocument();
    expect(screen.getByText("18 MB")).toBeInTheDocument();
  });

  it("surfaces the judge's explanation of a failure", () => {
    renderInRouter(
      <ProblemSubmissionPanel
        {...empty}
        created={judged({
          status: "compilation_error",
          test_cases_passed: 0,
          error_message: "The source could not be compiled.",
        })}
      />,
    );

    expect(screen.getByText("Compilation Error")).toBeInTheDocument();
    expect(screen.getByText("The source could not be compiled.")).toBeInTheDocument();
  });

  it("claims no verdict for a submission the judge never reached", () => {
    renderInRouter(<ProblemSubmissionPanel {...empty} created={submission()} />);

    expect(screen.getByText("Queued")).toBeInTheDocument();
    // A stored-but-unjudged row has nothing to report, so no facts are shown.
    expect(screen.queryByText(/test cases passed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^412 ms$/)).not.toBeInTheDocument();
  });

  it("reports a failed write without claiming anything was submitted", () => {
    renderInRouter(
      <ProblemSubmissionPanel {...empty} actionError="source_code must contain the learner's code." />,
    );

    expect(screen.getByText(/must contain the learner's code/i)).toBeInTheDocument();
    expect(screen.queryByText(/submission #/i)).not.toBeInTheDocument();
  });

  it("shows the in-flight state while the judge is running", () => {
    renderInRouter(<ProblemSubmissionPanel {...empty} saving />);
    expect(screen.getByText(/running the judge on your submission/i)).toBeInTheDocument();
  });

  it("shows a load failure with a retry affordance", async () => {
    const reload = vi.fn();
    renderInRouter(<ProblemSubmissionPanel {...empty} error="Submissions are unavailable." reload={reload} />);

    expect(screen.getByText(/submissions are unavailable/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("states that submitting is graded, including on the hidden cases", () => {
    const { container } = renderInRouter(<ProblemSubmissionPanel {...empty} />);
    expect(container.querySelector(".submission-disclaimer")).toHaveTextContent(
      /hidden ones included/i,
    );
  });
});

describe("useSubmissionList", () => {
  function ListProbe({ params }) {
    const { data, error, loading } = useSubmissionList(params);
    if (loading) return <p>loading</p>;
    if (error) return <p>error: {error}</p>;
    return <p>{data.total} submissions</p>;
  }

  it("requests the first page with the default page size", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<ListProbe />);

    expect(await screen.findByText("0 submissions")).toBeInTheDocument();
    expect(submissionService.list).toHaveBeenCalledWith({
      problem_id: undefined,
      language: undefined,
      status: undefined,
      page: 1,
      page_size: 20,
    });
  });

  it("reports a failed request as an error", async () => {
    submissionService.list.mockRejectedValue(new Error("Submissions are unavailable."));
    renderInRouter(<ListProbe />);

    expect(await screen.findByText(/error: submissions are unavailable/i)).toBeInTheDocument();
  });

  it("makes no request when the learner is not signed in", async () => {
    function SignedOutProbe() {
      const { data } = useSubmissionList({}, { enabled: false });
      return <p>{data ? "loaded" : "not requested"}</p>;
    }
    renderInRouter(<SignedOutProbe />);

    expect(await screen.findByText("not requested")).toBeInTheDocument();
    expect(submissionService.list).not.toHaveBeenCalled();
  });
});

describe("useProblemSubmissions", () => {
  function RecorderProbe() {
    const { data, saving, actionError, created, create } = useProblemSubmissions(2);
    return (
      <div>
        <span>{saving ? "saving" : "idle"}</span>
        <span>{actionError || "no error"}</span>
        <span>{created ? `created ${created.id}` : "nothing created"}</span>
        <span>{(data?.items || []).length} listed</span>
        <button onClick={() => create({ language: "python", sourceCode: "x = 1" })} type="button">
          Save record
        </button>
      </div>
    );
  }

  it("stores the source and then refetches, so the panel matches the API", async () => {
    submissionService.forProblem.mockResolvedValue(page([]));
    submissionService.create.mockResolvedValue(submission());
    renderInRouter(<RecorderProbe />);

    await userEvent.click(await screen.findByRole("button", { name: /save record/i }));

    await waitFor(() =>
      expect(submissionService.create).toHaveBeenCalledWith({
        problemId: 2,
        language: "python",
        sourceCode: "x = 1",
      }),
    );
    expect(await screen.findByText("created 31")).toBeInTheDocument();
    await waitFor(() => expect(submissionService.forProblem).toHaveBeenCalledTimes(2));
  });

  it("surfaces a rejected write and reports nothing as saved", async () => {
    submissionService.forProblem.mockResolvedValue(page([]));
    submissionService.create.mockRejectedValue(new Error("The API request timed out."));
    renderInRouter(<RecorderProbe />);

    await userEvent.click(await screen.findByRole("button", { name: /save record/i }));

    expect(await screen.findByText("The API request timed out.")).toBeInTheDocument();
    expect(screen.getByText("nothing created")).toBeInTheDocument();
  });

  it("reads only the newest attempts for the problem", async () => {
    submissionService.forProblem.mockResolvedValue(page([]));
    renderInRouter(<RecorderProbe />);

    await waitFor(() =>
      expect(submissionService.forProblem).toHaveBeenCalledWith(2, { page: 1, page_size: 5 }),
    );
  });
});

describe("what the judged UI claims", () => {
  it("shows a verdict filter, because submissions are graded now", async () => {
    submissionService.list.mockResolvedValue(page([]));
    renderInRouter(<SubmissionHistory />);

    await screen.findByText(/no submissions yet/i);
    expect(screen.getByRole("button", { name: /^accepted$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^wrong answer$/i })).toBeInTheDocument();
  });

  it("imposes no runtime on a row the judge could not measure", async () => {
    submissionService.list.mockResolvedValue(page([submission({ status: "queued" })]));
    const { container } = renderInRouter(<SubmissionHistory />);

    await screen.findByText("Two Sum");
    // Scoped to the rows: the panel's own note is *supposed* to talk about what
    // the judge does. A row must not claim a measurement that was never taken.
    const rows = container.querySelector(".submission-list").textContent.toLowerCase();
    for (const forbidden of ["runtime", "memory", "ms", "mb"]) {
      expect(rows).not.toContain(forbidden);
    }
  });

  it("does show the pass count on a row the judge graded", async () => {
    submissionService.list.mockResolvedValue(page([judged()]));
    const { container } = renderInRouter(<SubmissionHistory />);

    await screen.findByText("Two Sum");
    expect(container.querySelector(".submission-list")).toHaveTextContent(
      "7 of 7 test cases passed",
    );
  });

  it("keeps a history row free of the source code", async () => {
    submissionService.list.mockResolvedValue(page([submission({ source_code: "SECRET_SOURCE" })]));
    renderInRouter(<SubmissionHistory />);

    await screen.findByText("Two Sum");
    expect(screen.queryByText(/SECRET_SOURCE/)).not.toBeInTheDocument();
  });

  it("labels a queued row without an icon-only ambiguous glyph", async () => {
    submissionService.list.mockResolvedValue(page([submission()]));
    renderInRouter(<SubmissionHistory />);

    const row = (await screen.findByText("Two Sum")).closest("li");
    expect(within(row).getByText("Queued")).toBeInTheDocument();
  });
});

describe("the workspace submit area", () => {
  beforeEach(() => {
    useAuth.mockReturnValue({ isAuthenticated: true });
    problemApi.get.mockResolvedValue(PAGE_PROBLEM);
    progressService.problem.mockResolvedValue(PROGRESS_RECORD);
    submissionService.forProblem.mockResolvedValue(page([]));
    submissionService.create.mockResolvedValue(judged());
    judgeService.languages.mockResolvedValue({
      items: [
        { id: "javascript", label: "JavaScript" },
        { id: "python", label: "Python" },
      ],
      execution_enabled: true,
    });
    judgeService.run.mockResolvedValue({ verdict: null, cases: [], ad_hoc: {} });
  });

  it("offers a real Run affordance, and reports nothing before anything has run", async () => {
    await renderWorkspace();

    const run = await screen.findByRole("button", { name: /run test cases/i });
    expect(run).toBeEnabled();
    // The page may run code, but until the learner asks it to, it has no
    // measurement to report and must not imply one.
    expect(screen.queryByText(/\d+\s*ms/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+\s*of\s*\d+\s*test cases passed/i)).not.toBeInTheDocument();
  });

  it("cannot run an editor that holds no code", async () => {
    await renderWorkspace();

    const editor = await screen.findByLabelText(/code editor/i);
    await userEvent.clear(editor);

    expect(screen.getByRole("button", { name: /run test cases/i })).toBeDisabled();
  });

  it("cannot run without a session", async () => {
    useAuth.mockReturnValue({ isAuthenticated: false });
    await renderWorkspace();

    expect(await screen.findByRole("button", { name: /run test cases/i })).toBeDisabled();
  });

  it("states that submitting is graded, including on the hidden cases", async () => {
    await renderWorkspace();

    expect(await screen.findAllByText(/hidden ones included/i)).not.toHaveLength(0);
  });

  it("submits the editor's code and shows the verdict the judge returned", async () => {
    await renderWorkspace();

    const editor = await screen.findByLabelText(/code editor/i);
    await userEvent.clear(editor);
    await userEvent.type(editor, "const x = 1;");
    await userEvent.click(screen.getByRole("button", { name: /submit solution/i }));

    await waitFor(() =>
      expect(submissionService.create).toHaveBeenCalledWith({
        problemId: 2,
        language: "javascript",
        sourceCode: "const x = 1;",
      }),
    );
    // The verdict is the point of submitting, so it is on screen without the
    // learner having to go and look for it.
    expect(await screen.findByText(/submission #31 in python/i)).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("7 of 7 test cases passed")).toBeInTheDocument();
  });

  it("submits in whichever language tab is selected", async () => {
    await renderWorkspace();

    await userEvent.click(await screen.findByRole("tab", { name: /python/i }));
    await userEvent.click(screen.getByRole("button", { name: /submit solution/i }));

    await waitFor(() =>
      expect(submissionService.create).toHaveBeenCalledWith(
        expect.objectContaining({ language: "python" }),
      ),
    );
  });

  it("cannot submit an editor that holds no code", async () => {
    await renderWorkspace();

    const editor = await screen.findByLabelText(/code editor/i);
    await userEvent.clear(editor);

    expect(screen.getByRole("button", { name: /submit solution/i })).toBeDisabled();
  });

  it("leaves the progress write to the API, because only an accept can solve", async () => {
    await renderWorkspace();

    await screen.findByLabelText(/code editor/i);
    await userEvent.click(screen.getByRole("button", { name: /submit solution/i }));

    // The client cannot decide whether a submission solved the problem -- only
    // the judge knows the verdict -- so it must never write progress itself.
    expect(progressService.setStatus).not.toHaveBeenCalled();
    expect(progressService.recordAttempt).not.toHaveBeenCalled();
  });

  it("refreshes the progress panel after a submit, because the API owns progress", async () => {
    await renderWorkspace();

    await userEvent.click(await screen.findByRole("button", { name: /submit solution/i }));

    await waitFor(() => expect(progressService.problem.mock.calls.length).toBeGreaterThan(1));
  });

  it("refreshes the submission list after a submit, so the panel matches the API", async () => {
    await renderWorkspace();

    await userEvent.click(await screen.findByRole("button", { name: /submit solution/i }));

    await waitFor(() =>
      expect(submissionService.forProblem.mock.calls.length).toBeGreaterThan(1),
    );
  });

  it("reports a failed submit without claiming a verdict was given", async () => {
    submissionService.create.mockRejectedValue(new Error("The API request timed out."));
    await renderWorkspace();

    await userEvent.click(await screen.findByRole("button", { name: /submit solution/i }));

    expect(await screen.findByText(/the api request timed out/i)).toBeInTheDocument();
    expect(screen.queryByText(/submission #/i)).not.toBeInTheDocument();
  });
});
