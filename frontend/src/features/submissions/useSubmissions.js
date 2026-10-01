import { useCallback, useState } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { useRefreshKey } from "../../hooks/useRefreshKey";
import { submissionService } from "./submissionService";

/** The API's default page size; kept here so the pager and the request agree. */
export const DEFAULT_PAGE_SIZE = 20;

/** The newest few attempts, for the workspace side panel. */
export const PROBLEM_PREVIEW_SIZE = 5;

/**
 * One page of the learner's own submission history.
 *
 * `enabled` is false only while the session is still being restored, so the
 * caller renders a loading state in that window instead of firing a request
 * that could only come back 401.
 *
 * `refreshKey` asks for one extra read when it changes. A page that is not
 * mounted while the learner submits cannot see the new row otherwise, and a
 * history that silently missed a submission would under-report the very thing
 * the learner just did.
 */
export function useSubmissionList(params = {}, { enabled = true, refreshKey = 0 } = {}) {
  const { problemId, language, status, page = 1, pageSize = DEFAULT_PAGE_SIZE } = params;
  const load = useCallback(
    () =>
      submissionService.list({
        problem_id: problemId,
        language,
        status,
        page,
        page_size: pageSize,
      }),
    [problemId, language, status, page, pageSize],
  );
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  const resource = useApiResource(request);
  useRefreshKey(refreshKey, resource.reload);
  return resource;
}

/**
 * One submission, with the learner's own source.
 *
 * A 404 here is genuinely ambiguous on purpose -- the API will not say whether
 * the row is missing or belongs to someone else -- so the caller renders a
 * "not in your history" message rather than an error.
 */
export function useSubmissionDetail(submissionId, { enabled = true } = {}) {
  const load = useCallback(
    () => (submissionId ? submissionService.detail(submissionId) : Promise.resolve(null)),
    [submissionId],
  );
  const request = useCallback(() => (enabled && submissionId ? load() : Promise.resolve(null)), [
    enabled,
    load,
    submissionId,
  ]);
  return useApiResource(request);
}

/**
 * The learner's attempts on one problem, plus the action that adds another.
 *
 * `create` submits the source to the judge and then refetches, so the panel can
 * never show a row the API does not hold. `saving` covers the in-flight window
 * and `actionError` reports a rejected write separately from a failed load,
 * because the two need different affordances. `created` holds the graded record
 * the API returned, which is what the caller renders as the verdict.
 *
 * `onJudged` fires after a successful submit. The API is what decides whether a
 * problem is solved -- only an `accepted` verdict moves it -- so the client
 * cannot infer that itself; it only needs to know something changed and refetch.
 */
export function useProblemSubmissions(problemId, { enabled = true, onJudged } = {}) {
  const load = useCallback(
    () =>
      problemId
        ? submissionService.forProblem(problemId, { page: 1, page_size: PROBLEM_PREVIEW_SIZE })
        : Promise.resolve(null),
    [problemId],
  );
  const request = useCallback(() => (enabled && problemId ? load() : Promise.resolve(null)), [
    enabled,
    load,
    problemId,
  ]);
  const { data, error, errorStatus, loading, reload } = useApiResource(request);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const [created, setCreated] = useState(null);

  const create = useCallback(
    async ({ language, sourceCode }) => {
      setSaving(true);
      setActionError("");
      setCreated(null);
      try {
        const stored = await submissionService.create({ problemId, language, sourceCode });
        setCreated(stored);
        await reload();
        if (onJudged) {
          onJudged(stored);
        }
        return stored;
      } catch (writeFailure) {
        setActionError(writeFailure.message);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [problemId, reload, onJudged],
  );

  return {
    data,
    error,
    errorStatus,
    loading,
    reload,
    saving,
    actionError,
    created,
    create,
  };
}
