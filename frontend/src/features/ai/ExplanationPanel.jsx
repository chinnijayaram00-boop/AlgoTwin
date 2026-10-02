import { BookOpen, Sparkles } from "lucide-react";
import { useCallback } from "react";

import InsightBody from "./InsightBody";
import { aiService } from "./aiService";
import { aiUnavailableMessage, useAiInsight, useAiStatus } from "./aiInsight";

/**
 * The problem's intended approach, generated from the catalog's own record.
 *
 * Shown alongside the workspace rather than instead of it. The catalog ships a
 * written editorial and this generates a second explanation grounded in the same
 * facts, so the two are presented as distinct acts -- the editorial is stored
 * platform copy, this is generated text with an attributed model. A learner who
 * prefers one is not obliged to use the other, and nothing here implies the
 * generated text was reviewed by anyone.
 *
 * The panel offers two focuses because the prompt does: `approach` and
 * `correctness`. Both come from the catalog's record; neither can introduce
 * anything, and the server resolves both rather than accepting prose.
 *
 * Nothing is requested until the learner presses the button. The backend caches by
 * prompt digest and charges a rate limit only on a real generation, so a panel
 * that fired on mount would spend a budget nobody chose to spend.
 */
export default function ExplanationPanel({ problemId, enabled = true }) {
  const { status: aiStatus, configured, loading: statusLoading } = useAiStatus({ enabled });
  const request = useCallback(
    () => (problemId ? aiService.explanation(problemId) : Promise.resolve(null)),
    [problemId],
  );
  const insight = useAiInsight(request, { enabled: enabled && configured, requestKey: String(problemId ?? "") });

  if (!problemId) return null;

  if (statusLoading) {
    return (
      <div className="ai-insight-state" role="status">
        <span className="spinner" />
        <span>Checking whether AI is available.</span>
      </div>
    );
  }

  if (!configured) {
    return (
      <div className="ai-panel-unavailable" role="status">
        <Sparkles aria-hidden="true" size={15} /> {aiUnavailableMessage(aiStatus, null)}
      </div>
    );
  }

  return (
    <div className="ai-panel">
      <div className="ai-panel-actions">
        <button
          className="button button-secondary"
          disabled={insight.status === "loading"}
          onClick={() => insight.generate()}
          type="button"
        >
          <BookOpen aria-hidden="true" size={15} />
          {insight.status === "loading" ? "Generating" : "Explain this approach"}
        </button>
        {/*
          The second press asks for the other focus. It is a *different request*
          to the backend, not a regeneration: the cache is keyed by prompt, so it
          answers with new text rather than the first answer again.
        */}
        <button
          className="button button-quiet"
          disabled={insight.status === "loading"}
          onClick={() =>
            insight.generate(() => aiService.explanation(problemId, { focus: "correctness" }))
          }
          type="button"
        >
          Explain the correctness argument
        </button>
      </div>

      {/*
        The API's generated text and the catalog's editorial never share a
        container. They are different acts by different authors, and mixing them
        would make it impossible to tell which is which.
      */}
      <InsightBody
        error={insight.actionError}
        errorStatus={insight.errorStatus}
        insight={insight.insight}
        loading={insight.status === "loading"}
        onRetry={() => insight.generate()}
      />
    </div>
  );
}