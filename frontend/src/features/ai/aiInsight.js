import { useCallback, useState } from "react";

import { useApiResource } from "../../hooks/useApiResource";
import { aiService } from "./aiService";

/**
 * One grounded AI insight, and the action that asks for it.
 *
 * Deliberately not `useApiResource`, for the same reason `useCodeRun` is not: a
 * generation is an action, not a resource. Nothing is fetched on mount, because
 * generating costs a provider call and the learner's rate-limit budget. The first
 * insight arrives when they press the button, so `insight` starts `null` rather
 * than as a placeholder -- the panel has to be able to say "not asked yet", and an
 * empty object shaped like a result would be a claim about something that was
 * never generated.
 *
 * The status is `idle`, `loading`, `success`, or `error`, and they are mutually
 * exclusive by construction rather than by three independent booleans that can
 * contradict each other. A panel driven by booleans eventually renders a spinner
 * and an error at once; this cannot, because there is only one of them.
 *
 * `actionError` is kept separate from a failed *load* for the same reason
 * `useCodeRun` does: a generation that failed did not invalidate a previous
 * successful insight, and wiping that text on a transient 502 would destroy the one
 * thing the learner came for.
 *
 * `generate` takes an optional request to use instead of the hook's own. That is
 * how a panel offers a second question about the same subject without a second
 * hook: the backend keys its cache by prompt, so asking differently produces
 * different text rather than the same answer again.
 *
 * `requestKey` identifies what is being asked about -- a problem id, a submission
 * id, the current source. When it changes, the hook resets. Without that, moving
 * from one problem to another would leave the previous problem's explanation
 * sitting next to the new problem's statement, which is the same class of mistake
 * as showing a previous run's verdict next to code that did not produce it.
 */
export function useAiInsight(request, { enabled = true, requestKey = "" } = {}) {
  const [status, setStatus] = useState("idle");
  const [insight, setInsight] = useState(null);
  const [actionError, setActionError] = useState("");
  const [errorStatus, setErrorStatus] = useState(null);
  const [key, setKey] = useState(requestKey);

  // Resets are driven by rendering rather than by an effect so a change of key
  // and the render that observes it cannot be separated by a paint. The guard is
  // what stops this from clearing on every render.
  if (key !== requestKey) {
    setKey(requestKey);
    setStatus("idle");
    setInsight(null);
    setActionError("");
    setErrorStatus(null);
  }

  const generate = useCallback(async (overrideRequest) => {
    if (!enabled || (!request && !overrideRequest)) return null;
    setStatus("loading");
    setActionError("");
    setErrorStatus(null);
    try {
      const response = await (overrideRequest ? overrideRequest() : request());
      setInsight(response);
      setStatus("success");
      return response;
    } catch (generationFailure) {
      setActionError(generationFailure.message);
      setErrorStatus(generationFailure.status ?? null);
      setStatus("error");
      return null;
    }
  }, [enabled, request]);

  const reset = useCallback(() => {
    setStatus("idle");
    setInsight(null);
    setActionError("");
    setErrorStatus(null);
  }, []);

  return { status, insight, actionError, errorStatus, generate, reset };
}

/**
 * Whether this deployment can generate anything.
 *
 * A read, so it goes through `useApiResource` like every other read. The point of
 * asking is to avoid offering a button whose only possible answer is a 503, and to
 * be able to say *why* -- "AI is disabled on this deployment" is actionable,
 * whereas a disabled button with no explanation is not.
 *
 * A failure to read the status is not a reason to hide the panels. The status
 * endpoint is public and cheap; if it is unreachable the API is not, and the
 * panels can say so themselves. `error` is therefore returned rather than thrown,
 * and callers decide.
 */
export function useAiStatus({ enabled = true } = {}) {
  const load = useCallback(() => (enabled ? aiService.status() : Promise.resolve(null)), [enabled]);
  const { data, error, loading, reload } = useApiResource(load);
  const configured = data?.configured === true;
  return { status: data, configured, loading, error, reload };
}

/**
 * The status endpoint's own explanation, or a generic one if it could not be read.
 */
export function aiUnavailableMessage(status, error) {
  if (error) return "The AI status could not be read. Generation may still be unavailable.";
  if (status?.message) return status.message;
  return "AI is not available on this deployment.";
}