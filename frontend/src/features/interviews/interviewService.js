import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * The mock interview API, mirrored from the interview routes.
 *
 * Every call is authenticated and scoped by the bearer token: there is no id
 * anywhere that could name another learner's session, matching the backend
 * contract where `user_id` is resolved from the token and never sent.
 *
 * The client only ever sends calibration and code. A create request names a
 * role, an optional seniority, optional filters, and a question budget; an
 * answer names a language and source. Verdicts, pass counts, times, scores,
 * and the selection itself are written by the server and only read back.
 *
 * Like the submission contract, "active" is a server concept too: the timer is
 * stored as `expires_at`, `remaining_seconds` is computed by the API, and a
 * read after the clock runs out is the read that finalises the session.
 */

/**
 * The judge grades an answer, so an interview submission gets the same headroom
 * the submission contract gives the judge.
 */
const SUBMIT_TIMEOUT_MS = 60000;

function authOptions(extra = {}) {
  const token = getStoredToken();
  return token ? { token, ...extra } : { ...extra };
}

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  });
  return query.toString();
}

function withQuery(path, params) {
  const query = toQuery(params);
  return query ? `${path}?${query}` : path;
}

export const interviewService = {
  /** Open a session. An existing created or running session is a 409. */
  create({ role, level, difficulty, topic, questionCount, durationMinutes }) {
    return apiClient.post(
      "/interviews",
      {
        role,
        level: level || null,
        difficulty: difficulty || null,
        topic: topic || null,
        question_count: questionCount,
        duration_minutes: durationMinutes,
      },
      authOptions(),
    );
  },
  /** One page of the learner's own interview history, newest first. */
  list(params = {}) {
    return apiClient.get(
      withQuery("/interviews", {
        status: params.status,
        page: params.page,
        page_size: params.pageSize,
      }),
      authOptions(),
    );
  },
  /**
   * The learner's active session, finalised by the server if its clock ran out.
   * A 404 is the honest "no active interview right now".
   */
  active() {
    return apiClient.get("/interviews/active", authOptions());
  },
  detail(interviewId) {
    return apiClient.get(`/interviews/${encodeURIComponent(interviewId)}`, authOptions());
  },
  /** Start the clock on a created session. */
  start(interviewId) {
    return apiClient.post(`/interviews/${encodeURIComponent(interviewId)}/start`, {}, authOptions());
  },
  /** Judge the learner's answer to one recorded question. */
  submit({ interviewId, position, language, sourceCode }) {
    return apiClient.post(
      `/interviews/${encodeURIComponent(interviewId)}/questions/${encodeURIComponent(position)}/submit`,
      { language, source_code: sourceCode },
      authOptions({ timeoutMs: SUBMIT_TIMEOUT_MS }),
    );
  },
  /** End a running session early and score what was answered. */
  finish(interviewId) {
    return apiClient.post(`/interviews/${encodeURIComponent(interviewId)}/finish`, {}, authOptions());
  },
  /** Discard a created or running session, leaving it unscored. */
  abandon(interviewId) {
    return apiClient.post(`/interviews/${encodeURIComponent(interviewId)}/abandon`, {}, authOptions());
  },
  /** The post-session report. Only served once the session is completed. */
  report(interviewId) {
    return apiClient.get(`/interviews/${encodeURIComponent(interviewId)}/report`, authOptions());
  },
};