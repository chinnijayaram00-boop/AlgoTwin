import { EmptyState } from "../../components/ui/Feedback";
import { InterviewScoreChart } from "./AnalyticsCharts";
import { formatPercent } from "./analyticsFormat";

/**
 * Mock-interview performance: session counts, stored scores, and how many
 * answered questions the judge accepted.
 *
 * Scores come from completed sessions only -- an abandoned session carries no
 * score by construction -- and acceptance is over answered questions, so a
 * question nobody submitted is not counted as a miss.
 */
export default function InterviewPanel({ interviews }) {
  if (interviews.total === 0) {
    return (
      <EmptyState
        description="Run a mock interview and your score trend and question acceptance will appear here."
        title="No mock interviews yet"
      />
    );
  }

  return (
    <div className="interview-analytics">
      <div className="interview-stats">
        <Stat
          detail={`${interviews.abandoned} abandoned · ${interviews.active} active`}
          label="Completed"
          value={interviews.completed}
        />
        <Stat
          detail={
            interviews.average_score == null
              ? "No completed session scored yet"
              : `Best ${interviews.best_score}%`
          }
          label="Average score"
          value={formatPercent(interviews.average_score)}
        />
        <Stat
          detail={`${formatPercent(interviews.acceptance_rate)} of answered questions`}
          label="Questions accepted"
          value={`${interviews.questions_accepted}/${interviews.questions_answered}`}
        />
      </div>
      {interviews.scores.length > 0 ? (
        <InterviewScoreChart scores={interviews.scores} />
      ) : (
        <EmptyState
          description="Finish a mock interview to build the score trend."
          title="No completed session carries a score yet"
        />
      )}
    </div>
  );
}

function Stat({ label, value, detail }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}
