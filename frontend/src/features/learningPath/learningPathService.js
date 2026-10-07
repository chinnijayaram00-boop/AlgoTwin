import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";

/**
 * The learning path is per learner, so every call carries the session token.
 *
 * There is deliberately no `userId` argument anywhere: the API identifies the
 * learner from the token alone, so the client cannot ask for someone else's
 * path even by accident.
 */
function authOptions() {
  const token = getStoredToken();
  return token ? { token } : {};
}

export const learningPathService = {
  /**
   * The whole path in one read: ordered stages, per-stage progress, the weak
   * topics, and the single recommended next problem with its reason.
   *
   * One request rather than a "summary" and a "detail" pair, because the
   * dashboard and the path page are two views of one computation and splitting
   * them would let them disagree.
   */
  path() {
    return apiClient.get("/learning-path", authOptions());
  },
};
