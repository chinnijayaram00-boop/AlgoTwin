import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PersonalizationPage from "../../pages/PersonalizationPage";
import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";
import MentorPanel from "./MentorPanel";
import { degradedMessage, MENTOR_FOCUS_OPTIONS } from "./personalizationFormat";
import { personalizationService } from "./personalizationService";
import { useMentor } from "./useMentor";
import { usePersonalization } from "./usePersonalization";

// Only the transport is faked. The service, hooks, formatters, and page under
// test stay real, so these tests exercise the actual request the page builds and
// the real fallback rendering.
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

const PROFILE = {
  overview: {
    total_problems: 50,
    solved: 3,
    attempted: 2,
    not_started: 45,
    completion_percentage: 6,
    current_streak_days: 2,
    total_submissions: 9,
    judged_submissions: 5,
    accepted_submissions: 3,
    acceptance_rate: 60,
    problems_submitted: 2,
    interviews_completed: 1,
    questions_answered: 3,
    questions_accepted: 2,
    average_interview_score: 75,
  },
  strengths: [
    {
      code: "solved_volume",
      title: "Problem-solving momentum",
      detail: "You have solved 3 of 50 published problems.",
      evidence: "3/50 solved (6%)",
    },
  ],
  weaknesses: [
    {
      code: "unfinished_attempts",
      title: "Unfinished attempts",
      detail: "2 problem(s) are started but not yet solved.",
      evidence: "2 attempted, unsolved",
    },
  ],
  recommendations: [
    {
      problem_id: 12,
      slug: "single-number",
      title: "Single Number",
      difficulty: "Easy",
      topics: ["Arrays"],
      primary_topic: "Arrays",
      status: "not_started",
      reason_code: "continue_stage",
      reason: "Continue your Arrays progression.",
      priority: 5,
    },
    {
      problem_id: 13,
      slug: "valid-parentheses",
      title: "Valid Parentheses",
      difficulty: "Medium",
      topics: ["Strings"],
      primary_topic: "Strings",
      status: "not_started",
      reason_code: "continue_stage",
      reason: "Continue your Arrays progression.",
      priority: 0,
    },
  ],
  focus_areas: [
    { topic: "Hash Maps", solved: 0, attempted: 1, total: 5, completion_percentage: 0 },
    { topic: "Arrays", solved: 3, attempted: 2, total: 9, completion_percentage: 33.3 },
  ],
  as_of: "2026-03-15",
};

const GUIDANCE = {
  focus: "overview",
  content: "## Where you stand\n\nYou have solved **3 of 50** published problems.",
  provider: "deterministic",
  model: "profile-rules",
  grounding: { solved: 3, total_problems: 50, focus: "overview" },
  fallback: true,
  degraded_reason: "provider_not_configured",
  is_demo_output: false,
  generated_at: "2026-03-15T10:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  getStoredToken.mockReturnValue("token-123");
});

describe("personalizationService", () => {
  it("reads the profile carrying the session token, without asking whose it is", async () => {
    apiClient.get.mockResolvedValue(PROFILE);

    const result = await personalizationService.profile();

    expect(result).toBe(PROFILE);
    expect(apiClient.get).toHaveBeenCalledWith("/personalization/profile", { token: "token-123" });
    const [path, options] = apiClient.get.mock.calls[0];
    expect(path).toBe("/personalization/profile");
    expect(options).not.toHaveProperty("userId");
    expect(options).not.toHaveProperty("user_id");
  });

  it("sends no token when the session is empty", async () => {
    getStoredToken.mockReturnValue("");
    apiClient.get.mockResolvedValue(PROFILE);

    await personalizationService.profile();

    expect(apiClient.get).toHaveBeenCalledWith("/personalization/profile", {});
  });

  it("asks the mentor with a focus label and a model-scale timeout", async () => {
    apiClient.post.mockResolvedValue(GUIDANCE);

    await personalizationService.mentor("strengths");

    expect(apiClient.post).toHaveBeenCalledWith(
      "/personalization/mentor",
      { focus: "strengths" },
      { token: "token-123", timeoutMs: expect.any(Number) },
    );
    const [, body, options] = apiClient.post.mock.calls[0];
    expect(body).toEqual({ focus: "strengths" });
    expect(options).not.toHaveProperty("userId");
  });

  it("omits the focus when none is asked for", async () => {
    apiClient.post.mockResolvedValue(GUIDANCE);

    await personalizationService.mentor();

    expect(apiClient.post).toHaveBeenCalledWith(
      "/personalization/mentor",
      {},
      expect.objectContaining({ token: "token-123" }),
    );
  });
});

