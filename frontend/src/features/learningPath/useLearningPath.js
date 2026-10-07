import { useCallback } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { learningPathService } from "./learningPathService";

/**
 * The learner's ordered stages and next recommendation.
 *
 * `enabled` is false only while the session is still being restored; the caller
 * renders a loading state in that window rather than firing a request that
 * could only come back 401.
 */
export function useLearningPath({ enabled = true } = {}) {
  const load = useCallback(() => learningPathService.path(), []);
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  return useApiResource(request);
}
