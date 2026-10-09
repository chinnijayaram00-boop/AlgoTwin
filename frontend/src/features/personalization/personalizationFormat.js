/**
 * Display helpers for the personalized coach.
 *
 * The focus options and the degraded-reason sentences live here rather than in
 * the components, so the labels a learner reads and the values the request sends
 * cannot drift, and so the fallback vocabulary is defined in one place.
 */

/** The focus values the API accepts, in the order they are offered. */
export const MENTOR_FOCUS_OPTIONS = [
  { value: "overview", label: "Overview" },
  { value: "strengths", label: "Build on strengths" },
  { value: "weaknesses", label: "Address weaknesses" },
  { value: "next_steps", label: "Next steps" },
];

const DEGRADED_MESSAGES = {
  provider_not_configured:
    "No AI provider is configured on this deployment, so this guidance was written from your profile by rules, not by a language model.",
  rate_limited:
    "You have reached the AI request limit for now, so this guidance was written from your profile by rules, not by a language model.",
  provider_timeout:
    "The AI provider took too long to answer, so this guidance was written from your profile by rules.",
  provider_error:
    "The AI provider could not answer, so this guidance was written from your profile by rules.",
};

/**
 * Why a mentor response did not come from a model, in a sentence.
 *
 * The API names the reason with a closed vocabulary; this maps it to something a
 * learner can read, and returns an empty string for a successful generation or an
 * unrecognised reason rather than inventing an explanation.
 */
export function degradedMessage(reason) {
  return DEGRADED_MESSAGES[reason] || "";
}

/** A difficulty as one of the pill tones the UI already knows. */
export function difficultyTone(difficulty) {
  if (difficulty === "Easy") return "easy";
  if (difficulty === "Hard") return "hard";
  return "medium";
}
