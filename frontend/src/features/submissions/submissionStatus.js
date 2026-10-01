/**
 * The submission vocabulary as the learner sees it.
 *
 * The backend owns these values
 * (`database.models.submission.SUBMISSION_STATUS_VALUES`). They are mirrored
 * here only for presentation: label, pill tone, and description. An
 * unrecognised value degrades to "Queued" instead of rendering blank, so a
 * status added server-side later cannot blank out the UI.
 *
 * All nine are reachable. Submitting runs the learner's program through the
 * judge and stores the verdict it reports, so the descriptions say what the
 * judge found rather than what it might find.
 *
 * The API also reports `test_cases_passed`, `test_cases_total`, `runtime_ms`,
 * `memory_mb`, `error_message`, and `judged_at`. Those are read-only and are
 * rendered: they are what the judge measured, and hiding them would leave a
 * learner told "Wrong Answer" with no way to see how far their answer got.
 */

export const SUBMISSION_STATUSES = [
  "queued",
  "running",
  "accepted",
  "wrong_answer",
  "runtime_error",
  "compilation_error",
  "time_limit_exceeded",
  "memory_limit_exceeded",
  "failed",
];

export const SUPPORTED_LANGUAGES = ["javascript", "python"];

/**
 * The one sentence that has to appear wherever a submission is shown, so the
 * boundary between what was stored and what was graded is stated by the product
 * and not just by the API docs.
 */
export const JUDGE_NOTE =
  "Submitting runs your code against every test case, hidden ones included. The judge reports the verdict and the measurements; the hidden cases themselves are never shown.";

const PRESENTATION = {
  queued: { label: "Queued", tone: "neutral", description: "Stored, never judged" },
  running: { label: "Running", tone: "medium", description: "Being judged" },
  accepted: { label: "Accepted", tone: "success", description: "Passed every test case" },
  wrong_answer: {
    label: "Wrong Answer",
    tone: "hard",
    description: "Ran to completion, but printed the wrong answer",
  },
  runtime_error: { label: "Runtime Error", tone: "hard", description: "Crashed while running" },
  compilation_error: {
    label: "Compilation Error",
    tone: "hard",
    description: "The interpreter could not start your code",
  },
  time_limit_exceeded: {
    label: "Time Limit Exceeded",
    tone: "medium",
    description: "Ran longer than the time limit",
  },
  memory_limit_exceeded: {
    label: "Memory Limit Exceeded",
    tone: "medium",
    description: "Stopped after exceeding the memory limit",
  },
  failed: { label: "Failed", tone: "hard", description: "The judge could not grade this" },
};

const LANGUAGE_LABELS = { javascript: "JavaScript", python: "Python" };

export function isSubmissionStatus(value) {
  return SUBMISSION_STATUSES.includes(value);
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

/** True once the judge, rather than the recorder, has spoken about the attempt. */
export function isJudgedStatus(status) {
  return isSubmissionStatus(status) && status !== "queued";
}

export function languageLabel(language) {
  return LANGUAGE_LABELS[language] || language || "—";
}

/**
 * How many cases passed, as "3 of 7 test cases passed".
 *
 * Returns `null` when there is no count to report, so a caller can leave the
 * field out entirely rather than print "null of null". A zero-pass run is
 * different from an ungraded one and must keep its row: "0 of 7" tells a
 * learner their program ran and was wrong everywhere, which is the single most
 * useful thing on a failing submission.
 */
export function formatCaseCounts(submission) {
  if (!submission) return null;
  const { test_cases_passed: passed, test_cases_total: total } = submission;
  if (passed === null || passed === undefined || !total) return null;
  return `${passed} of ${total} test cases passed`;
}

/**
 * A measured runtime, as "412 ms".
 *
 * `null` when the judge could not measure one, which is never reported as
 * "0 ms": an absent measurement is not a fast run.
 */
export function formatRuntime(runtimeMs) {
  if (runtimeMs === null || runtimeMs === undefined) return null;
  return `${runtimeMs} ms`;
}

/**
 * A measured peak memory, as "18 MB".
 *
 * Null where the platform cannot measure it -- Windows has no `RLIMIT_AS`, so
 * peak memory is not observable there. Rendered as an absent fact rather than a
 * zero, for the same reason a missing runtime is.
 */
export function formatMemory(memoryMb) {
  if (memoryMb === null || memoryMb === undefined) return null;
  return `${memoryMb} MB`;
}

function presentation(status) {
  return PRESENTATION[status] ?? PRESENTATION.queued;
}

/**
 * Format a submitted-at timestamp as date and time.
 *
 * A history is read as a sequence of attempts, so the time of day carries
 * information that a date alone would flatten.
 */
export function formatSubmittedAt(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
