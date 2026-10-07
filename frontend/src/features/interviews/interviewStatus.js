/**
 * The interview vocabulary as the learner sees it.
 *
 * The backend owns these values (`database.models.interview.InterviewStatus`).
 * They are mirrored here only for presentation: label, pill tone, and
 * description. An unrecognised value degrades to "Not started" instead of
 * rendering blank, so a status added server-side later cannot blank out the UI.
 *
 * The verdicts shown on questions are the submission vocabulary, not a second
 * copy: an interview question links to the submission the judge graded, so the
 * report and the history render the same verdict labels every other screenshot
 * uses.
 */

export const INTERVIEW_STATUSES = ["created", "in_progress", "completed", "abandoned"];

const PRESENTATION = {
  created: { label: "Not started", tone: "neutral", description: "Created, clock not started" },
  in_progress: { label: "In progress", tone: "medium", description: "The clock is running" },
  completed: { label: "Completed", tone: "success", description: "Finished and scored" },
  abandoned: { label: "Abandoned", tone: "hard", description: "Left without a score" },
};

export function isInterviewStatus(value) {
  return INTERVIEW_STATUSES.includes(value);
}

export function interviewStatusLabel(status) {
  return presentation(status).label;
}

export function interviewStatusTone(status) {
  return presentation(status).tone;
}

export function interviewStatusDescription(status) {
  return presentation(status).description;
}

/**
 * The countdown as the learner reads it: "MM:SS", or "H:MM:SS" past an hour.
 *
 * Returns "—" when there is no server-computed time to show, never "00:00" for
 * a session that is simply not running: an absent timer is not a finished one.
 */
export function formatRemainingSeconds(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mm = String(minutes).padStart(2, "0");
  const ss = String(secs).padStart(2, "0");
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

function presentation(status) {
  return PRESENTATION[status] ?? PRESENTATION.created;
}