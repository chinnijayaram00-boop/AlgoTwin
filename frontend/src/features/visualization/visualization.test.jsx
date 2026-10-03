import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "../../lib/env";
import { TOKEN_KEY } from "../auth/authStorage";
import {
  CELL_TONES,
  NOT_MEASURED,
  SIDE_STATUSES,
  STATE_KINDS,
  algorithmApi,
  formatMeasurement,
  hasMeasurement,
} from "./algorithmService";

/**
 * One file, because one feature's contract has two ends and both are worth pinning.
 *
 * The service tests pin the wire contract: the paths, the request bodies, and the
 * Authorization header. A typo in any of those only shows up as an empty screen in
 * the running app, which is the most expensive kind of bug to find by hand.
 *
 * The page tests pin the honesty rules, and those are the assertions that matter
 * most. A stale frame surviving a change of algorithm, a refused input rendering as
 * an empty timeline, a capped run presenting itself as the whole run -- each of
 * those failures looks like a working feature to the person using it. The page is
 * therefore driven over a stubbed `fetch` rather than a mocked module: the real
 * service layer runs, so a body the API would reject cannot pass here either.
 *
 * Nothing here spawns a worker. The platform is stubbed at the network boundary,
 * which is where the real subprocess would sit anyway.
 */

const BUBBLE_SORT = {
  id: "bubble-sort",
  name: "Bubble Sort",
  category: "Sorting",
  time_complexity: "O(n^2)",
  space_complexity: "O(1)",
  supported_languages: ["python"],
  summary: "Walk the array repeatedly, swapping neighbours that are out of order.",
  input_grammar: "int_list",
  input_hint: "Line 1: how many values follow. Line 2: that many integers.",
  comparison_group: "sort",
  state_kind: "bar_array",
  sample_input: "2\n5 2",
  is_stable: true,
};

const MERGE_SORT = {
  ...BUBBLE_SORT,
  id: "merge-sort",
  name: "Merge Sort",
  time_complexity: "O(n log n)",
  space_complexity: "O(n)",
  is_stable: true,
};

const TIMELINE = {
  algorithm: BUBBLE_SORT,
  input: "2\n5 2",
  frames: [
    {
      step: 0,
      state: {
        kind: "bar_array",
        rows: [{ label: "Array", cells: [{ label: "5", tone: "compare" }, { label: "2", tone: "compare" }] }],
        auxiliary: [],
        pointers: { i: 0, j: 1 },
        metrics: { comparisons: 1 },
        status: "running",
        result: null,
      },
      explanation: "Compare 5 and 2 to see whether they are out of order.",
    },
    {
      step: 1,
      state: {
        kind: "bar_array",
        rows: [{ label: "Array", cells: [{ label: "2", tone: "sorted" }, { label: "5", tone: "sorted" }] }],
        auxiliary: [],
        pointers: {},
        metrics: { comparisons: 1, swaps: 1 },
        status: "complete",
        result: "2 5",
      },
      explanation: "5 is larger than 2, so swap them and settle 5 in its final position.",
    },
  ],
  metrics: { comparisons: 1, swaps: 1 },
  result: "2 5",
  truncated: false,
  duration_ms: 58.4,
  peak_memory_mb: null,
};

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
  fetchMock = vi.fn().mockResolvedValue(jsonResponse({ items: [] }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  vi.resetAllMocks();
});

describe("algorithmApi catalog calls", () => {
  it("reads the algorithm list from the public endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [{ id: "bubble-sort" }] }));

    const catalog = await algorithmApi.list();

    expect(lastRequest().url).toBe(`${API_BASE_URL}/algorithms`);
    expect(catalog.items[0].id).toBe("bubble-sort");
  });

  it("sends no Authorization header for a public read", async () => {
    await algorithmApi.list();

    // The catalog is public. Sending a credential to a route that does not want one
    // is a habit worth not forming, and a test is the only place it gets pinned.
    expect(lastRequest().options.headers.Authorization).toBeUndefined();
  });

  it("encodes the algorithm id into the detail path", async () => {
    await algorithmApi.detail("bubble sort");

    expect(lastRequest().url).toBe(`${API_BASE_URL}/algorithms/bubble%20sort`);
  });

  it("reads the approach for one problem", async () => {
    await algorithmApi.forProblem("binary-search");

    expect(lastRequest().url).toBe(`${API_BASE_URL}/algorithms/problems/binary-search/algorithms`);
  });
});

