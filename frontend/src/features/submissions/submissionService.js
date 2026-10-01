import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * Submission calls for the signed-in learner.
 *
 * Submitting *judges*: the API runs the learner's program against the
 * problem's full case set and stores the verdict it reports. This client never
 * sends a status, a runtime, or a test-case count -- the API would reject them
 * anyway, because those are the judge's to write.
 *
 * As with `progressService`, there is deliberately no `userId` argument
 * anywhere. The API identifies the learner from the bearer token alone, so the
 * client cannot ask for someone else's history even by accident.
 */

/**
 * How long a submit may take before the client gives up.
 *
 * Deliberately the same ceiling `judgeService` uses for a Run, and for the same
 * reason: the API judges synchronously, bounded by the deployment's
 * `MAX_JUDGE_WALL_CLOCK_MS` (30s by default) plus the judge's grace period for
 * tearing down a worker. The generic 10s default would abort a legitimate
 * request that the server then went on to store and grade -- the learner would
 * see a timeout and a verdict that never arrives, for a submission that really
 * was recorded. Setting this lower than the server's budget is how that
 * happens.
 */
const SUBMIT_TIMEOUT_MS = 60000;

function authOptions(extra = {}) {
  const token = getStoredToken();
  return token ? { token, ...extra } : { ...extra };
}

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, value);
    }
  });
  return query.toString();
}

function withQuery(path, params) {
  const query = toQuery(params);
  return query ? `${path}?${query}` : path;
}

export const submissionService = {
  /**
   * Submit the learner's code to be judged, and get the graded record back.
   *
   * Only `problemId`, `language`, and `sourceCode` are sent, because those are
   * the only three fields the API accepts. The response is the stored verdict:
   * a pass, a wrong answer, a crash, a timeout, and the measurements the judge
   * took. A submission counts as one attempt on the learner's progress record,
   * and only a real `accepted` verdict marks the problem solved.
   */
  create({ problemId, language, sourceCode }) {
    return apiClient.post(
      "/submissions",
      { problem_id: problemId, language, source_code: sourceCode },
      authOptions({ timeoutMs: SUBMIT_TIMEOUT_MS }),
    );
  },

  /** One page of the learner's own submission history, newest first. */
  list(params = {}) {
    return apiClient.get(withQuery("/submissions", params), authOptions());
  },

  /**
   * One submission, with its source. A row belonging to another learner answers
   * 404, the same as a row that does not exist, so the UI cannot tell the two
   * apart either and must not imply that it can.
   */
  detail(submissionId) {
    return apiClient.get(`/submissions/${encodeURIComponent(submissionId)}`, authOptions());
  },

  /** The learner's own submissions for one problem, newest first. */
  forProblem(problemId, params = {}) {
    return apiClient.get(
      withQuery(`/problems/${encodeURIComponent(problemId)}/submissions`, params),
      authOptions(),
    );
  },
};
