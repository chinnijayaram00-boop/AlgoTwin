import { useState } from "react";

import { EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ui/Feedback";
import { ActivityChart, DifficultyChart, TopicChart, VerdictChart } from "../features/analytics/AnalyticsCharts";
import AnalyticsOverview from "../features/analytics/AnalyticsOverview";
import { activeTopics } from "../features/analytics/analyticsFormat";
import InterviewPanel from "../features/analytics/InterviewPanel";
import PathSnapshot from "../features/analytics/PathSnapshot";
import { useAnalytics } from "../features/analytics/useAnalytics";

const WINDOW_OPTIONS = [7, 30, 90];

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data, error, errorStatus, loading, reload } = useAnalytics({ days });

  return (
    <div className="page-stack">
      <PageHeader
        description="Overview, breakdowns, activity, curriculum position, and interview performance — every number computed from your own recorded work."
        eyebrow="Learning intelligence"
        title="Notice the shape of your progress."
      />
      {loading ? <LoadingState label="Loading learning signals" /> : null}
      {errorStatus === 401 ? (
        <div className="inline-notice" role="alert">
          Sign in again to load your analytics. Your session may have expired.
        </div>
      ) : null}
      {error && errorStatus !== 401 ? <ErrorState message={error} onRetry={reload} /> : null}
      {data ? <AnalyticsView data={data} days={days} onDaysChange={setDays} /> : null}
    </div>
  );
}

function AnalyticsView({ data, days, onDaysChange }) {
  const {
    activity,
    activity_days: activityDays,
    difficulty,
    interviews,
    learning_path: path,
    overview,
    topics,
    verdicts,
  } = data;
  const topicRows = activeTopics(topics);
  const hasCatalog = difficulty.some((row) => row.total > 0);
  const hasVerdicts = verdicts.length > 0;
  const hasActivity = activity.some(
    (day) => day.submissions > 0 || day.attempts > 0 || day.solves > 0,
  );

  return (
    <>
      <AnalyticsOverview interviews={interviews} overview={overview} />

      <div className="analytics-grid">
        <SectionCard
          description="Catalog standing per tier: solved, attempted, and untouched, with the submissions behind each bar."
          title="Mastery by difficulty"
        >
          {hasCatalog ? (
            <DifficultyChart rows={difficulty} />
          ) : (
            <EmptyState
              description="Publish problems to unlock the difficulty breakdown."
              title="No catalog to compare against"
            />
          )}
        </SectionCard>

        <SectionCard
          description={
            topicRows.length
              ? `The ${topicRows.length} topics you have touched, most solved first.`
              : "The topics you have touched show up here, most solved first."
          }
          title="Topic coverage"
        >
          {topicRows.length ? (
            <TopicChart rows={topicRows} />
          ) : (
            <EmptyState
              description="Solve or attempt a problem and its topics will appear here."
              title="No topic activity yet"
            />
          )}
        </SectionCard>
      </div>

      <div className="analytics-grid">
        <SectionCard
          description={`${overview.total_submissions} submission${
            overview.total_submissions === 1 ? "" : "s"
          } to the judge, by verdict.`}
          title="Submission verdicts"
        >
          {hasVerdicts ? (
            <VerdictChart rows={verdicts} />
          ) : (
            <EmptyState
              description="Send code to the judge to start building your verdict distribution."
              title="No submissions yet"
            />
          )}
        </SectionCard>

        <SectionCard
          description={`Submissions and solves per day across the last ${activityDays} days.`}
          title="Activity"
        >
          <div
            aria-label="Activity window"
            className="window-picker"
            role="group"
          >
            {WINDOW_OPTIONS.map((option) => (
              <button
                aria-pressed={option === days}
                className={`button ${option === days ? "button-primary" : "button-quiet"}`}
                key={option}
                onClick={() => onDaysChange(option)}
                type="button"
              >
                {option} days
              </button>
            ))}
          </div>
          {hasActivity ? (
            <ActivityChart days={activity} />
          ) : (
            <EmptyState
              description="Attempt a problem or submit code to start the series."
              title="No activity in this window"
            />
          )}
        </SectionCard>
      </div>

      <div className="analytics-grid">
        <SectionCard
          description="Stages, weak topics, and the next recommendation — the same computation the learning path page runs."
          title="Learning path position"
        >
          <PathSnapshot path={path} />
        </SectionCard>
        <SectionCard
          description="Scores from completed sessions, and question acceptance over answered questions."
          title="Mock interview performance"
        >
          <InterviewPanel interviews={interviews} />
        </SectionCard>
      </div>
    </>
  );
}