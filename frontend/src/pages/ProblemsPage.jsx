import { Filter, Search, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import ProblemCard from "../features/problems/ProblemCard";
import ProgressStatusPill from "../features/progress/ProgressStatusPill";
import { useProgressList } from "../features/progress/useProgress";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusPill } from "../components/ui/Feedback";

const difficulties = ["All", "Easy", "Medium", "Hard"];
const statusFilters = [
  { id: "all", label: "All" },
  { id: "not_started", label: "Not Started" },
  { id: "attempted", label: "Attempted" },
  { id: "solved", label: "Solved" },
];

function initialSelection(values, allowed, fallback) {
  const requested = values.get("status");
  return allowed.includes(requested) ? requested : fallback;
}

/**
 * The practice library, annotated with this learner's own progress.
 *
 * Status and difficulty filtering happens server-side through the same
 * endpoint that supplies the list, so a filtered view and its count always
 * come from one consistent snapshot. The free-text filter stays client-side
 * because it only narrows an already-fetched page.
 */
export default function ProblemsPage() {
  const [searchParams] = useSearchParams();
  const [difficulty, setDifficulty] = useState(
    initialSelection(searchParams, difficulties, "All"),
  );
  const [status, setStatus] = useState(
    initialSelection(
      searchParams,
      statusFilters.map((option) => option.id),
      "all",
    ),
  );
  const [query, setQuery] = useState("");

  const { data, error, loading, reload } = useProgressList({
    status: status === "all" ? undefined : status,
    difficulty: difficulty === "All" ? undefined : difficulty,
  });

  const problems = (data?.items || []).filter((problem) => {
    const searchValue = query.trim().toLowerCase();
    if (!searchValue) return true;
    return `${problem.title} ${problem.difficulty} ${problem.topics.join(" ")}`
      .toLowerCase()
      .includes(searchValue);
  });

  return (
    <div className="page-stack">
      <PageHeader
        description="Start with a focused pattern, then build a repeatable solution habit."
        eyebrow="Practice library"
        title="Problems that compound."
        action={
          <Link className="button button-secondary" to="/visualizer">
            Open visualizer <SlidersHorizontal size={16} />
          </Link>
        }
      />

      <div className="toolbar">
        <label className="library-search">
          <Search size={17} />
          <span className="sr-only">Filter problems</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by title, pattern, or topic"
            value={query}
          />
        </label>
        <div aria-label="Filter by difficulty" className="filter-group" role="group">
          <Filter size={15} />
          {difficulties.map((option) => (
            <button
              className={`filter-button${difficulty === option ? " selected" : ""}`}
              key={option}
              onClick={() => setDifficulty(option)}
              type="button"
            >
              {option}
            </button>
          ))}
        </div>
        <div aria-label="Filter by your progress" className="filter-group" role="group">
          <Filter size={15} />
          {statusFilters.map((option) => (
            <button
              className={`filter-button${status === option.id ? " selected" : ""}`}
              key={option.id}
              onClick={() => setStatus(option.id)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? <LoadingState label="Loading published problems" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {!loading && !error ? (
        <>
          <div className="results-heading">
            <div>
              <span className="eyebrow">Published catalog</span>
              <h3>{data?.total ?? 0} problems</h3>
            </div>
            <div className="results-heading-pills">
              <StatusPill tone="neutral">{difficulty === "All" ? "All levels" : difficulty}</StatusPill>
              {status === "all" ? null : <ProgressStatusPill status={status} />}
            </div>
          </div>
          {problems.length ? (
            <div className="problem-grid">
              {problems.map((problem) => (
                <ProblemCard key={problem.problem_id} problem={problem} />
              ))}
            </div>
          ) : (
            <EmptyState
              description={
                query
                  ? "Try a different search term, or clear the filters."
                  : "No problem in the catalog matches these filters yet."
              }
              title="No matching problems"
            />
          )}
        </>
      ) : null}
    </div>
  );
}
