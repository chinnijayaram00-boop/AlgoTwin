import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "../auth/authStorage";
import { AI_TIMEOUT_MS } from "../ai/aiService";

/**
 * Calls for the personalized coach.
 *
 * Two reads and one action. The profile is a pure read; the mentor call is an
 * action that may cost a provider call, so it is not fetched on mount.
 *
 * There is deliberately no `userId` argument anywhere: the API identifies the
 * learner from the bearer token alone, so the client cannot ask the coach about
 * somebody else even by accident. The mentor request body carries at most a
 * `focus` label -- the facts behind the advice always come from the server's own
 * record of this learner, never from the caller.
 */
function authOptions(timeoutMs) {
  const token = getStoredToken();
  const wait = timeoutMs ? { timeoutMs } : {};
  return token ? { token, ...wait } : wait;
}

export const personalizationService = {
  /**
   * The learner's profile: headline numbers, explainable strengths and
   * weaknesses, next-step recommendations, and focus areas.
   *
   * Assembled from the same computations the analytics and learning-path pages
   * run, so this panel can never disagree with them about a count or about what
   * comes next.
   */
  profile() {
    return apiClient.get("/personalization/profile", authOptions());
  },

  /**
   * Grounded coaching for the learner, centring on `focus`.
   *
   * The endpoint always answers: when no model is available, or the learner is
   * over their budget, or the provider fails, the response carries deterministic
   * text and a `fallback` flag rather than an error. `focus` is a preference
   * drawn from a closed set, so it selects an emphasis and cannot add content.
   *
   * A generation may take as long as a model call, so it waits longer than the
   * default, below the server's own budget so the server gives up first.
   */
  mentor(focus) {
    const body = focus ? { focus } : {};
    return apiClient.post("/personalization/mentor", body, authOptions(AI_TIMEOUT_MS));
  },
};

export default personalizationService;
