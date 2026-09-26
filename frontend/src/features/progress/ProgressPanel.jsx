import { Flame, Layers3, Target } from "lucide-react";

import { EmptyState, ErrorState, LoadingState, SectionCard } from "../../components/ui/Feedback";
import { statusLabel } from "./progressStatus";

/**
 * The learner's progress on the dashboard.
 *
 * Reads one summary payload and renders every number from it, so the card and
 * the metrics above it can never disagree. The three segments are derived
 * rather than fetched separately: `not_started` is the remainder of the
 * catalog, which is exactly what the API reports.
 */
export default function ProgressPanel({ summary, loading, error, errorStatus, onRetry }) {
  if (loading) {
    return (
      <SectionCard description="Reading your stored progress." title="Your progress">
        <LoadingState label="Loading your progress" />
      </SectionCard>
    );
  }

  if (error) {
    return (
      <SectionCard description="Reading your stored progress." title="Your progress">
        {errorStatus === 401 ? (
          <div className="inline-notice" role="alert">
            Sign in again to load your progress. Your session may have expired.
          </div>
        ) : (
          <ErrorState message={error} onRetry={onRetry} />
        )}
      </SectionCard>
    );
  }

  if (!summary) {
    return (
      <SectionCard description="Reading your stored progress." title="Your progress">
        <EmptyState
          description="Sign in and open a problem to start building your record."
          title="No progress yet"
        />
      </SectionCard>
    );
  }

  const total = summary.total_problems || 0;
  if (total === 0) {
    return (
      <SectionCard description="Your standing across the published catalog." title="Your progress">
        <EmptyState
          description="Publish a problem and your progress will start filling in here."
          title="No problems to track"
        />
      </SectionCard>
    );
  }

  const solved = summary.solved || 0;
  const attempted = summary.attempted || 0;
  const notStarted = Math.max(summary.not_started || 0, 0);
  const segments = [
    { key: "solved", value: solved },
    { key: "attempted", value: attempted },
    { key: "not_started", value: notStarted },
  ];

  return (
    <SectionCard
      description="Your standing across the published catalog, scoped to this account."
      title="Your progress"
    >
      <div className="progress-headline">
        <div>
          <span className="eyebrow">Completion</span>
          <strong>{summary.completion_percentage}%</strong>
          <span className="progress-headline-detail">
            {solved} of {total} solved
          </span>
        </div>
        <div className="progress-streak" title="Consecutive days with recorded activity">
          <Flame aria-hidden="true" size={16} />
          <strong>{summary.current_streak_days}</strong>
          <span>day streak</span>
        </div>
      </div>

      <div
        aria-label={`${solved} solved, ${attempted} attempted, ${notStarted} not started`}
        className="progress-meter"
        role="img"
      >
        {segments.map((segment) =>
          segment.value > 0 ? (
            <span
              className={`progress-segment ${segment.key}`}
              key={segment.key}
              style={{ width: `${(segment.value / total) * 100}%` }}
            />
          ) : null,
        )}
      </div>

      <ul className="progress-legend">
        {segments.map((segment) => (
          <li key={segment.key}>
            <span className={`progress-dot ${segment.key}`} />
            {statusLabel(segment.key)}
            <strong>{segment.value}</strong>
          </li>
        ))}
      </ul>

      <div className="progress-breakdown">
        <Breakdown empty="No difficulty breakdown yet." icon={Target} rows={difficultyRows(summary)} title="By difficulty" />
        <Breakdown empty="No topic breakdown yet." icon={Layers3} rows={topicRows(summary)} title="By topic" />
      </div>
    </SectionCard>
  );
}

/** Solved-over-total per difficulty, skipping levels with nothing solved yet. */
function difficultyRows(summary) {
  const totalByDifficulty = summary.total_by_difficulty || {};
  const solvedByDifficulty = summary.solved_by_difficulty || {};
  return Object.keys(totalByDifficulty)
    .sort()
    .map((difficulty) => ({
      label: difficulty,
      solved: solvedByDifficulty[difficulty] || 0,
      total: totalByDifficulty[difficulty] || 0,
    }))
    .filter((row) => row.total > 0);
}

/** Solved-over-total per topic, ranked by how much the learner has covered. */
function topicRows(summary) {
  const totalByTopic = summary.total_by_topic || {};
  const solvedByTopic = summary.solved_by_topic || {};
  return Object.keys(totalByTopic)
    .map((topic) => ({
      label: topic,
      solved: solvedByTopic[topic] || 0,
      total: totalByTopic[topic] || 0,
    }))
    .filter((row) => row.total > 0)
    .sort((first, second) => second.solved - first.solved || second.total - first.total)
    .slice(0, 6);
}

function Breakdown({ title, icon: Icon, rows, empty }) {
  return (
    <div className="progress-breakdown-group">
      <span className="progress-breakdown-title">
        <Icon aria-hidden="true" size={14} /> {title}
      </span>
      {rows.length ? (
        <div className="progress-rows">
          {rows.map((row) => (
            <div className="progress-row" key={row.label}>
              <span>{row.label}</span>
              <span className="progress-row-track" aria-hidden="true">
                <span
                  className={row.solved > 0 ? "solved" : "zero"}
                  style={{ width: `${Math.min((row.solved / row.total) * 100, 100)}%` }}
                />
              </span>
              <strong>
                {row.solved}/{row.total}
              </strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="progress-breakdown-empty">{empty}</p>
      )}
    </div>
  );
}