describe("usePersonalization", () => {
  function ProfileProbe({ enabled = true }) {
    const { data, loading, error } = usePersonalization({ enabled });
    if (loading) return <p>loading</p>;
    if (error) return <p>error: {error}</p>;
    return <p>{data ? `${data.overview.solved}/${data.overview.total_problems}` : "no data"}</p>;
  }

  it("resolves the learner's profile", async () => {
    apiClient.get.mockResolvedValue(PROFILE);
    render(<ProfileProbe />);

    expect(await screen.findByText("3/50")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("reports a failed request as an error", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request failed (500)."));
    render(<ProfileProbe />);

    expect(await screen.findByText(/error: the api request failed/i)).toBeInTheDocument();
  });

  it("makes no request while the session is still restoring", async () => {
    render(<ProfileProbe enabled={false} />);

    expect(await screen.findByText("no data")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

describe("useMentor", () => {
  function MentorProbe() {
    const { status, guidance, error, generate } = useMentor();
    return (
      <div>
        <button onClick={() => generate("overview")} type="button">
          ask
        </button>
        <p>status: {status}</p>
        <p>guidance: {guidance ? guidance.provider : "none"}</p>
        {error ? <p>error: {error}</p> : null}
      </div>
    );
  }

  it("keeps idle until asked, then resolves the guidance", async () => {
    apiClient.post.mockResolvedValue(GUIDANCE);
    render(<MentorProbe />);

    expect(screen.getByText("guidance: none")).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "ask" }));

    expect(await screen.findByText("guidance: deterministic")).toBeInTheDocument();
    expect(screen.getByText("status: success")).toBeInTheDocument();
  });

  it("reports a failed generation without throwing", async () => {
    apiClient.post.mockRejectedValue(new Error("The API request timed out."));
    render(<MentorProbe />);

    await userEvent.click(screen.getByRole("button", { name: "ask" }));

    expect(await screen.findByText(/error: the api request timed out/i)).toBeInTheDocument();
  });
});

describe("personalizationFormat", () => {
  it("explains every degraded reason the API can return", () => {
    expect(degradedMessage("provider_not_configured")).toMatch(/no ai provider is configured/i);
    expect(degradedMessage("rate_limited")).toMatch(/request limit/i);
    expect(degradedMessage("provider_timeout")).toMatch(/took too long/i);
    expect(degradedMessage("provider_error")).toMatch(/could not answer/i);
  });

  it("returns nothing for a successful or unknown reason rather than inventing one", () => {
    expect(degradedMessage(null)).toBe("");
    expect(degradedMessage("something-new")).toBe("");
  });

  it("offers a closed set of focus options including the API default", () => {
    expect(MENTOR_FOCUS_OPTIONS.map((option) => option.value)).toContain("overview");
    expect(MENTOR_FOCUS_OPTIONS).toHaveLength(4);
  });
});

function renderPage() {
  return render(
    <MemoryRouter>
      <PersonalizationPage />
    </MemoryRouter>,
  );
}

describe("PersonalizationPage", () => {
  it("shows a loading state before the profile arrives", () => {
    apiClient.get.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText(/building your profile/i)).toBeInTheDocument();
  });

  it("renders strengths, weaknesses, recommendations, and focus areas", async () => {
    apiClient.get.mockResolvedValue(PROFILE);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Strengths" })).toBeInTheDocument();
    expect(screen.getByText("Problem-solving momentum")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Worth your attention" })).toBeInTheDocument();
    expect(screen.getByText("Unfinished attempts")).toBeInTheDocument();

    expect(screen.getByText("Single Number")).toBeInTheDocument();
    expect(screen.getAllByText(/continue your arrays progression/i)).toHaveLength(2);
    expect(screen.getByText("Hash Maps")).toBeInTheDocument();

    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("explains an expired session instead of a generic error", async () => {
    const failure = new Error("Not authenticated");
    failure.status = 401;
    apiClient.get.mockRejectedValue(failure);
    renderPage();

    expect(await screen.findByText(/sign in again to load your profile/i)).toBeInTheDocument();
    expect(screen.queryByText(/something needs attention/i)).not.toBeInTheDocument();
  });

  it("surfaces a load failure with a retry affordance", async () => {
    apiClient.get.mockRejectedValue(new Error("The API request timed out."));
    renderPage();

    expect(await screen.findByText(/the api request timed out/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(apiClient.get.mock.calls.length).toBeGreaterThan(1));
  });
});

describe("MentorPanel", () => {
  it("does not ask on mount and explains why", () => {
    render(
      <MemoryRouter>
        <MentorPanel />
      </MemoryRouter>,
    );

    expect(screen.getByText(/nothing is generated until you do/i)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("asks the coach and renders the fallback text with its reason", async () => {
    apiClient.post.mockResolvedValue(GUIDANCE);
    render(
      <MemoryRouter>
        <MentorPanel />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole("button", { name: /ask the coach/i }));

    expect(await screen.findByText(/you have solved/i)).toBeInTheDocument();
    expect(apiClient.post).toHaveBeenCalledWith(
      "/personalization/mentor",
      { focus: "overview" },
      expect.objectContaining({ token: "token-123" }),
    );
    // The fallback is labelled, so rules-based text is never mistaken for a model's.
    expect(screen.getByText(/written from your profile by rules/i)).toBeInTheDocument();
    expect(screen.getByText(/focus: overview/i)).toBeInTheDocument();
  });

  it("labels demo output so fixed text is never attributed to a model", async () => {
    apiClient.post.mockResolvedValue({
      ...GUIDANCE,
      provider: "fake",
      model: "fake-deterministic",
      fallback: false,
      degraded_reason: null,
      is_demo_output: true,
      content: "## Your next step\n\nFixed text.",
    });
    render(
      <MemoryRouter>
        <MentorPanel />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole("button", { name: /ask the coach/i }));

    expect(await screen.findByText(/demo output/i)).toBeInTheDocument();
    expect(screen.getByText(/not from a model/i)).toBeInTheDocument();
  });
});
