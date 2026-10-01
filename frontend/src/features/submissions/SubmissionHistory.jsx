import { ChevronLeft, ChevronRight, Filter, Info } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "../../components/ui/Feedback";
import SubmissionList from "./SubmissionList";
import { DEFAULT_PAGE_SIZE, useSubmissionList } from "./useSubmissions";
import {
  JUDGE_NOTE,
  SUBMISSION_STATUSES,
  SUPPORTED_LANGUAGES,
  languageLabel,
  statusLabel,
} from "./submissionStatus";

/**
 * The learner's account-wide submission history, newest first.
 *
 * The list, the filters, and the count all come from one request, so a filtered
 * view and its total can never disagree. Both filters narrow the same request
 * and a change to either returns to page one -- a filter change can invalidate
 * the current page, and landing on page 7 of a newly narrowed set looks like
 * "no results" rather than like a filter.
 *
 * Every status is offered as a filter, because every status is reachable now.
 */
export default function SubmissionHistory({
  onSelect,
  selectedId = null,
  enabled = true,
  pageSize = DEFAULT_PAGE_SIZE,
  refreshKey = 0,
}) {
  const [language, setLanguage] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, errorStatus, loading, reload } = useSubmissionList(
    {
      language: language || undefined,
      status: status || undefined,
      page,
      pageSize,
    },
    { enabled, refreshKey },
  );

  function chooseLanguage(next) {
    setLanguage(next);
    setPage(1);
  }

  function chooseStatus(next) {
    setStatus(next);
    setPage(1);
  }

  function clearFilters() {
    setLanguage("");
    setStatus("");
    setPage(1);
  }

  const items = data?.items || [];
  const total = data?.total || 0;
  const totalPages = data?.total_pages || 0;
  const filtering = Boolean(language || status);

  return (
    <div className="submission-history">
      <div className="submission-history-toolbar">
        <div aria-label="Filter by language" className="filter-group" role="group">
          <Filter size={15} />
          <button
            className={`filter-button${language === "" ? " selected" : ""}`}
            onClick={() => chooseLanguage("")}
            type="button"
          >
            All languages
          </button>
          {SUPPORTED_LANGUAGES.map((option) => (
            <button
              className={`filter-button${language === option ? " selected" : ""}`}
              key={option}
              onClick={() => chooseLanguage(option)}
              type="button"
            >
              {languageLabel(option)}
            </button>
          ))}
        </div>
        <div aria-label="Filter by verdict" className="filter-group" role="group">
          <Filter size={15} />
          <button
            className={`filter-button${status === "" ? " selected" : ""}`}
            onClick={() => chooseStatus("")}
            type="button"
          >
            All verdicts
          </button>
          {SUBMISSION_STATUSES.map((option) => (
            <button
              className={`filter-button${status === option ? " selected" : ""}`}
              key={option}
              onClick={() => chooseStatus(option)}
              type="button"
            >
              {statusLabel(option)}
            </button>
          ))}
        </div>
        <span className="submission-history-total">
          {loading ? "Reading your history…" : `${total} submitted`}
        </span>
      </div>

      {loading ? <LoadingState label="Loading your submission history" /> : null}

      {error ? (
        errorStatus === 401 ? (
          <div className="inline-notice" role="alert">
            Sign in again to load your submissions. Your session may have expired.
          </div>
        ) : (
          <ErrorState message={error} onRetry={reload} />
        )
      ) : null}

      {!loading && !error && !data ? (
        <div className="inline-notice">
          <Info size={15} /> Your submission history could not be loaded.
        </div>
      ) : null}

      {!loading && !error && data && items.length ? (
        <>
          <SubmissionList items={items} onSelect={onSelect} selectedId={selectedId} />
          {totalPages > 1 ? (
            <div className="submission-pagination">
              <button
                className="button button-quiet"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(current - 1, 1))}
                type="button"
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <span>
                Page {data.page} of {totalPages}
              </span>
              <button
                className="button button-quiet"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(current + 1, totalPages))}
                type="button"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          ) : null}
        </>
      ) : null}

      {!loading && !error && data && !items.length ? (
        <EmptyState
          action={
            filtering ? (
              <button className="button button-secondary" onClick={clearFilters} type="button">
                Clear the filters
              </button>
            ) : null
          }
          description={
            filtering
              ? "No submission matches this filter yet."
              : "Open a problem, write some code, and submit it to be judged."
          }
          title={filtering ? "No submissions match" : "No submissions yet"}
        />
      ) : null}

      <p className="submission-disclaimer">
        <Info aria-hidden="true" size={14} /> {JUDGE_NOTE}
      </p>
    </div>
  );
}
