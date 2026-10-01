import { ArrowRight, Gavel, Info } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState } from "../../components/ui/Feedback";
import SubmissionList from "./SubmissionList";
import SubmissionStatusPill from "./SubmissionStatusPill";
import {
  JUDGE_NOTE,
  formatCaseCounts,
  formatMemory,
  formatRuntime,
  isJudgedStatus,
  languageLabel,
  statusDescription,
} from "./submissionStatus";

/**
 * The learner's judged attempts on the problem currently open in the editor.
 *
 * Presentational, like `ProgressPanel`: `WorkspacePage` owns
 * `useProblemSubmissions` so the editor footer's submit button and this panel
 * read the same state, and a submit is reflected in one place without a second
 * request.
 *
 * The saved result is a verdict, not a receipt, so it is shown as one: the
 * status, the pass count, the runtime, and whatever the judge said went wrong.
 * A submission the judge never reached still reads "Stored, never judged" rather
 * than borrowing the meaning of a pass.
 */
export default function ProblemSubmissionPanel({
  data,
  error,
  errorStatus,
  loading,
  reload,
  saving,
  actionError,
  created,
}) {
  const cases = formatCaseCounts(created);
  const runtime = formatRuntime(created?.runtime_ms);
  const memory = formatMemory(created?.memory_mb);

  return (
    <div className="submission-recorder">
      {loading ? <LoadingState label="Loading your submissions for this problem" /> : null}

      {error ? (
        errorStatus === 401 ? (
          <div className="inline-notice" role="alert">
            Sign in again to load your submissions. Your session may have expired.
          </div>
        ) : (
          <ErrorState message={error} onRetry={reload} />
        )
      ) : null}

      {!loading && !error && data && data.total === 0 ? (
        <EmptyState
          description="Write a solution and submit it. It is run against every test case and graded."
          title="Nothing submitted for this problem"
        />
      ) : null}

      {!loading && !error && data && data.total > 0 ? (
        <>
          <div className="submission-recorder-head">
            <span className="submission-recorder-count">
              {data.total} attempt{data.total === 1 ? "" : "s"} submitted
            </span>
            <Link className="button button-quiet" to="/submissions">
              Full history <ArrowRight size={14} />
            </Link>
          </div>
          <SubmissionList emptyLabel="No submissions for this problem yet." items={data.items} />
        </>
      ) : null}

      {saving ? (
        <span className="problem-progress-saving">Running the judge on your submission…</span>
      ) : null}

      {created ? (
        <div className="submission-saved" role="status">
          <Gavel aria-hidden="true" size={15} />
          <span>
            Submission #{created.id} in {languageLabel(created.language)}.
          </span>
          <SubmissionStatusPill status={created.status} />
        </div>
      ) : null}

      {created && isJudgedStatus(created.status) ? (
        <dl className="submission-facts">
          <div>
            <dt>Verdict</dt>
            <dd>{statusDescription(created.status)}</dd>
          </div>
          {cases ? (
            <div>
              <dt>Test cases</dt>
              <dd>{cases}</dd>
            </div>
          ) : null}
          {runtime ? (
            <div>
              <dt>Runtime</dt>
              <dd>{runtime}</dd>
            </div>
          ) : null}
          {memory ? (
            <div>
              <dt>Peak memory</dt>
              <dd>{memory}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {created?.error_message ? (
        <p className="submission-error">{created.error_message}</p>
      ) : null}

      {actionError ? (
        <div className="inline-notice" role="alert">
          {actionError}
        </div>
      ) : null}

      <p className="submission-disclaimer">
        <Info aria-hidden="true" size={14} /> {JUDGE_NOTE}
      </p>
    </div>
  );
}
