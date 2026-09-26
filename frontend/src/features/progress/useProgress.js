import { useCallback, useState } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { progressService } from "./progressService";

/**
 * The learner's overall standing for the dashboard.
 *
 * `requiresAuth` is false only while the session is still being restored; the
 * caller renders a loading state in that window rather than firing a request
 * that could only come back 401.
 */
export function useProgressSummary({ enabled = true } = {}) {
  const load = useCallback(() => progressService.summary(), []);
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  return useApiResource(request);
}

/** Every published problem annotated with the learner's status, with filters. */
export function useProgressList(params = {}, { enabled = true } = {}) {
  const { status, difficulty, topic, limit = 50, offset = 0 } = params;
  const load = useCallback(
    () => progressService.problems({ status, difficulty, topic, limit, offset }),
    [status, difficulty, topic, limit, offset],
  );
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  return useApiResource(request);
}

/**
 * One problem's progress, plus the mutations that change it.
 *
 * Each mutation replaces the local record with the server's response and then
 * refetches, so the UI can never drift from what is stored. `saving` covers the
 * in-flight window, and `actionError` reports a rejected change separately from
 * a failed load, because the two need different affordances in the UI.
 */
export function useProblemProgress(problemId, { enabled = true } = {}) {
  const load = useCallback(
    () => (problemId ? progressService.problem(problemId) : Promise.resolve(null)),
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

  const run = useCallback(
    async (operation) => {
      setSaving(true);
      setActionError("");
      try {
        const updated = await operation();
        // The response is authoritative, and the refetch also re-syncs the
        // dashboard aggregate the next time it is read.
        await reload();
        return updated;
      } catch (actionFailure) {
        setActionError(actionFailure.message);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [reload],
  );

  const setStatus = useCallback(
    (status) => run(() => progressService.setStatus(problemId, status)),
    [problemId, run],
  );

  const recordAttempt = useCallback(
    (metrics = {}) => run(() => progressService.recordAttempt(problemId, metrics)),
    [problemId, run],
  );

  return { data, error, errorStatus, loading, reload, saving, actionError, setStatus, recordAttempt };
}
