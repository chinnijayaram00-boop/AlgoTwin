import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * Calls for the grounded AI coach.
 *
 * Three generation endpoints and one status read. Two properties are deliberate.
 *
 * **Nothing here can choose what a request is grounded in.** Each generation call
 * takes only identifiers -- a problem id, a submission id -- and the server resolves
 * the facts from its own database. There is no parameter through which a caller
 * could pass a statement, an editorial, a test case, a status, or a set of
 * "facts", because the API has no field that accepts one. A client cannot smuggle
 * its own context into a prompt, and cannot ask about a submission that is not its
 * own.
 *
 * **There is deliberately no `userId` argument anywhere.** The API identifies the
 * learner from the bearer token alone, matching `judgeService` and
 * `submissionService`. A client that could name a user would be able to ask the
 * server a question it should refuse, and the refusal is the feature.
 */

/**
 * How long a generation may take before this client gives up.
 *
 * Longer than `apiClient`'s ten-second default, because a generation is a model
 * call and the deployment budgets one explicitly (`AI_TIMEOUT_MS`, 30s by default).
 * The client must not be the thing that decides the server's answer arrived too
 * late -- otherwise a learner sees a timeout while the answer is being stored, and
 * a refresh reveals text that was never missing. Set below the server's own budget
 * so the server, which can explain a 504, is the one that gives up first.
 */
export const AI_TIMEOUT_MS = 45000;

/** The complexity the API returns when a model could not determine one. */
export const UNDETERMINED_COMPLEXITY = "undetermined";

function authOptions(timeoutMs = AI_TIMEOUT_MS) {
  const token = getStoredToken();
  return token ? { token, timeoutMs } : { timeoutMs };
}

export const aiService = {
  /**
   * Whether this deployment can generate anything, and why not if it cannot.
   *
   * Public, so it is sent without a token. The UI calls this before offering an AI
   * action, rather than letting a learner press a button whose only possible
   * answer is a 503.
   */
  status() {
    return apiClient.get("/ai/status");
  },

  /**
   * The problem's intended approach, generated from the catalog's own record.
   *
   * `focus` is a preference -- `approach` or `correctness` -- and can only select
   * between forms the catalog already publishes. It is omitted rather than sent as
   * `null` because the two are different requests to a strict request schema.
   *
   * Repeating a request returns the stored answer without a provider call, so the
   * second press is free. The response says so through `cached`.
   */
  explanation(problemId, { focus } = {}) {
    const body = focus ? { focus } : {};
    return apiClient.post(
      `/problems/${encodeURIComponent(problemId)}/explanation`,
      body,
      authOptions(),
    );
  },

  /**
   * A diagnosis of one recorded submission.
   *
   * Grounded in the stored verdict and the judge's measurements -- never in the
   * learner's source, and never in a test case, because a judged submission stores
   * counts rather than cases. The API filters by the bearer token, so a submission
   * that is not the learner's answers 404 and this client has nothing to handle.
   */
  diagnosis(submissionId) {
    return apiClient.post(
      `/submissions/${encodeURIComponent(submissionId)}/diagnose`,
      undefined,
      authOptions(),
    );
  },

  /**
   * A time and space complexity for a snippet.
   *
   * `problemId` is optional and contributes only the catalog's recorded target
   * complexity for comparison. The snippet itself is sent once and stored nowhere.
   */
  complexity({ language, sourceCode, problemId } = {}) {
    const query =
      problemId === undefined || problemId === null || problemId === ""
        ? ""
        : `?problem_id=${encodeURIComponent(problemId)}`;
    return apiClient.post(
      `/code/complexity${query}`,
      { language, source_code: sourceCode },
      authOptions(),
    );
  },
};

/**
 * Whether a complexity is a real answer.
 *
 * The API reports `"undetermined"` rather than guessing, so the UI has to treat
 * that string as the absence of a claim. Rendering it as if it were an analysis
 * would undo the honesty the backend went to the trouble of keeping.
 */
export function isDeterminedComplexity(value) {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.trim().toLowerCase() !== UNDETERMINED_COMPLEXITY
  );
}

export default aiService;