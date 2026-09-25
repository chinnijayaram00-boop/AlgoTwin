import { Filter, Search, SlidersHorizontal } from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import ProblemCard from "../features/problems/ProblemCard";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusPill } from "../components/ui/Feedback";
import { useApiResource } from "../hooks/useApiResource";
import { problemApi } from "../services/platformService";

const difficulties = ["All", "Easy", "Medium", "Hard"];

export default function ProblemsPage() {
  const [searchParams] = useSearchParams();
  const initialDifficulty = searchParams.get("difficulty") || "All";
  const [difficulty, setDifficulty] = useState(
    difficulties.includes(initialDifficulty) ? initialDifficulty : "All",
  );
  const [query, setQuery] = useState("");
  const loadProblems = useCallback(
    () => problemApi.list({ difficulty: difficulty === "All" ? undefined : difficulty, limit: 50 }),
    [difficulty],
  );
  const { data, error, loading, reload } = useApiResource(loadProblems);
  const problems = (data?.items || []).filter((problem) => {
    const searchValue = query.trim().toLowerCase();
    if (!searchValue) return true;
    return `${problem.title} ${problem.summary} ${problem.topics.join(" ")}`.toLowerCase().includes(searchValue);
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
          <input onChange={(event) => setQuery(event.target.value)} placeholder="Filter by title, pattern, or topic" value={query} />
        </label>
        <div className="filter-group" role="group" aria-label="Filter by difficulty">
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
            <StatusPill tone="neutral">{difficulty === "All" ? "All levels" : difficulty}</StatusPill>
          </div>
          {problems.length ? (
            <div className="problem-grid">
              {problems.map((problem) => <ProblemCard key={problem.id} problem={problem} />)}
            </div>
          ) : (
            <EmptyState description="Try a different difficulty or clear the search filter." title="No matching problems" />
          )}
        </>
      ) : null}
    </div>
  );
}
