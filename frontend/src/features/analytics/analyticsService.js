import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * The analytics summary is one learner's own persisted rows, so every call
 * carries the session token.
 *
 * There is deliberately no `userId` argument anywhere: the API identifies the
 * learner from the token alone, so the client cannot ask for somebody else's
 * numbers even by accident.
 */
function authOptions() {
  const token = getStoredToken();
  return token ? { token } : {};
}

export const analyticsService = {
  /**
   * The whole summary in one read: overview, difficulty and topic
   * breakdowns, verdicts, the activity window, the learning-path position,
   * and mock-interview performance.
   *
   * One endpoint rather than a family of narrowly-scoped ones, because every
   * section is a projection of the same rows at the same moment; splitting
   * them would let the headline number and the chart disagree.
   *
   * @param {{ days?: number }} [options] The activity window to request. It
   *   only bounds the activity series; every other section covers the whole
   *   recorded history. Omitted means the server's default.
   */
  summary({ days } = {}) {
    const query = Number.isFinite(days) && days > 0 ? `?days=${encodeURIComponent(days)}` : "";
    return apiClient.get(`/analytics/summary${query}`, authOptions());
  },
};
