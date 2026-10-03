import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * Client for the algorithm lab.
 *
 * Three calls, and the split between them matters: `list` and `detail` are public
 * reads, while `visualize` and `compare` start a worker process on the API and are
 * therefore authenticated like a code run. The service attaches the stored bearer
 * token to those two and never to the reads, so the client cannot accidentally send
 * a credential where one is not wanted.
 *
 * There is no `userId` argument anywhere. The API identifies the learner from the
 * token alone; a parameter for it would only create a way to ask for someone
 * else's data, and there is nothing to ask for -- the algorithm lab has no
 * per-learner state.
 */

/**
 * How long a lab call may take before the client gives up.
 *
 * Both runs are bounded server-side by `VISUALIZATION_WALL_CLOCK_MS` (3s by
 * default) plus the worker's grace period, and the comparisons by that times the
 * number of sides. The generic 10s default covers a single visualization but not a
 * four-sided comparison, and a timeout shown for a comparison that really did finish
 * would be worse than waiting: the learner would see a failure for a result that
 * exists.
 */
const LAB_TIMEOUT_MS = 30000;

function authOptions(extra = {}) {
  const token = getStoredToken();
  return token ? { token, ...extra } : { ...extra };
}

/**
 * The closed set of cell tones the API publishes.
 *
 * The renderer degrades an unrecognised tone to idle rather than rendering broken
 * markup, but the *test* asserts this set exactly: a new tone added on the backend
 * without a matching style here would otherwise pass silently and show up as "the
 * animation isn't highlighting anything".
 */
export const CELL_TONES = [
  "idle",
  "active",
  "compare",
  "pivot",
  "swap",
  "sorted",
  "match",
  "visited",
  "frontier",
  "path",
  "blocked",
];

/** The closed set of layouts a frame can be drawn in. */
export const STATE_KINDS = ["array", "bar_array", "grid", "text"];

/**
 * The values the API may report for a side that failed to run.
 *
 * `unavailable` and `failed` are separate because they mean different things: the
 * first is "this platform does not have that algorithm", the second is "it has it,
 * and it could not run on this input". Collapsing them would make a typo look like
 * a bug in the algorithm.
 */
export const SIDE_STATUSES = ["ok", "failed", "unavailable"];

/** What the UI shows for a measurement the platform did not take. */
export const NOT_MEASURED = "Not measured";

/**
 * Render a measurement, or say plainly that it was not taken.
 *
 * `null`, `undefined`, and a non-positive number all render as "Not measured". That
 * is the single most important function in this file: the alternative is a `0` that
 * sorts to the top of a runtime column and reads as "the fastest algorithm", which
 * is a claim the platform never made.
 */
export function formatMeasurement(value, suffix = "", digits = 2) {
  if (value === null || value === undefined) return NOT_MEASURED;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return NOT_MEASURED;
  return `${numeric.toFixed(digits)}${suffix}`;
}

/** True when a measurement is a real number rather than an absence. */
export function hasMeasurement(value) {
  const numeric = Number(value);
  return value !== null && value !== undefined && Number.isFinite(numeric) && numeric > 0;
}

export const algorithmApi = {
  /** The public catalog. No token: a card naming a complexity is not learner data. */
  list() {
    return apiClient.get("/algorithms");
  },

  /** One algorithm in full, including the pairings the API would accept. */
  detail(algorithmId) {
    return apiClient.get(`/algorithms/${encodeURIComponent(algorithmId)}`);
  },

  /** The algorithms a catalog problem names as its approach. */
  forProblem(slug) {
    return apiClient.get(`/algorithms/problems/${encodeURIComponent(slug)}/algorithms`);
  },

  /**
   * Run one algorithm over one input and return its timeline.
   *
   * Only the fields the API accepts are sent, and only when set. A `maxFrames` of
   * `undefined` is omitted rather than serialized as `null`, because the schema
   * forbids extra fields and a null would be a 422 for no reason.
   */
  visualize(algorithmId, { input, maxFrames, wallClockMs } = {}) {
    return apiClient.post(
      `/algorithms/${encodeURIComponent(algorithmId)}/visualize`,
      compact({ input, max_frames: maxFrames, wall_clock_ms: wallClockMs }),
      authOptions({ timeoutMs: LAB_TIMEOUT_MS }),
    );
  },

  /**
   * Run two to four algorithms on one shared input.
   *
   * The body carries a single `input`. That is not a simplification of the API's
   * shape -- it is the API's shape, and it is what makes "every side saw the same
   * input" a structural property rather than a promise.
   */
  compare({ algorithmIds = [], input, maxFrames, repetitions, wallClockMs } = {}) {
    return apiClient.post(
      "/algorithms/compare",
      compact({
        algorithms: algorithmIds.map((algorithmId) => ({ algorithm_id: algorithmId })),
        input,
        max_frames: maxFrames,
        repetitions,
        wall_clock_ms: wallClockMs,
      }),
      authOptions({ timeoutMs: LAB_TIMEOUT_MS }),
    );
  },
};

/** Drop unset fields so the request body only ever holds what was set. */
function compact(body) {
  return Object.fromEntries(
    Object.entries(body).filter(([, value]) => value !== undefined && value !== null),
  );
}
