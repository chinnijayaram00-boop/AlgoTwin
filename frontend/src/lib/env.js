const configuredApiUrl = import.meta.env.VITE_API_URL;

/**
 * The API base URL comes from `VITE_API_URL` and nothing else.
 *
 * A silent fallback to a guessed port is what made this app look like it had a
 * network bug: the browser posted to the wrong port, so the request never
 * reached this API and the failure surfaced as an opaque "Failed to fetch".
 * Failing loudly at start-up turns a missing variable into an obvious
 * configuration error instead.
 */
function resolveApiBaseUrl() {
  const url = (configuredApiUrl || "").trim();

  if (!url) {
    throw new Error(
      "VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env and set it to the API base URL, for example http://localhost:8001/api/v1.",
    );
  }

  return url.replace(/\/$/, "");
}

export const API_BASE_URL = resolveApiBaseUrl();
