import { BrainCircuit, Code2, Flame, Target, Timer, Trophy } from "lucide-react";

import { formatMegabytes, formatMilliseconds, formatPercent } from "./analyticsFormat";

/**
 * The headline numbers: catalog and streak on the evidence of progress rows,
 * submissions on the evidence of judge runs, interviews on stored scores.
 *
 * A value with no evidence behind it renders as an em dash rather than a
 * plausible-looking zero -- `null` from the API means "never measured", which
 * is a different statement from "measured as zero".
 */
export default function AnalyticsOverview({ overview, interviews }) {
  const streakDetail =
    overview.current_streak_days > 0
      ? "Consecutive days with recorded activity"
      : "No activity recorded today yet";

  const interviewDetail =
    interviews.average_score == null
      ? `${interviews.completed} completed · no score recorded yet`
      : `${interviews.completed} completed · avg ${formatPercent(interviews.average_score)} · best ${interviews.best_score}%`;

  return (
    <div className="metrics-grid analytics-metrics">
      <InsightCard
        detail={`${formatPercent(overview.completion_percentage)} of the catalog`}
        icon={Trophy}
        label="Problems solved"
        value={`${overview.solved}/${overview.total_problems}`}
      />
      <InsightCard
        detail={streakDetail}
        icon={Flame}
        label="Current streak"
        value={`${overview.current_streak_days} ${overview.current_streak_days === 1 ? "day" : "days"}`}
      />
      <InsightCard
        detail={`${overview.judged_submissions} judged · ${overview.problems_submitted} problems`}
        icon={Code2}
        label="Submissions"
        value={overview.total_submissions}
      />
      <InsightCard
        detail={`${overview.accepted_submissions} accepted of ${overview.judged_submissions} judged`}
        icon={Target}
        label="Acceptance rate"
        value={formatPercent(overview.acceptance_rate)}
      />
      <InsightCard
        detail={`Avg memory ${formatMegabytes(overview.average_memory_mb)}`}
        icon={Timer}
        label="Avg runtime"
        value={formatMilliseconds(overview.average_runtime_ms)}
      />
      <InsightCard
        detail={interviewDetail}
        icon={BrainCircuit}
        label="Mock interviews"
        value={interviews.completed}
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
