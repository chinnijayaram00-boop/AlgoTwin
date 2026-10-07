import { useCallback } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { analyticsService } from "./analyticsService";

/**
 * The learner's analytics summary.
 *
 * `days` selects the activity window (7–90 days); leaving it out asks the
 * server for its default. `enabled` exists so a caller can hold the request
 * until it has something to authenticate with, instead of firing a request
 * that could only come back 401.
 */
export function useAnalytics({ days, enabled = true } = {}) {
  const load = useCallback(() => analyticsService.summary({ days }), [days]);
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  return useApiResource(request);
}
