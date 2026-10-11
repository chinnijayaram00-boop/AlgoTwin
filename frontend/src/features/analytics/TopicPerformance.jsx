import { formatPercent } from "./analyticsFormat";

/**
 * Per-topic acceptance, weakest first, as a practice queue.
 *
 * Every row is read straight from the summary -- `accepted` over `judged` -- so
 * the meter cannot disagree with the numbers beside it. Only topics with judged
 * submissions are rendered (the caller filters), because a topic with no verdict
 * has no rate to show and a zero-width meter would say "failing" when it means
 * "unmeasured".
 */
export default function TopicPerformance({ rows }) {
  return (
    <div className="topic-accuracy">
      {rows.map((row) => (
        <div className="focus-area" key={row.topic}>
          <div className="focus-area-top">
            <strong>{row.topic}</strong>
            <span>
              {row.accepted}/{row.judged} accepted · {formatPercent(row.acceptance_rate)}
            </span>
          </div>
          <div className="snapshot-meter">
            <span
              style={{ width: `${Math.min(Math.max(row.acceptance_rate, 0), 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
