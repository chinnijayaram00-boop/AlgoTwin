import { Info, Sparkles, Stethoscope } from "lucide-react";
import { useCallback } from "react";

import InsightBody from "./InsightBody";
import { aiService } from "./aiService";
import { aiUnavailableMessage, useAiInsight, useAiStatus } from "./aiInsight";

/**
 * A diagnosis of one recorded submission.
 *
 * The grounding here is worth being explicit about, because it is narrower than a
 * learner might assume. The API sends the stored verdict and the judge's
 * measurements -- passed and total case counts, runtime, memory, and the judge's
 * own error message -- and nothing else. It does **not** send the learner's
 * source, and it cannot send a test case, because a judged submission stores counts
 * rather than cases and the hidden suite is not readable through any route.
 *
 * That is why the notice below is part of the panel rather than a footnote. A
 * learner reading "you failed 3 of 12 cases" and expecting the diagnosis to name
 * the failing input would be right to be disappointed; saying so up front is better
 * than letting them conclude the model guessed.
 *
 * A submission that has never been judged is still diagnosable, and the answer
 * says the verdict was never recorded rather than inventing one.
 */
export default function DiagnosisPanel({ submissionId, status, enabled = true }) {
  const { status: aiStatus, configured, loading: statusLoading } = useAiStatus({ enabled });
  const request = useCallback(
    () => (submissionId ? aiService.diagnosis(submissionId) : Promise.resolve(null)),
    [submissionId],
  );
  const insight = useAiInsight(request, {
    enabled: enabled && configured,
    requestKey: String(submissionId ?? ""),
  });

  if (!submissionId) return null;

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
    <div className="ai-panel ai-diagnosis-panel">
      <button
        className="button button-secondary"
        disabled={insight.status === "loading"}
        onClick={() => insight.generate()}
        title={
          status
            ? `Diagnose this ${status} result.`
            : "Diagnose this submission, which has no recorded verdict."
        }
        type="button"
      >
        <Stethoscope aria-hidden="true" size={15} />
        {insight.status === "loading" ? "Diagnosing" : "Diagnose this result"}
      </button>

      <InsightBody
        error={insight.actionError}
        errorStatus={insight.errorStatus}
        insight={insight.insight}
        loading={insight.status === "loading"}
        onRetry={() => insight.generate()}
      />

      <p className="ai-grounding-note">
        <Info aria-hidden="true" size={14} /> A diagnosis is grounded in the stored verdict and the
        measurements the judge took. Hidden test cases, expected outputs, and your source code are
        never sent.
      </p>
    </div>
  );
}