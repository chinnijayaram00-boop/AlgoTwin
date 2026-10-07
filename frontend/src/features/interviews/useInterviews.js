import { useCallback, useEffect, useRef, useState } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { useRefreshKey } from "../../hooks/useRefreshKey";
import { interviewService } from "./interviewService";

/** The API's default page size; kept here so the pager and the request agree. */
export const DEFAULT_PAGE_SIZE = 20;

/**
 * The learner's whole interview surface in one hook: the active session if
 * there is one, and every action that moves it.
 *
 * `session` is the API's latest word on the interview -- set from the response
 * of every action, never invented client-side. A `created` session is one that
 * has its questions recorded but no clock yet; `in_progress` is a running
 * timer; `completed` and `abandoned` are terminal. `loading`/`loadError` cover
 * the initial active-session read, `saving`/`actionError` cover an action in
 * flight, so the two windows get different affordances.
 *
 * A 404 from `active` is not an error: it is the honest "no active interview
 * right now", and it means the learner should be offered the setup view.
 * Every other status becomes a real `loadError`.
 */
export function useInterviews() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");

  const loadActive = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      setSession(await interviewService.active());
    } catch (error) {
      // The active read is also the read that finalises a timed-out session, so
      // a completed session can surface out of this call rather than a 404.
      setSession(null);
      if (error.status !== 404) setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActive();
  }, [loadActive]);

  const run = useCallback(async (action) => {
    setSaving(true);
    setActionError("");
    try {
      const result = await action();
      setSession(result);
      return result;
    } catch (error) {
      setActionError(error.message);
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  const sessionId = session?.id;

  const create = useCallback(
    (calibration) => run(() => interviewService.create(calibration)),
    [run],
  );
  const start = useCallback(
    () => (sessionId == null ? Promise.resolve(null) : run(() => interviewService.start(sessionId))),
    [run, sessionId],
  );
  const submitAnswer = useCallback(
    ({ position, language, sourceCode }) =>
      sessionId == null
        ? Promise.resolve(null)
        : run(() => interviewService.submit({ interviewId: sessionId, position, language, sourceCode })),
    [run, sessionId],
  );
  const finish = useCallback(
    () => (sessionId == null ? Promise.resolve(null) : run(() => interviewService.finish(sessionId))),
    [run, sessionId],
  );
  const abandon = useCallback(
    () => (sessionId == null ? Promise.resolve(null) : run(() => interviewService.abandon(sessionId))),
    [run, sessionId],
  );

  return {
    session,
    loading,
    loadError,
    saving,
    actionError,
    reload: loadActive,
    create,
    start,
    submitAnswer,
    finish,
    abandon,
  };
}

/**
 * A local mirror of the server clock for a running session.
 *
 * The countdown starts from the server-computed `remainingSeconds` and ticks
 * down between API responses, so the client never invents an expiry. At zero it
 * doesn't declare the session over -- it calls `onExpire`, and the caller reads
 * the active session again, because only the server's stored `expires_at` can
 * finalise a session. A new `remainingSeconds` (from a fresh response) resets
 * the count so client drift never accumulates.
 */
export function useInterviewCountdown(remainingSeconds, { enabled = true, onExpire } = {}) {
  const [remaining, setRemaining] = useState(remainingSeconds ?? null);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    setRemaining(enabled ? remainingSeconds : null);
    if (!enabled || remainingSeconds == null || remainingSeconds <= 0) return undefined;

    const timer = window.setInterval(() => {
      setRemaining((current) => {
        if (current == null || current > 1) {
          return current == null ? current : current - 1;
        }
        window.clearInterval(timer);
        if (onExpireRef.current) onExpireRef.current();
        return 0;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [enabled, remainingSeconds]);

  return remaining;
}

/**
 * One page of the learner's interview history, newest first.
 *
 * `enabled` is false while a session is open on the page: the history is hidden
 * then, and reading it is a write we do not need. `refreshKey` asks for one
 * extra read when it changes, so an interview that just became terminal shows
 * up without the learner leaving the page.
 */
export function useInterviewHistory({ enabled = true, refreshKey = 0, page = 1, pageSize = DEFAULT_PAGE_SIZE } = {}) {
  const load = useCallback(
    () => interviewService.list({ page, pageSize }),
    [page, pageSize],
  );
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  const resource = useApiResource(request);
  useRefreshKey(refreshKey, resource.reload);
  return resource;
}

/**
 * The post-session report for one completed interview.
 *
 * A 404 here is as ambiguous as everywhere else -- the API will not say whether
 * the id is missing or belongs to someone else -- so the caller renders a "not
 * in your history" message rather than an error. A 409 means the session has
 * not completed yet, which the caller normally prevents by gating this to
 * completed sessions.
 */
export function useInterviewReport(interviewId, { enabled = true } = {}) {
  const load = useCallback(
    () => (interviewId ? interviewService.report(interviewId) : Promise.resolve(null)),
    [interviewId],
  );
  const request = useCallback(() => (enabled && interviewId ? load() : Promise.resolve(null)), [
    enabled,
    load,
    interviewId,
  ]);
  return useApiResource(request);
}