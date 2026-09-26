import { CheckCheck, Gauge, History, Info, Pencil, RotateCcw } from "lucide-react";

import { ErrorState, LoadingState } from "../../components/ui/Feedback";
import ProgressStatusPill from "./ProgressStatusPill";
import { formatDuration, formatTimestamp, statusDescription } from "./progressStatus";
import { useProblemProgress } from "./useProgress";

/**
 * One problem's progress record, with the actions that change it.
 *
 * Everything here is self-reported: the learner marks what they actually did.
 * Nothing is graded, inferred, or sent anywhere, and the panel says so, because
 * a status that looks like a verdict would misrepresent what is stored.
 */
export default function ProblemProgressPanel({ problemId, enabled = true }) {
  const { data, error, errorStatus, loading, reload, saving, actionError, setStatus, recordAttempt } =
    useProblemProgress(problemId, { enabled });

  if (loading) {
    return <LoadingState label="Loading your progress for this problem" />;
  }

  if (error) {
    return errorStatus === 401 ? (
      <div className="inline-notice" role="alert">
        Sign in again to load your progress. Your session may have expired.
      </div>
    ) : (
      <ErrorState message={error} onRetry={reload} />
    );
  }

  if (!data) {
    return (
      <div className="inline-notice">
        <Info size={15} /> Progress for this problem could not be loaded.
      </div>
    );
  }

  return (
    <div className="problem-progress">
      <div className="problem-progress-head">
        <ProgressStatusPill showIcon status={data.status} />
        <span className="problem-progress-status-note">{statusDescription(data.status)}</span>
      </div>

      <dl className="problem-progress-facts">
        <div>
          <dt>
            <History size={14} /> Attempts
          </dt>
          <dd>{data.attempts_count || 0}</dd>
        </div>
        <div>
          <dt>
            <Pencil size={14} /> Last attempted
          </dt>
          <dd>{formatTimestamp(data.last_attempted_at)}</dd>
        </div>
        <div>
          <dt>Solved</dt>
          <dd>{formatTimestamp(data.solved_at)}</dd>
        </div>
        <div>
          <dt>
            <Gauge size={14} /> Best runtime
          </dt>
          <dd>{formatDuration(data.best_runtime_ms)}</dd>
        </div>
      </dl>

      <div className="problem-progress-actions">
        <button
          className="button button-secondary"
          disabled={saving}
          onClick={() => recordAttempt()}
          type="button"
        >
          <History size={15} /> I attempted this
        </button>
        <button
          className="button button-primary"
          disabled={saving || data.status === "solved"}
          onClick={() => setStatus("solved")}
          type="button"
        >
          <CheckCheck size={15} /> Mark as solved
        </button>
        <button
          className="button button-quiet"
          disabled={saving || data.status === "not_started"}
          onClick={() => setStatus("not_started")}
          type="button"
        >
          <RotateCcw size={15} /> Reset
        </button>
      </div>

      {saving ? <span className="problem-progress-saving">Saving your progress…</span> : null}
      {actionError ? (
        <div className="inline-notice" role="alert">
          {actionError}
        </div>
      ) : null}

      <p className="problem-progress-disclaimer">
        <Info size={14} /> Recorded by you, not verified by a judge. No code is run or stored here.
      </p>
    </div>
  );
}