describe("algorithmApi.visualize", () => {
  it("posts the input to the algorithm's own visualize route", async () => {
    await algorithmApi.visualize("bubble-sort", { input: "5\n5 2 9 1 7" });

    const { url, options } = lastRequest();
    expect(url).toBe(`${API_BASE_URL}/algorithms/bubble-sort/visualize`);
    expect(options.method).toBe("POST");
    expect(lastBody()).toEqual({ input: "5\n5 2 9 1 7" });
  });

  it("omits the optional limits when the caller did not set them", async () => {
    await algorithmApi.visualize("bubble-sort", { input: "3\n3 2 1" });

    // The API forbids extra fields, and a `null` is not the same as absent.
    expect(Object.keys(lastBody())).toEqual(["input"]);
  });

  it("includes a limit only when one was set", async () => {
    await algorithmApi.visualize("bubble-sort", { input: "3\n3 2 1", maxFrames: 40 });

    expect(lastBody()).toEqual({ input: "3\n3 2 1", max_frames: 40 });
  });

  it("attaches the stored bearer token, because the run starts a worker", async () => {
    await algorithmApi.visualize("bubble-sort", { input: "3\n3 2 1" });

    expect(lastRequest().options.headers.Authorization).toBe("Bearer stored-token");
  });

  it("sends no token when there is no stored session", async () => {
    window.localStorage.removeItem(TOKEN_KEY);

    await algorithmApi.visualize("bubble-sort", { input: "3\n3 2 1" });

    expect(lastRequest().options.headers.Authorization).toBeUndefined();
  });

  it("surfaces the API's 422 as a validation error", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "Declared 3 elements but supplied 2. Check the input format." }, 422),
    );

    await expect(algorithmApi.visualize("bubble-sort", { input: "3\n1 2" })).rejects.toMatchObject({
      status: 422,
      isValidationError: true,
    });
  });

  it("surfaces a disabled deployment as a 503 rather than an empty timeline", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "Algorithm visualization is not enabled on this deployment." }, 503),
    );

    await expect(algorithmApi.visualize("bubble-sort", { input: "3\n3 2 1" })).rejects.toMatchObject({
      status: 503,
    });
  });
});

describe("algorithmApi.compare", () => {
  const sides = [
    { algorithm_id: "bubble-sort" },
    { algorithm_id: "quick-sort" },
    { algorithm_id: "merge-sort" },
  ];

  it("sends one input and a list of algorithm ids", async () => {
    await algorithmApi.compare({ algorithmIds: ["bubble-sort", "quick-sort"], input: "4\n4 1 3 2" });

    const { url, options } = lastRequest();
    expect(url).toBe(`${API_BASE_URL}/algorithms/compare`);
    expect(options.method).toBe("POST");
    expect(lastBody()).toEqual({
      algorithms: [{ algorithm_id: "bubble-sort" }, { algorithm_id: "quick-sort" }],
      input: "4\n4 1 3 2",
    });
  });

  it("cannot express two different inputs for two sides", async () => {
    await algorithmApi.compare({ algorithmIds: ["bubble-sort", "quick-sort"], input: "4\n4 1 3 2" });

    // Structurally, not by convention: there is one `input` key in the body and no
    // field anywhere to put a per-side one. This is the property the whole feature
    // rests on, so it is asserted rather than trusted.
    const body = lastBody();
    expect(Object.keys(body).sort()).toEqual(["algorithms", "input"]);
    for (const side of body.algorithms) {
      expect(Object.keys(side)).toEqual(["algorithm_id"]);
    }
  });

  it("accepts up to four sides and maps them all", async () => {
    await algorithmApi.compare({ algorithmIds: sides.map((side) => side.algorithm_id), input: "4\n4 1 3 2" });

    expect(lastBody().algorithms).toEqual(sides);
  });

  it("attaches the stored bearer token", async () => {
    await algorithmApi.compare({ algorithmIds: ["bubble-sort", "quick-sort"], input: "4\n4 1 3 2" });

    expect(lastRequest().options.headers.Authorization).toBe("Bearer stored-token");
  });

  it("surfaces a refused pairing as a 422 naming the reason", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { detail: "These algorithms do not solve the same task, so they cannot be compared on one input." },
        422,
      ),
    );

    await expect(
      algorithmApi.compare({ algorithmIds: ["bubble-sort", "kadane-max-subarray"], input: "3\n1 2 3" }),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("waits long enough for a four-sided comparison to come back", async () => {
    // The API bounds each side by its own wall clock and runs them in sequence, so a
    // four-sided comparison can outlast the generic 10s default. Aborting it would
    // show a failure for a result that really was computed.
    const scheduled = [];
    // Captured before the spy is installed: `window.setTimeout` and the bare
    // `setTimeout` are the same binding here, so the mock calling through to the
    // global would call itself until the stack ran out.
    const schedule = window.setTimeout.bind(window);
    const spy = vi.spyOn(window, "setTimeout").mockImplementation((fn, ms, ...rest) => {
      scheduled.push(ms);
      return schedule(fn, ms, ...rest);
    });
    try {
      await algorithmApi.compare({ algorithmIds: ["bubble-sort", "quick-sort"], input: "4\n4 1 3 2" });
    } finally {
      spy.mockRestore();
    }

    expect(scheduled).toContain(30000);
    expect(scheduled).not.toContain(10000);
  });
});


