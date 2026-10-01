import { useCallback, useState } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { judgeService } from "./judgeService";

/**
 * Running the learner's current source, and the result of the last run.
 *
 * Deliberately not `useApiResource`: a run is an action, not a resource. There is
 * nothing to fetch on mount, and refetching would re-run code without being asked.
 * The first run happens when the learner presses the button, which is also why
 * `result` starts null rather than as a placeholder -- the UI has to be able to
 * say "not run yet", and an empty object shaped like a result would be a claim.
 *
 * `running` covers the in-flight window, and `actionError` reports a rejected run
 * separately from the previous `result`, because the two need different
 * affordances: a failure to run the program is not a failure of the program.
 *
 * `enabled` is false only while the session is still being restored, so the caller
 * renders a loading state in that window instead of firing a request that could
 * only come back 401.
 */
export function useCodeRun(problemId, { enabled = true } = {}) {
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState("");

  const run = useCallback(
    async ({ language, sourceCode, stdin } = {}) => {
      if (!enabled || !problemId) return null;
      setRunning(true);
      setActionError("");
      try {
        const response = await judgeService.run({ problemId, language, sourceCode, stdin });
        setResult(response);
        return response;
      } catch (runFailure) {
        // The previous result is kept, because a failed request says nothing
        // about whether the program in the editor is correct. It is cleared
        // explicitly by `reset` and by the caller switching problems.
        setActionError(runFailure.message);
        return null;
      } finally {
        setRunning(false);
      }
    },
    [enabled, problemId],
  );

  const reset = useCallback(() => {
    setResult(null);
    setActionError("");
  }, []);

  return { result, running, actionError, run, reset };
}

/**
 * The languages this deployment can run, for the editor's tabs.
 *
 * A read, so it goes through `useApiResource` rather than the action path above.
 * A failure here is not a failure of the page: the workspace falls back to the
 * problem's own advertised languages, which are the same list the catalog was
 * validated against. What it must never do is invent a language, because a tab
 * the runner cannot honour ends in a 422.
 */
export function useRunnableLanguages({ enabled = true } = {}) {
  const load = useCallback(
    () => (enabled ? judgeService.languages() : Promise.resolve(null)),
    [enabled],
  );
  const { data, error, loading, reload } = useApiResource(load);
  const languages = Array.isArray(data?.items) ? data.items : [];

  return { languages, error, loading, reload };
}
