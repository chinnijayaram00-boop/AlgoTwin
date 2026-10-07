import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InterviewsPage from "../../pages/InterviewsPage";
import { apiClient } from "../../services/apiClient";
import { problemApi } from "../../services/platformService";
import { getStoredToken } from "../auth/authStorage";
import { interviewService } from "./interviewService";

// Only the transport is faked. The service and the hooks stay real, so these
// tests exercise the actual paths, payloads, and headers the feature builds.
vi.mock("../../services/apiClient", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));
vi.mock("../auth/authStorage", () => ({ getStoredToken: vi.fn() }));
vi.mock("../../services/platformService", () => ({
  problemApi: { get: vi.fn() },
}));
vi.mock("../problems/CodeEditor", () => ({
  default: ({ value, onChange }) => (
    <textarea aria-label="Code editor" onChange={(e) => onChange(e.target.value)} value={value || ""} />
  ),
}));

const SESSION_CREATED = {
  id: 41,
  status: "created",
  role: "Software Engineer",
  level: null,
  difficulty: "Easy",
  topic: "Arrays",
  question_count: 2,
  duration_seconds: 1800,
  current_index: 0,
  score: null,
  created_at: "2026-10-07T10:00:00Z",
  started_at: null,
  expires_at: null,
  completed_at: null,
  remaining_seconds: null,
  timed_out: false,
  questions: [
    {
      position: 0,
      problem_id: 1,
      slug: "two-sum",
      title: "Two Sum",
      summary: "Find the pair that adds up.",
      difficulty: "Easy",
      topics: ["Arrays", "Two Pointers"],
      primary_topic: "Arrays",
      status: "pending",
      verdict: null,
      submission_id: null,
      accepted: false,
      attempts: 0,
      runtime_ms: null,
      answered_at: null,
    },
    {
      position: 1,
      problem_id: 7,
      slug: "reverse-linked-list",
      title: "Reverse Linked List",
      summary: "Reverse a singly linked list.",
      difficulty: "Medium",
      topics: ["Linked Lists"],
      primary_topic: "Linked Lists",
      status: "pending",
      verdict: null,
      submission_id: null,
      accepted: false,
      attempts: 0,
      runtime_ms: null,
      answered_at: null,
    },
  ],
};

const SESSION_RUNNING = {
  ...SESSION_CREATED,
  status: "in_progress",
  started_at: "2026-10-07T10:05:00Z",
  expires_at: "2026-10-07T10:35:00Z",
  remaining_seconds: 600,
};

const SESSION_RUNNING_AFTER_SUBMIT = {
  ...SESSION_RUNNING,
  current_index: 1,
  questions: [
    { ...SESSION_CREATED.questions[0], status: "submitted", verdict: "accepted", accepted: true, attempts: 1, runtime_ms: 12 },
    SESSION_CREATED.questions[1],
  ],
};

const SESSION_COMPLETED = {
  ...SESSION_RUNNING,
  status: "completed",
  current_index: 2,
  score: 50,
  completed_at: "2026-10-07T10:17:00Z",
  timed_out: false,
  questions: [
    { ...SESSION_RUNNING_AFTER_SUBMIT.questions[0] },
    { ...SESSION_CREATED.questions[1], status: "submitted", verdict: "wrong_answer", accepted: false, attempts: 2, runtime_ms: 9, answered_at: "2026-10-07T10:16:00Z" },
  ],
};

const SESSION_ABANDONED = { ...SESSION_CREATED, status: "abandoned", completed_at: "2026-10-07T10:03:00Z" };

const PROBLEM = {
  id: 1,
  slug: "two-sum",
  title: "Two Sum",
  summary: "Find the pair that adds up.",
  difficulty: "Easy",
  topics: ["Arrays", "Two Pointers"],
  examples: [{ input: "[2,7,11,15]\n2", output: "[0,1]" }],
  constraints: "1 <= nums.length <= 10^4",
  starter_code: { python: "def solve():\n    pass\n", javascript: "function solve() {}" },
  supported_languages: ["python", "javascript"],
};

const REPORT = {
  id: 41,
  role: "Software Engineer",
  level: null,
  difficulty: "Easy",
  topic: "Arrays",
  status: "completed",
  question_count: 2,
  duration_seconds: 1800,
  score: 50,
  timed_out: false,
  started_at: "2026-10-07T10:05:00Z",
  completed_at: "2026-10-07T10:17:00Z",
  duration_used_seconds: 720,
  questions_answered: 2,
  questions_accepted: 1,
  questions: [
    { ...SESSION_RUNNING_AFTER_SUBMIT.questions[0], test_cases_passed: 3, test_cases_total: 3, memory_mb: 4 },
    { ...SESSION_COMPLETED.questions[1], test_cases_passed: 1, test_cases_total: 3, memory_mb: null },
  ],
};

