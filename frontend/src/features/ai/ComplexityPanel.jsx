import { Gauge, Sparkles } from "lucide-react";
import { useCallback } from "react";

import InsightBody from "./InsightBody";
import { aiService, isDeterminedComplexity } from "./aiService";
import { aiUnavailableMessage, useAiInsight, useAiStatus } from "./aiInsight";

/**
 * A time and space complexity for the source currently in the editor.
 *
 * Two things are deliberately *not* done here.
 *
 * **The analysis is never requested on mount.** Every generation costs a provider
 * call and a slice of the learner's rate-limit budget, and a request the learner
 * did not ask for is not one they should pay for.
 *
 * **The source is not sent implicitly.** The panel is given the language and the
 * current text and passes exactly those. The backend sends the snippet to a model
 * and stores nothing, so the guarantee that source is not retained is the
 * backend's to make and is asserted in `backend/tests/test_ai.py`; the client's
 * only part in it is to send what it says it sends.
 *
 * When `problemId` is given, the response also carries the catalog's recorded
 * target complexity. It is shown as the problem's own target and never as a
 * measurement, and the two are only compared when the analysis actually states a
 * complexity -- an "undetermined" answer is displayed as undetermined, because
 * presenting it beside a target would imply a comparison that was never made.
 */
export default function ComplexityPanel({ problemId, language, sourceCode, enabled = true }) {
  const { status: aiStatus, configured, loading: statusLoading } = useAiStatus({ enabled });
  const hasSource = typeof sourceCode === "string" && sourceCode.trim().length > 0;

  const request = useCallback(
    () =>
      hasSource
        ? aiService.complexity({ language, sourceCode, problemId })
        : Promise.resolve(null),
    [hasSource, language, problemId, sourceCode],
  );
  const insight = useAiInsight(request, {
    enabled: enabled && configured,
    // Keyed on the source, so editing the program clears a stale verdict instead
    // of leaving an analysis of the previous version on screen beside code that
    // was never analysed.
    requestKey: `${language}:${problemId ?? ""}:${sourceCode ?? ""}`,
  });

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
      <button
        className="button button-secondary"
        disabled={!hasSource || insight.status === "loading"}
        onClick={() => insight.generate()}
        title={hasSource ? "Analyse the code in the editor." : "Write some code first."}
        type="button"
      >
        <Gauge aria-hidden="true" size={15} />
        {insight.status === "loading" ? "Analysing" : "Analyse complexity"}
      </button>

      <InsightBody
        error={insight.actionError}
        errorStatus={insight.errorStatus}
        insight={insight.insight}
        loading={insight.status === "loading"}
        onRetry={() => insight.generate()}
      >
        {insight.insight ? (
          <dl className="ai-complexity-facts">
            <div>
              <dt>Time</dt>
              <dd>{complexityLabel(insight.insight.time_complexity)}</dd>
            </div>
            <div>
              <dt>Space</dt>
              <dd>{complexityLabel(insight.insight.space_complexity)}</dd>
            </div>
            {/*
              The target appears only when both sides of the comparison exist. A
              target beside an undetermined answer would imply the two were
              compared.
            */}
            {insight.insight.expected_time_complexity ? (
              <div>
                <dt>This problem's target time</dt>
                <dd>{insight.insight.expected_time_complexity}</dd>
              </div>
            ) : null}
            {insight.insight.expected_space_complexity ? (
              <div>
                <dt>This problem's target space</dt>
                <dd>{insight.insight.expected_space_complexity}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}
      </InsightBody>
    </div>
  );
}

function complexityLabel(value) {
  return isDeterminedComplexity(value) ? value : "Not determined";
}