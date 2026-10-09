import { EmptyState } from "../../components/ui/Feedback";

/**
 * One list of explainable signals -- strengths or weaknesses.
 *
 * Each row shows the claim, the sentence behind it, and the measurement it came
 * from, so the signal is checkable rather than asserted. The evidence is rendered
 * as a small marker rather than prose, because it is the fact the claim reduces
 * to, not a second explanation.
 */
export default function SignalsPanel({
  signals,
  emptyTitle,
  emptyDescription,
  tone = "violet",
}) {
  if (!signals || signals.length === 0) {
    return <EmptyState description={emptyDescription} title={emptyTitle} />;
  }

  return (
    <ul className="signal-list">
      {signals.map((signal) => (
        <li className="signal-item" key={signal.code}>
          <div className="signal-heading">
            <strong>{signal.title}</strong>
            <span className={`signal-evidence ${tone}`}>{signal.evidence}</span>
          </div>
          <p>{signal.detail}</p>
        </li>
      ))}
    </ul>
  );
}
