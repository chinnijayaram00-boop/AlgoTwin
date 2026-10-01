import {
  ArrowUpRight,
  CheckCheck,
  Clock3,
  Code2,
  Cpu,
  Info,
  Search,
  Timer,
} from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState } from "../../components/ui/Feedback";
import SubmissionStatusPill from "./SubmissionStatusPill";
import { useSubmissionDetail } from "./useSubmissions";
import {
  JUDGE_NOTE,
  formatCaseCounts,
  formatMemory,
  formatRuntime,
  formatSubmittedAt,
  isJudgedStatus,
  languageLabel,
  statusDescription,
} from "./submissionStatus";

/**
 * One judged submission, with the learner's own source.
 *
 * This is the only submission view that shows `source_code`, mirroring the
 * API: a history row stays light, and opening one is what earns the code.
 *
 * A 404 is reported as "not in your history" rather than as a failure. That is
 * deliberate and not a cosmetic choice -- the API answers 404 both for a row
 * that does not exist and for one belonging to another learner, so anything
 * more specific here would either be wrong or would start leaking ownership
 * the backend deliberately hides.
 *
 * The judge's measurements are shown, because they are what the learner came
 * back for. What is not shown is any per-case detail: the API stores none, so
 * there is nothing to show, and the hidden suite stays unreadable from here.
 */
export default function SubmissionDetail({ submissionId, enabled = true }) {
  const { data, error, errorStatus, loading, reload } = useSubmissionDetail(submissionId, { enabled });

  if (!submissionId) {
    return (
      <EmptyState
        description="Pick a submission from your history to read the code you submitted."
        title="No submission selected"
      />
    );
  }

  if (loading) {
    return <LoadingState label="Loading this submission" />;
  }

  if (error) {
    if (errorStatus === 401) {
      return (
        <div className="inline-notice" role="alert">
          Sign in again to open this submission. Your session may have expired.
        </div>
      );
    }
    if (errorStatus === 404) {
      return (
        <div className="inline-notice" role="status">
          <Search size={15} /> This submission is not in your history. It may have been removed, or it
          may never have been yours to open.
        </div>
      );
    }
    return <ErrorState message={error} onRetry={reload} />;
  }

  if (!data) {
    return (
      <div className="inline-notice">
        <Info size={15} /> This submission could not be loaded.
      </div>
    );
  }

  const cases = formatCaseCounts(data);
  const runtime = formatRuntime(data.runtime_ms);
  const memory = formatMemory(data.memory_mb);

  return (
    <article className="submission-detail">
      <header className="submission-detail-head">
        <div>
          <span className="eyebrow">Submission #{data.id}</span>
          <h3>{data.problem_title || data.problem_slug}</h3>
        </div>
        <SubmissionStatusPill showIcon status={data.status} />
      </header>

      <dl className="submission-facts">
        <div>
          <dt>
            <Code2 size={14} /> Language
          </dt>
          <dd>{languageLabel(data.language)}</dd>
        </div>
        {cases ? (
          <div>
            <dt>
              <CheckCheck size={14} /> Test cases
            </dt>
            <dd>{cases}</dd>
          </div>
        ) : null}
        {runtime ? (
          <div>
            <dt>
              <Timer size={14} /> Runtime
            </dt>
            <dd>{runtime}</dd>
          </div>
        ) : null}
        {memory ? (
          <div>
            <dt>
              <Cpu size={14} /> Peak memory
            </dt>
            <dd>{memory}</dd>
          </div>
        ) : null}
        <div>
          <dt>
            <Clock3 size={14} /> Submitted
          </dt>
          <dd>{formatSubmittedAt(data.submitted_at)}</dd>
        </div>
        <div>
          <dt>Judged</dt>
          <dd>{isJudgedStatus(data.status) ? formatSubmittedAt(data.judged_at) : "Not judged"}</dd>
        </div>
      </dl>

      <div className="submission-detail-status">
        {/*
          The status pill already sits in the header, so this line explains the
          stored label instead of repeating it.
        */}
        <span>{statusDescription(data.status)}</span>
      </div>

      {data.error_message ? (
        <p className="submission-error">{data.error_message}</p>
      ) : null}

      <div className="submission-source">
        <span className="submission-source-label">Submitted source</span>
        <pre>
          <code>{data.source_code}</code>
        </pre>
      </div>

      <footer className="submission-detail-foot">
        <p className="submission-disclaimer">
          <Info aria-hidden="true" size={14} /> {JUDGE_NOTE}
        </p>
        {data.problem_slug ? (
          <Link className="button button-quiet" to={`/problems/${data.problem_slug}`}>
            Open the workspace <ArrowUpRight size={14} />
          </Link>
        ) : null}
      </footer>
    </article>
  );
}
