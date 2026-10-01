import { useEffect, useRef } from "react";

/**
 * Refetch `reload` exactly once whenever `refreshKey` changes.
 *
 * Several parts of the platform are written by an action that happens somewhere
 * else: submitting a problem updates the learner's progress and their history
 * server-side, so a panel that has not been told cannot know. Rather than have
 * every one of those panels grow its own effect, the caller passes a counter
 * and this does the rest.
 *
 * The last key is tracked rather than the effect reacting to `reload` directly,
 * because `reload` changes identity on every render in most callers. Comparing
 * keys is also what keeps this from fetching twice when something else -- a new
 * problem id, say -- changes the request in the same commit as the key.
 *
 * Only ever causes an extra read, so a caller that never bumps the key behaves
 * exactly as if this did not exist.
 */
export function useRefreshKey(refreshKey, reload) {
  const lastRefreshKey = useRef(refreshKey);

  useEffect(() => {
    if (lastRefreshKey.current === refreshKey) {
      return;
    }
    lastRefreshKey.current = refreshKey;
    reload();
  }, [refreshKey, reload]);
}