/**
 * The learner-facing progress vocabulary.
 *
 * The backend owns these values (`database.models.progress.ProgressStatus`).
 * They are mirrored here only for presentation: label, pill tone, and icon.
 * An unrecognised value degrades to "Not Started" instead of rendering blank,
 * so a status added server-side later cannot blank out the UI.
 */

export const PROGRESS_STATUSES = ["not_started", "attempted", "solved"];

const PRESENTATION = {
  not_started: { label: "Not Started", tone: "neutral", description: "Not opened yet" },
  attempted: { label: "Attempted", tone: "medium", description: "Started, not solved" },
  solved: { label: "Solved", tone: "success", description: "Marked as solved" },
};

export function isProgressStatus(value) {
  return PROGRESS_STATUSES.includes(value);
}

export function statusLabel(status) {
  return presentation(status).label;
}

export function statusTone(status) {
  return presentation(status).tone;
}

export function statusDescription(status) {
  return presentation(status).description;
}

function presentation(status) {
  return PRESENTATION[status] ?? PRESENTATION.not_started;
}

/** Format an ISO timestamp for the progress panels, tolerating null. */
export function formatTimestamp(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Render a runtime in milliseconds as a compact human duration. */
export function formatDuration(milliseconds) {
  if (typeof milliseconds !== "number" || !Number.isFinite(milliseconds) || milliseconds < 0) {
    return "—";
  }
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  return `${(milliseconds / 1000).toFixed(milliseconds < 10000 ? 2 : 1)} s`;
}
