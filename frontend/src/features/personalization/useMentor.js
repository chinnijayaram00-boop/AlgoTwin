import { useCallback, useState } from "react";

import { personalizationService } from "./personalizationService";

/**
 * One mentor response, and the action that asks for it.
 *
 * Deliberately not `useApiResource`: asking the coach is an action, not a
 * resource. Nothing is generated on mount, because a generation may cost a
 * provider call and the learner's rate-limit budget -- the first response arrives
 * when they press the button, so `guidance` starts `null` rather than as a
 * placeholder shaped like a result.
 *
 * The status is `idle`, `loading`, `success`, or `error`, mutually exclusive by
 * construction rather than by independent booleans. A failed generation does not
 * discard a previous successful one: the backend treats asking for advice as a
 * request that always has an answer, so an error here means the platform itself
 * was unreachable, and wiping useful text would destroy the thing the learner
 * came for.
 */
export function useMentor({ enabled = true } = {}) {
  const [status, setStatus] = useState("idle");
  const [guidance, setGuidance] = useState(null);
  const [error, setError] = useState("");
  const [errorStatus, setErrorStatus] = useState(null);

  const generate = useCallback(
    async (focus) => {
      if (!enabled) return null;
      setStatus("loading");
      setError("");
      setErrorStatus(null);
      try {
        const response = await personalizationService.mentor(focus);
        setGuidance(response);
        setStatus("success");
        return response;
      } catch (failure) {
        setError(failure.message);
        setErrorStatus(failure.status ?? null);
        setStatus("error");
        return null;
      }
    },
    [enabled],
  );

  return { status, guidance, error, errorStatus, generate };
}
