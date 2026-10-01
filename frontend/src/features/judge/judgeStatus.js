/**
 * The run vocabulary as the learner sees it.
 *
 * The backend owns these values (`database.models.submission.SubmissionStatus`,
 * mirrored by the run response schema). They are mirrored here only for
 * presentation: label, pill tone, and description. An unrecognised value degrades
 * to a neutral "Result" rather than rendering blank, so a verdict added
 * server-side later cannot blank out the UI.
 *
 * The one rule this module exists to enforce in the UI: **a null verdict is not a
 * pass.** A run on a learner's own input has no expected output, so the API sends
 * `verdict: null` and this module renders that as "No verdict", never as
 * "Accepted". Displaying a null verdict as anything favourable is how a debugging
 * aid turns into a false promise.
 */

/** The verdicts a graded run can report. */
export const RUN_VERDICTS = [
  "accepted",
  "wrong_answer",
  "runtime_error",
  "compilation_error",
  "time_limit_exceeded",
  "memory_limit_exceeded",
  "failed",
];

const PRESENTATION = {
  accepted: {
    label: "Accepted",
    tone: "success",
    description: "Every visible test case matched.",
  },
  wrong_answer: {
    label: "Wrong answer",
    tone: "hard",
    description: "The program ran but printed the wrong answer.",
  },
  runtime_error: {
    label: "Runtime error",
    tone: "hard",
    description: "The program crashed before it finished.",
  },
  compilation_error: {
    label: "Compilation error",
    tone: "hard",
    description: "The program could not be started.",
  },
  time_limit_exceeded: {
    label: "Time limit exceeded",
    tone: "medium",
    description: "The program ran longer than its time limit allows.",
  },
  memory_limit_exceeded: {
    label: "Memory limit exceeded",
    tone: "medium",
    description: "The program used more memory than its limit allows.",
  },
  failed: {
    label: "Failed",
    tone: "hard",
    description: "The judge could not confirm this answer.",
  },
};

/**
 * The sentence shown wherever a run's result appears.
 *
 * A run *is* graded -- against the problem's visible examples, and that verdict is
 * what the panel shows -- but it stores nothing and says nothing about the hidden
 * cases. Both halves have to be stated together: a green tick next to "not saved"
 * is the honest reading, while either half on its own misleads. "Is not graded"
 * would be a lie, because a verdict was returned; "passed" on its own would
 * suggest the full graded suite was cleared.
 */
export const RUN_NOTE =
  "Run is a debugging aid. It grades your code against the visible examples only, is not saved, and says nothing about the hidden cases.";

/**
 * What a run on the learner's own input can honestly say.
 *
 * There is no expected output for a made-up input, so there is nothing to pass.
 */
export const AD_HOC_NOTE =
  "Your own input has no expected output, so this run has no verdict and no pass count.";

export function isRunVerdict(value) {
  return RUN_VERDICTS.includes(value);
}

/**
 * The label for a run's verdict.
 *
 * A null or absent verdict is `null` -- the absence of a verdict, not a verdict.
 */
export function verdictLabel(verdict) {
  if (!verdict) return "No verdict";
  return PRESENTATION[verdict]?.label ?? "Result";
}

export function verdictTone(verdict) {
  if (!verdict) return "neutral";
  return PRESENTATION[verdict]?.tone ?? "neutral";
}

export function verdictDescription(verdict) {
  if (!verdict) return "Nothing was compared against an expected output.";
  return PRESENTATION[verdict]?.description ?? "The judge reported this result.";
}

/** Whether the result is a graded run of the problem's own cases. */
export function isGradedRun(result) {
  return Boolean(result && !result.ad_hoc && result.verdict);
}

/**
 * Summarise a graded run as "passed of total".
 *
 * Returns `null` when there is no graded run to summarise, so a caller renders
 * nothing rather than "0 of 0" -- which reads as a failing result.
 */
export function formatCaseCounts(result) {
  if (!isGradedRun(result)) return null;
  return `${result.cases_passed} of ${result.cases_total} test cases passed`;
}

/** Format a measured duration in milliseconds. */
export function formatRunDuration(ms) {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/** Format a measured peak memory in megabytes, or `null` if it was not measurable. */
export function formatPeakMemory(mb) {
  if (typeof mb !== "number" || !Number.isFinite(mb) || mb <= 0) return null;
  return `${mb.toFixed(1)} MB`;
}

export function languageLabel(language) {
  const labels = { javascript: "JavaScript", python: "Python" };
  return labels[language] || language || "—";
}
