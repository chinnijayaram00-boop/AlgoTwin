import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * Progress is per learner, so every call carries the session token.
 *
 * There is deliberately no `userId` argument anywhere: the API identifies the
 * learner from the token alone, so the client cannot ask for someone else's
 * progress even by accident.
 */
function authOptions() {
  const token = getStoredToken();
  return token ? { token } : {};
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

export const progressService = {
  summary() {
    return apiClient.get("/progress/me", authOptions());
  },

  problems(params = {}) {
    return apiClient.get(withQuery("/progress/problems", params), authOptions());
  },

  problem(problemId) {
    return apiClient.get(`/progress/problems/${encodeURIComponent(problemId)}`, authOptions());
  },

  /**
   * Set the learner's status for a problem. Idempotent server-side, so this is
   * also the reset path: sending `not_started` clears the recorded trail.
   */
  setStatus(problemId, status, metrics = {}) {
    const body = { ...metrics, ...(status ? { status } : {}) };
    return apiClient.put(
      `/progress/problems/${encodeURIComponent(problemId)}`,
      body,
      authOptions(),
    );
  },

  /**
   * Record one more attempt. This is a progress marker only: no code is sent,
   * run, or graded.
   */
  recordAttempt(problemId, metrics = {}) {
    return apiClient.post(
      `/progress/problems/${encodeURIComponent(problemId)}/attempt`,
      metrics,
      authOptions(),
    );
  },
};
