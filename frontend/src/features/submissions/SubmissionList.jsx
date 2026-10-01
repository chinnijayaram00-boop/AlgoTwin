import { Code2 } from "lucide-react";

import SubmissionStatusPill from "./SubmissionStatusPill";
import { formatCaseCounts, formatSubmittedAt, languageLabel } from "./submissionStatus";

/**
 * A read-only list of judged submissions.
 *
 * Presentational on purpose: the account-wide history and the per-problem
 * preview render the same row, and neither should own a request. A row shows
 * only what the API holds for one attempt -- which problem, in which language,
 * submitted when, and the verdict the judge reported with its pass count.
 *
 * A row stays free of the source, for the same reason the list response omits
 * it: twenty rows should not carry twenty code bodies, and opening one is what
 * earns the code.
 *
 * `onSelect` is optional: with it, each row becomes a button the learner can
 * open; without it, the rows are static, which is what the compact workspace
 * preview wants.
 */
export default function SubmissionList({ items = [], selectedId = null, onSelect, emptyLabel }) {
  if (!items.length) {
    return <p className="submission-list-empty">{emptyLabel || "No submissions yet."}</p>;
  }

  return (
    <ul className="submission-list">
      {items.map((submission) => {
        const isSelected = selectedId !== null && String(selectedId) === String(submission.id);
        const cases = formatCaseCounts(submission);
        const body = (
          <>
            <span className="submission-row-main">
              <strong>{submission.problem_title || submission.problem_slug}</strong>
              <span className="submission-row-meta">
                <Code2 aria-hidden="true" size={12} /> {languageLabel(submission.language)}
                <span aria-hidden="true">·</span>
                {formatSubmittedAt(submission.submitted_at)}
                {/* Only shown when the judge reported counts; a row never
                    implies a measurement that was not taken. */}
                {cases ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="submission-row-cases">{cases}</span>
                  </>
                ) : null}
              </span>
            </span>
            <SubmissionStatusPill showIcon status={submission.status} />
          </>
        );

        return (
          <li key={submission.id}>
            {onSelect ? (
              <button
                aria-current={isSelected ? "true" : undefined}
                className={`submission-row${isSelected ? " selected" : ""}`}
                onClick={() => onSelect(submission.id)}
                type="button"
              >
                {body}
              </button>
            ) : (
              <div className="submission-row">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
