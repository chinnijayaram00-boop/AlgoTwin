/**
 * Display helpers for the analytics page.
 *
 * Pure functions rather than inline formatting, so the numbers a chart
 * renders are testable without rendering the chart, and so a rate never gets
 * rounded two different ways in two different panels.
 */

const VERDICT_LABELS = {
  accepted: "Accepted",
  queued: "Queued",
  running: "Running",
  wrong_answer: "Wrong answer",
  runtime_error: "Runtime error",
  compile_error: "Compile error",
  time_limit_exceeded: "Time limit exceeded",
  memory_limit_exceeded: "Memory limit exceeded",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A stored verdict slug as a person would read it. */
export function verdictLabel(status) {
  if (VERDICT_LABELS[status]) return VERDICT_LABELS[status];
  return status.replace(/_/g, " ").replace(/^./, (letter) => letter.toUpperCase());
}

/**
 * "2026-10-07" as "Oct 7". Parsed field by field rather than through
 * `Date.parse`, because a timezone offset could otherwise move an activity
 * day onto the neighbouring date and shift the whole series.
 */
export function shortDay(isoDate) {
  const [year, month, day] = String(isoDate).split("-").map(Number);
  if (!year || !month || !day) return String(isoDate);
  return `${MONTHS[month - 1]} ${day}`;
}

/** A rate as a whole-or-tenth percent: 66.666…% becomes "66.7%". */
export function formatPercent(value) {
  if (value == null) return "—";
  return `${Math.round(value * 10) / 10}%`;
}

/** A runtime average the judge actually measured, or an em dash for none. */
export function formatMilliseconds(value) {
  if (value == null) return "—";
  return `${Math.round(value)} ms`;
}

/** A memory average the judge actually measured, or an em dash for none. */
export function formatMegabytes(value) {
  if (value == null) return "—";
  return `${Math.round(value * 100) / 100} MB`;
}

/**
 * The topics worth charting: the ones the learner has actually touched,
 * most solved first, capped at `limit`.
 *
 * Every catalog topic ships in the response and the untouched ones all sit
 * at zero; charting forty-five zero rows would bury the two that say
 * something, so they are filtered out here rather than in the component.
 * The input array is not mutated.
 */
export function activeTopics(topics, limit = 12) {
  return topics
    .filter((row) => row.solved > 0 || row.attempted > 0)
    .sort(
      (left, right) =>
        right.solved - left.solved ||
        right.attempted - left.attempted ||
        left.topic.localeCompare(right.topic),
    )
    .slice(0, limit);
}