const HISTORY = {
  items: [
    {
      id: 42,
      status: "completed",
      role: "Senior Engineer",
      level: "senior",
      difficulty: null,
      question_count: 1,
      score: 100,
      timed_out: false,
      created_at: "2026-10-06T09:00:00Z",
      completed_at: "2026-10-06T09:25:00Z",
    },
    {
      id: 40,
      status: "abandoned",
      role: "Software Engineer",
      level: null,
      difficulty: null,
      question_count: 3,
      score: null,
      timed_out: false,
      created_at: "2026-10-05T18:00:00Z",
      completed_at: "2026-10-05T18:02:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

const EMPTY_HISTORY = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

function notFound(message) {
  return Object.assign(new Error(message), { status: 404 });
}

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  getStoredToken.mockReturnValue("token-123");
  apiClient.get.mockReset();
  apiClient.post.mockReset();
  problemApi.get.mockReset().mockResolvedValue(PROBLEM);
});

describe("interviewService", () => {
  it("creates a session with calibration and the session token", async () => {
    apiClient.post.mockResolvedValue(SESSION_CREATED);
    await interviewService.create({
      role: "Data Engineer",
      level: "mid",
      difficulty: "Medium",
      topic: "Graphs",
      questionCount: 2,
      durationMinutes: 45,
    });
    expect(apiClient.post).toHaveBeenCalledWith("/interviews", {
      role: "Data Engineer",
      level: "mid",
      difficulty: "Medium",
      topic: "Graphs",
      question_count: 2,
      duration_minutes: 45,
    }, { token: "token-123" });
  });

  it("treats a missing level or filter as null, never an empty string", async () => {
    apiClient.post.mockResolvedValue(SESSION_CREATED);
    await interviewService.create({ role: "Software Engineer", level: "", difficulty: "", topic: "", questionCount: 3, durationMinutes: 30 });
    const body = apiClient.post.mock.calls[0][1];
    expect(body.level).toBeNull();
    expect(body.difficulty).toBeNull();
    expect(body.topic).toBeNull();
  });

  it("reads the active session from the dedicated path", async () => {
    apiClient.get.mockResolvedValue(SESSION_RUNNING);
    await interviewService.active();
    expect(apiClient.get).toHaveBeenCalledWith("/interviews/active", { token: "token-123" });
  });

  it("lists history with the wire query names", async () => {
    apiClient.get.mockResolvedValue(HISTORY);
    await interviewService.list({ page: 2, pageSize: 5 });
    expect(apiClient.get).toHaveBeenCalledWith("/interviews?page=2&page_size=5", { token: "token-123" });
  });

  it("submits an answer to the question endpoint with the judge timeout", async () => {
    apiClient.post.mockResolvedValue(SESSION_RUNNING_AFTER_SUBMIT);
    await interviewService.submit({ interviewId: 41, position: 0, language: "python", sourceCode: "print(1)" });
    expect(apiClient.post).toHaveBeenCalledWith(
      "/interviews/41/questions/0/submit",
      { language: "python", source_code: "print(1)" },
      { token: "token-123", timeoutMs: 60000 },
    );
  });

  it("requests the report for a completed interview", async () => {
    apiClient.get.mockResolvedValue(REPORT);
    await interviewService.report(41);
    expect(apiClient.get).toHaveBeenCalledWith("/interviews/41/report", { token: "token-123" });
  });
});

describe("InterviewsPage", () => {
  it("shows the setup form and empty history when there is no active session", async () => {
    apiClient.get.mockImplementation((path) =>
      path.startsWith("/interviews?") ? Promise.resolve(EMPTY_HISTORY) : Promise.reject(notFound("No active interview.")),
    );

    renderInRouter(<InterviewsPage />);

    expect(await screen.findByRole("heading", { name: /set up an interview/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/role/i)).toHaveValue("Software Engineer");
    expect(await screen.findByText(/no interviews yet/i)).toBeInTheDocument();
  });

  it("starts a session from the form, then starts the clock into the running view", async () => {
    apiClient.get.mockImplementation((path) =>
      path.startsWith("/interviews?") ? Promise.resolve(EMPTY_HISTORY) : Promise.reject(notFound("No active interview.")),
    );
    apiClient.post.mockImplementation((path) => {
      if (path === "/interviews/41/start") return Promise.resolve(SESSION_RUNNING);
      return Promise.resolve(SESSION_CREATED);
    });

    renderInRouter(<InterviewsPage />);

    const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: /set up an interview/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /start interview/i }));

    expect(await screen.findByRole("heading", { name: /your questions are ready/i })).toBeInTheDocument();
    expect(screen.getByText("Two Sum")).toBeInTheDocument();
    expect(screen.getByText("Reverse Linked List")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /start the clock/i }));

    expect(await screen.findByRole("heading", { name: /two sum/i })).toBeInTheDocument();
    expect(screen.getByText("10:00")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /python/i })).toBeInTheDocument();
  });

  it("judges an answer and shows the verdict while advancing to the next question", async () => {
    apiClient.get.mockImplementation((path) =>
      path.startsWith("/interviews?") ? Promise.resolve(EMPTY_HISTORY) : Promise.reject(notFound("No active interview.")),
    );
    apiClient.post.mockImplementation((path) => {
      if (path === "/interviews/41/start") return Promise.resolve(SESSION_RUNNING);
      if (path === "/interviews/41/questions/0/submit") return Promise.resolve(SESSION_RUNNING_AFTER_SUBMIT);
      return Promise.resolve(SESSION_CREATED);
    });

    renderInRouter(<InterviewsPage />);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /start interview/i }));
    await user.click(await screen.findByRole("button", { name: /start the clock/i }));

    const editor = await screen.findByRole("textbox", { name: /code editor/i });
    await waitFor(() => expect(editor).toHaveValue("def solve():\n    pass\n"));
    await user.clear(editor);
    await user.type(editor, "print(1)");
    await user.click(screen.getByRole("button", { name: /submit & judge/i }));

    expect(await screen.findByText("Accepted")).toBeInTheDocument();
    expect(apiClient.post).toHaveBeenCalledWith(
      "/interviews/41/questions/0/submit",
      { language: "python", source_code: "print(1)" },
      expect.objectContaining({ token: "token-123" }),
    );
    const activeTab = await screen.findByRole("tab", { name: /reverse linked list/i });
    expect(activeTab).toHaveAttribute("aria-selected", "true");
  });

  it("finishing a session opens the report built from the report endpoint", async () => {
    apiClient.get.mockImplementation((path) => {
      if (path.startsWith("/interviews/41/report")) return Promise.resolve(REPORT);
      if (path.startsWith("/interviews?")) return Promise.resolve(EMPTY_HISTORY);
      return Promise.reject(notFound("No active interview."));
    });
    apiClient.post.mockImplementation((path) => {
      if (path === "/interviews/41/start") return Promise.resolve(SESSION_RUNNING);
      if (path === "/interviews/41/finish") return Promise.resolve(SESSION_COMPLETED);
      return Promise.resolve(SESSION_CREATED);
    });

    renderInRouter(<InterviewsPage />);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /start interview/i }));
    await user.click(await screen.findByRole("button", { name: /start the clock/i }));
    await user.click(screen.getByRole("button", { name: /finish interview/i }));

    expect(await screen.findByRole("heading", { name: /your interview report/i })).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/interviews/41/report", { token: "token-123" });
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("1 of 3 test cases passed")).toBeInTheDocument();
  });

  it("abandoning a session returns to setup and refreshes the history", async () => {
    apiClient.get.mockImplementation((path) =>
      path.startsWith("/interviews?") ? Promise.resolve(HISTORY) : Promise.reject(notFound("No active interview.")),
    );
    apiClient.post.mockImplementation((path) => {
      if (path === "/interviews/41/abandon") return Promise.resolve(SESSION_ABANDONED);
      return Promise.resolve(SESSION_CREATED);
    });

    renderInRouter(<InterviewsPage />);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /start interview/i }));
    await user.click(await screen.findByRole("button", { name: /abandon interview/i }));

    expect(await screen.findByRole("heading", { name: /set up an interview/i })).toBeInTheDocument();
    expect(await screen.findByText(/abandoned/i)).toBeInTheDocument();
  });

  it("opens a completed interview's report from the history rows", async () => {
    apiClient.get.mockImplementation((path) => {
      if (path.startsWith("/interviews?")) return Promise.resolve(HISTORY);
      if (path.startsWith("/interviews/42/report")) return Promise.resolve({ ...REPORT, id: 42, score: 100 });
      return Promise.reject(notFound("No active interview."));
    });

    renderInRouter(<InterviewsPage />);

    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: /open the report for the senior engineer/i }),
    );

    expect(await screen.findByRole("heading", { name: /your interview report/i })).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /back to history/i }));
    expect(await screen.findByRole("heading", { name: /set up an interview/i })).toBeInTheDocument();
  });
});

describe("navigation wiring", () => {
  it("exposes an Interviews entry pointing at the registered route", async () => {
    const { navigationItems } = await import("../../app/navigation");
    const item = navigationItems.find((entry) => entry.to === "/interviews");
    expect(item).toBeTruthy();
    expect(item.label).toBe("Interviews");
    expect(item.icon).toBe("interviews");
  });
});