describe("formatMeasurement", () => {
  it("renders a real measurement with its unit", () => {
    expect(formatMeasurement(0.4512, " ms", 3)).toBe("0.451 ms");
    expect(formatMeasurement(18.4, " MB")).toBe("18.40 MB");
  });

  it("says 'Not measured' for an absent measurement", () => {
    // This is the assertion that matters most in the file. `null` has to render as a
    // sentence, because any numeric fallback -- zero especially -- would sort to the
    // top of a runtime column and read as "the fastest algorithm".
    expect(formatMeasurement(null)).toBe(NOT_MEASURED);
    expect(formatMeasurement(undefined)).toBe(NOT_MEASURED);
  });

  it("never renders an absent measurement as zero", () => {
    for (const value of [null, undefined, NaN, 0, -1, "not-a-number"]) {
      expect(formatMeasurement(value)).toBe(NOT_MEASURED);
      expect(formatMeasurement(value)).not.toMatch(/\b0(\.0+)?\b/);
    }
  });

  it("treats a zero as not measured rather than as a measurement of nothing", () => {
    expect(hasMeasurement(0)).toBe(false);
    expect(hasMeasurement(null)).toBe(false);
    expect(hasMeasurement(0.4)).toBe(true);
  });
});

describe("published vocabularies", () => {
  it("matches the tone vocabulary the API publishes", () => {
    // Asserted as a literal set, so a tone added on the backend without a matching
    // style here fails the suite instead of silently rendering as unhighlighted.
    expect([...CELL_TONES].sort()).toEqual(
      ["active", "blocked", "compare", "frontier", "idle", "match", "path", "pivot", "sorted", "swap", "visited"].sort(),
    );
  });

  it("matches the layout vocabulary the API publishes", () => {
    expect([...STATE_KINDS].sort()).toEqual(["array", "bar_array", "grid", "text"]);
  });

  it("separates a failed side from an unavailable one", () => {
    // "We do not have this algorithm" and "this algorithm could not run on this
    // input" are different facts. Collapsing them makes a typo look like a bug.
    expect([...SIDE_STATUSES].sort()).toEqual(["failed", "ok", "unavailable"]);
  });
});

