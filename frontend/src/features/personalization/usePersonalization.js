import { useCallback } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { personalizationService } from "./personalizationService";

/**
 * The learner's personalized profile.
 *
 * A read, so it goes through `useApiResource` like every other read. `enabled`
 * exists so a caller can hold the request until it has something to
 * authenticate with, instead of firing a request that could only come back 401.
 */
export function usePersonalization({ enabled = true } = {}) {
  const load = useCallback(() => personalizationService.profile(), []);
  const request = useCallback(() => (enabled ? load() : Promise.resolve(null)), [enabled, load]);
  return useApiResource(request);
}
