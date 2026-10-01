import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "../../lib/env";
import { TOKEN_KEY } from "../auth/authStorage";
import { submissionService } from "./submissionService";

/**
 * These tests pin the wire contract, because a typo in a path or a renamed field
 * would otherwise only show up as an empty screen in the running app.
 *
 * `fetch` is stubbed rather than the service itself, so the URL, the query
 * string, the request body, and the Authorization header are all asserted
 * exactly as the API will receive them.
 */

const DETAIL = {
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
  source_code: "def solve():\n    return 1\n",
};

const PAGE = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

let fetchMock;

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function lastRequest() {
  const [url, options] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  return { url, options };
}

function lastBody() {
  const { options } = lastRequest();
  return options.body ? JSON.parse(options.body) : null;
}

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(TOKEN_KEY, "stored-token");
  fetchMock = vi.fn().mockResolvedValue(jsonResponse(PAGE));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("submissionService.create", () => {
  it("posts the three accepted fields to the submissions endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse(DETAIL, 201));

    await submissionService.create({ problemId: 2, language: "python", sourceCode: "x = 1" });

    const { url, options } = lastRequest();
    expect(url).toBe(`${API_BASE_URL}/submissions`);
    expect(options.method).toBe("POST");
    expect(lastBody()).toEqual({ problem_id: 2, language: "python", source_code: "x = 1" });
  });

  it("sends nothing a learner may not set, so a record can never look judged", async () => {
    await submissionService.create({ problemId: 2, language: "javascript", sourceCode: "x = 1" });

    const body = lastBody();
    expect(Object.keys(body).sort()).toEqual(["language", "problem_id", "source_code"]);
    for (const forbidden of ["user_id", "status", "runtime_ms", "test_cases_passed", "error_message"]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });

  it("waits long enough for a synchronous judgement to come back", async () => {
    // The API judges synchronously, bounded by MAX_JUDGE_WALL_CLOCK_MS (30s by
    // default) plus a grace period. The generic client default is 10s, which
    // would abort a legitimate submit that the server went on to store and grade
    // -- a timeout shown to the learner for work that really was done.
    //
    // `timeoutMs` is consumed by `apiClient` and never reaches `fetch`, so the
    // abort delay is what the value actually produces and is what to assert.
    const scheduled = [];
    const realSetTimeout = window.setTimeout;
    const spy = vi.spyOn(window, "setTimeout").mockImplementation((fn, ms, ...rest) => {
      scheduled.push(ms);
      return realSetTimeout(fn, ms, ...rest);
    });
    try {
      await submissionService.create({ problemId: 2, language: "python", sourceCode: "x = 1" });
    } finally {
      spy.mockRestore();
    }

    expect(scheduled).toContain(60_000);
    // And specifically not the 10s default, which is the failure this guards.
    expect(scheduled).not.toContain(10_000);
  });

  it("returns the graded record the judge produced", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          ...DETAIL,
          status: "wrong_answer",
          test_cases_passed: 0,
          test_cases_total: 7,
          runtime_ms: 118,
          error_message: "The program printed the wrong answer for this case.",
          judged_at: "2026-02-10T09:00:04Z",
        },
        201,
      ),
    );

    const stored = await submissionService.create({
      problemId: 2,
      language: "python",
      sourceCode: "x = 1",
    });

    // The verdict is the caller's to render, so it has to survive the round trip
    // rather than being dropped on the way out of the service.
    expect(stored.status).toBe("wrong_answer");
    expect(stored.test_cases_passed).toBe(0);
    expect(stored.test_cases_total).toBe(7);
    expect(stored.runtime_ms).toBe(118);
    expect(stored.judged_at).toBe("2026-02-10T09:00:04Z");
  });
});

describe("submissionService.list", () => {
  it("reads the account-wide history with the given filters", async () => {
    await submissionService.list({ language: "python", page: 2, page_size: 5 });

    const { url } = lastRequest();
    expect(url).toBe(`${API_BASE_URL}/submissions?language=python&page=2&page_size=5`);
  });

  it("can narrow the history to one verdict", async () => {
    await submissionService.list({ status: "accepted", page: 1, page_size: 20 });

    const { url } = lastRequest();
    expect(url).toBe(`${API_BASE_URL}/submissions?status=accepted&page=1&page_size=20`);
  });

  it("omits filters that were not set instead of sending empty values", async () => {
    await submissionService.list({ problem_id: undefined, language: "", page: 1, page_size: 20 });

    const { url } = lastRequest();
    expect(url).toBe(`${API_BASE_URL}/submissions?page=1&page_size=20`);
  });
});

describe("submissionService.detail", () => {
  it("reads one submission by id", async () => {
    fetchMock.mockResolvedValue(jsonResponse(DETAIL));

    const detail = await submissionService.detail(31);

    expect(lastRequest().url).toBe(`${API_BASE_URL}/submissions/31`);
    expect(detail.source_code).toContain("def solve");
  });

  it("reports a 404 so the UI can say the row is not in this learner's history", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Submission not found." }, 404));

    await expect(submissionService.detail(999)).rejects.toMatchObject({ status: 404 });
  });
});

describe("submissionService.forProblem", () => {
  it("reads the learner's own submissions for one problem", async () => {
    await submissionService.forProblem(2, { page: 1, page_size: 5 });

    expect(lastRequest().url).toBe(`${API_BASE_URL}/problems/2/submissions?page=1&page_size=5`);
  });
});

describe("authentication", () => {
  const calls = [
    ["create", () => submissionService.create({ problemId: 1, language: "python", sourceCode: "x" })],
    ["list", () => submissionService.list({ page: 1 })],
    ["detail", () => submissionService.detail(1)],
    ["forProblem", () => submissionService.forProblem(1, {})],
  ];

  it.each(calls)("%s attaches the stored bearer token", async (_name, call) => {
    await call();

    const { options } = lastRequest();
    expect(options.headers.Authorization).toBe("Bearer stored-token");
  });

  it("never asks for another learner, because no call takes a user id", async () => {
    await Promise.all(calls.map(([, call]) => call()));

    for (const [url, options] of fetchMock.mock.calls) {
      expect(url).not.toMatch(/user/i);
      if (options.body) {
        expect(JSON.parse(options.body)).not.toHaveProperty("user_id");
      }
    }
  });

  it("sends no Authorization header when there is no stored session", async () => {
    window.localStorage.removeItem(TOKEN_KEY);

    await submissionService.list({ page: 1 });

    expect(lastRequest().options.headers.Authorization).toBeUndefined();
  });
});
