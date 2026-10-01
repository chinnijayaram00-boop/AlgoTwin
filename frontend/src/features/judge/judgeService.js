import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * The longest this client waits for a run.
 *
 * Longer than `apiClient`'s default, because the API holds the request open for
 * as long as the judge takes: the judge's own budget is tens of seconds, and a
 * run that is going to come back at all comes back within it. The number is not
 * a licence to wait forever -- it is an upper bound on a request the server
 * bounds itself.
 */
export const RUN_TIMEOUT_MS = 60000;

/**
 * Running a learner's code is a signed-in action.
 *
 * The API takes the learner's identity from the bearer token alone, so there is
 * deliberately no `userId` argument anywhere in this module: the client cannot
 * run code as, or read results belonging to, anyone else.
 *
 * Nothing here sends a verdict, a status, or a test-case count. The API rejects
 * those fields outright, and inventing them client-side is exactly the failure
 * this feature exists to remove.
 */
function authOptions(timeoutMs) {
  const token = getStoredToken();
  return token ? { token, timeoutMs } : { timeoutMs };
}

export const judgeService = {
  /**
   * The languages this deployment can actually run, and whether execution is
   * switched on at all.
   *
   * The editor draws its tabs from this rather than from a list in the bundle, so
   * a language the runner will refuse cannot be offered -- which is how a Java tab
   * once led to a submission the API rejected with a bare 422.
   */
  languages() {
    return apiClient.get("/judge/languages");
  },

  /**
   * Run the learner's source against one problem.
   *
   * With no `stdin`, the API runs the problem's *visible* cases and returns a
   * verdict. With `stdin`, it runs the program once on that input and returns only
   * what it printed -- there is no expected output to compare against, so the
   * response carries no verdict and no counts, and this client must not invent
   * either.
   *
   * A run stores nothing: no submission, no progress change, no attempt.
   */
  run({ problemId, language, sourceCode, stdin }) {
    const body = { language, source_code: sourceCode };
    if (stdin !== undefined && stdin !== null) {
      body.stdin = stdin;
    }
    return apiClient.post(
      `/problems/${encodeURIComponent(problemId)}/run`,
      body,
      authOptions(RUN_TIMEOUT_MS),
    );
  },
};