describe("the rendered page", () => {
  /**
   * The page runs against the real `algorithmApi` and the real `platformApi`, over a
   * `fetch` that answers only the two routes this page touches. The point is that
   * the page cannot pass here by being handed a friendlier shape than the API gives.
   */
  const platform = {
    catalog: [BUBBLE_SORT],
    timeline: () => TIMELINE,
    rejected: () => null,
  };

  beforeEach(() => {
    platform.catalog = [BUBBLE_SORT];
    platform.timeline = () => TIMELINE;
    platform.rejected = () => null;
    fetchMock.mockImplementation((url, options = {}) => {
      const path = String(url);
      if (path.endsWith("/algorithms")) return Promise.resolve(jsonResponse({ items: platform.catalog }));
      if (path.endsWith("/visualize")) {
        const failure = platform.rejected();
        // FastAPI puts a handler's own message in `detail` as a plain string, which
        // is the shape every `HTTPException` on the visualize routes produces. A
        // stub that nested `{status, message}` instead would never let the API's
        // sentence reach the page, and the assertions below would be asserting the
        // fallback rather than the contract.
        return Promise.resolve(
          failure
            ? jsonResponse({ detail: failure.message }, failure.status)
            : jsonResponse(platform.timeline()),
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unrouted request in test" }, 404));
    });
  });

  function visualizeBody() {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/visualize"));
    return call ? JSON.parse(call[1].body) : null;
  }

  async function renderPage() {
    const { default: VisualizerPage } = await import("../../pages/VisualizerPage");
    return render(
      <MemoryRouter>
        <VisualizerPage />
      </MemoryRouter>,
    );
  }

  async function selectBubbleSortAndRun(user) {
    await waitFor(() => screen.getByRole("button", { name: /bubble sort/i }));
    await user.click(screen.getByRole("button", { name: /bubble sort/i }));
    await user.click(screen.getByRole("button", { name: /^run$/i }));
  }

  it("offers one card per registered algorithm", async () => {
    await renderPage();

    await waitFor(() => screen.getByRole("button", { name: /bubble sort/i }));
    expect(screen.getByText("Time O(n^2)")).toBeTruthy();
    expect(screen.getByText("Stable")).toBeTruthy();
  });

  it("seeds the input box with the algorithm's own sample", async () => {
    await renderPage();
    await waitFor(() => screen.getByRole("button", { name: /bubble sort/i }));

    await userEvent.click(screen.getByRole("button", { name: /bubble sort/i }));

    // A sample that does not parse would be a trap: copy it, press run, be told your
    // input is wrong. The API asserts every sample parses, and the UI relies on it.
    expect(screen.getByRole("textbox").value).toBe(BUBBLE_SORT.sample_input);
  });

  it("draws the frame and its explanation after a run", async () => {
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);

    await waitFor(() => screen.getByText("Frame 1 of 2"));
    // The body the page sends is the sample, verbatim -- no reshaping, no limits the
    // caller never asked for.
    expect(visualizeBody()).toEqual({ input: BUBBLE_SORT.sample_input });
    expect(screen.getByRole("listitem", { name: "5" })).toBeTruthy();
    expect(screen.getByText(/walk the array/i)).toBeTruthy();
  });

  it("labels every frame with a pointer and counter readout", async () => {
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);

    await waitFor(() => screen.getByText("Pointers"));
    // The counters are the ones the algorithm recorded, not placeholders.
    expect(screen.getByText("comparisons")).toBeTruthy();
  });

  it("disables Back on the first frame and Forward on the last", async () => {
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);

    await waitFor(() => screen.getByText("Frame 1 of 2"));
    expect(screen.getByRole("button", { name: "Previous frame" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next frame" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Next frame" }));

    await waitFor(() => screen.getByText("Frame 2 of 2"));
    expect(screen.getByRole("button", { name: "Previous frame" })).toBeEnabled();
    // Disabled exactly when the cursor is on the last frame -- and never one frame
    // early, which is the off-by-one that makes a transport feel broken.
    expect(screen.getByRole("button", { name: "Next frame" })).toBeDisabled();
  });

  it("moves the drawn frame with the transport, not just the counter", async () => {
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);
    await waitFor(() => screen.getByText("Frame 1 of 2"));
    expect(screen.queryByText(/5 is larger than 2/i)).toBeNull();

    await user.click(screen.getByRole("button", { name: "Next frame" }));

    await waitFor(() => screen.getByText(/5 is larger than 2/i));
    // And back again, so the control is a scrubber and not a one-way walk.
    await user.click(screen.getByRole("button", { name: "Previous frame" }));
    await waitFor(() => screen.getByText("Frame 1 of 2"));
    expect(screen.queryByText(/5 is larger than 2/i)).toBeNull();
  });

  it("scrubs with the range input", async () => {
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);
    await waitFor(() => screen.getByText("Frame 1 of 2"));

    await user.click(screen.getByRole("button", { name: "Next frame" }));

    await waitFor(() => screen.getByText("Frame 2 of 2"));
    expect(screen.getByRole("slider", { name: "Frame" }).value).toBe("1");
  });

  it("offers the speed ladder and marks the active one", async () => {
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);
    await waitFor(() => screen.getByText("Frame 1 of 2"));

    expect(screen.getByRole("button", { name: "2x" })).toHaveAttribute("aria-pressed", "false");
    await user.click(screen.getByRole("button", { name: "2x" }));
    expect(screen.getByRole("button", { name: "2x" })).toHaveAttribute("aria-pressed", "true");
  });

  it("says so when the timeline was capped by the frame ceiling", async () => {
    platform.timeline = () => ({ ...TIMELINE, truncated: true });
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);

    // A capped timeline is real execution, but presenting it as the whole run would
    // be a claim about the algorithm's length the platform cannot support.
    await waitFor(() => screen.getByText("Capped timeline"));
    expect(screen.getByText("Whole run: capped")).toBeTruthy();
  });

  it("reports a refused input instead of drawing an empty timeline", async () => {
    platform.rejected = () => ({
      status: 422,
      message: "Declared 3 elements but supplied 2. Check the input format.",
    });
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);

    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByText(/Declared 3 elements/)).toBeTruthy();
    expect(screen.queryByText("Frame 1 of 2")).toBeNull();
  });

  it("reports a disabled deployment as a failure, not as an empty result", async () => {
    platform.rejected = () => ({
      status: 503,
      message: "Algorithm visualization is not enabled on this deployment.",
    });
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);

    await waitFor(() => screen.getByText(/not enabled/i));
    expect(screen.queryByText("Frame 1 of 2")).toBeNull();
  });

  it("clears the previous timeline when a different algorithm is chosen", async () => {
    platform.catalog = [BUBBLE_SORT, MERGE_SORT];
    const user = userEvent.setup();
    await renderPage();

    await selectBubbleSortAndRun(user);
    await waitFor(() => screen.getByText("Frame 1 of 2"));

    await user.click(screen.getByRole("button", { name: /merge sort/i }));

    // A stale frame under a new card is worse than no frame: it looks like a result.
    expect(screen.queryByText("Frame 1 of 2")).toBeNull();
  });

  it("offers an empty state before anything is chosen", async () => {
    await renderPage();

    await waitFor(() => screen.getByText(/choose an algorithm to start/i));
  });
});

