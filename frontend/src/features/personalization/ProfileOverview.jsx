import { BrainCircuit, Flame, Target, Trophy } from "lucide-react";

import { formatPercent } from "../analytics/analyticsFormat";

/**
 * The headline numbers behind every signal the profile reports.
 *
 * A value with no evidence renders as it was recorded rather than as a
 * plausible-looking default: a `null` average interview score is "no score yet",
 * not zero, matching the analytics page's treatment of the same field.
 */
export default function ProfileOverview({ overview }) {
  const scoreDetail =
    overview.average_interview_score == null
      ? `${overview.interviews_completed} completed · no score recorded`
      : `${overview.interviews_completed} completed · avg ${formatPercent(
          overview.average_interview_score,
        )}`;

  return (
    <div className="metrics-grid analytics-metrics">
      <InsightCard
        detail={`${formatPercent(overview.completion_percentage)} of the catalog`}
        icon={Trophy}
        label="Problems solved"
        value={`${overview.solved}/${overview.total_problems}`}
      />
      <InsightCard
        detail={
          overview.current_streak_days > 0
            ? "Consecutive days with recorded activity"
            : "No activity recorded today yet"
        }
        icon={Flame}
        label="Current streak"
        value={`${overview.current_streak_days} ${
          overview.current_streak_days === 1 ? "day" : "days"
        }`}
      />
      <InsightCard
        detail={`${overview.accepted_submissions} accepted of ${overview.judged_submissions} judged`}
        icon={Target}
        label="Acceptance rate"
        value={formatPercent(overview.acceptance_rate)}
      />
      <InsightCard
        detail={scoreDetail}
        icon={BrainCircuit}
        label="Mock interviews"
        value={overview.interviews_completed}
      />
    </div>
  );
}

function InsightCard({ icon: Icon, label, value, detail }) {
  return (
    <div className="metric-card insight-card">
      <div className="metric-icon">
        <Icon size={18} />
      </div>
      <div className="metric-label">{label}</div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}
