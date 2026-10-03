import { API_BASE_URL } from "../lib/env";

const VALIDATION_TYPES = new Set([
  "missing",
  "string_too_short",
  "string_too_long",
  "value_error",
  "int_parsing",
]);

/**
 * Turn a FastAPI `detail` payload into one readable sentence.
 *
 * FastAPI answers a 422 with `detail` as an array of `{loc, msg, type}`
 * objects. Interpolating that directly yields "[object Object]", so flatten it
 * into the field name plus the message.
 */
export function describeApiError(detail, fallback) {
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object") return typeof item === "string" ? item : "";
        const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
        const message = typeof item.msg === "string" ? item.msg : "";
        if (!message) return "";
        return field ? `${field}: ${message}` : message;
      })
      .filter(Boolean);

    if (messages.length) {
      return messages.join(" ");
    }
  }

  if (detail && typeof detail === "object" && typeof detail.msg === "string") {
    return detail.msg;
  }

  return fallback;
}

/**
 * Whether this failure was the API refusing the caller's input.
 *
 * A 422 is that answer by definition. FastAPI says so in two shapes: the
 * `loc`/`msg`/`type` array a request-schema rejection produces, and the plain string
 * a handler's own `HTTPException(422, detail=str(...))` produces. A handler has no
 * array to offer, and the algorithm lab refuses every input it cannot parse that
 * way -- so recognising only the array classified a rejected input as an ordinary
 * server failure. The status is the signal; the array is kept as a fallback for a
 * deployment that reports the shape without the status.
 */
function isValidationFailure(status, detail) {
  if (status === 422) return true;
  return (
    Array.isArray(detail) &&
    detail.some((item) => item && typeof item === "object" && VALIDATION_TYPES.has(item.type))
  );
}

async function readBody(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return { text: await response.text() };
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * How long a request waits before it is abandoned.
 *
 * Ten seconds suits every read in the app and every write, but not a code run:
 * the API holds a run open until the judge finishes, and the judge's own budget
 * is tens of seconds. A caller that knowingly waits longer says so per request
 * rather than this growing for everything, so a hung backend still fails fast
 * on ordinary calls.
 */
export const DEFAULT_TIMEOUT_MS = 10000;

async function request(path, options = {}) {
  const controller = new AbortController();
  const { token, headers, timeoutMs, ...fetchOptions } = options;
  const waitMs = Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : DEFAULT_TIMEOUT_MS;
  const timeoutId = window.setTimeout(() => controller.abort(), waitMs);
  const url = `${API_BASE_URL}${path}`;

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        "Content-Type": "application/json",
        ...(headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: controller.signal,
    });

    const payload = await readBody(response);
    if (!response.ok) {
      const error = new Error(
        describeApiError(payload?.detail, `The API request failed (${response.status}).`),
      );
      error.status = response.status;
      error.detail = payload?.detail ?? null;
      error.isValidationError = isValidationFailure(response.status, payload?.detail);
      throw error;
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The API request timed out.");
    }
    // A `TypeError` here is the browser refusing the request before it produced
    // a response: the API is not running, the URL is wrong, or the origin is not
    // in the CORS allowlist. The bare "Failed to fetch" hides which one it was,
    // so name the URL that was actually attempted.
    if (error instanceof TypeError) {
      const wrapped = new Error(`Could not reach the API at ${url}. ${error.message}`);
      wrapped.cause = error;
      throw wrapped;
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export const apiClient = {
  get(path, options) {
    return request(path, { ...(options || {}), method: "GET" });
  },
  post(path, body, options) {
    return request(path, {
      ...(options || {}),
      method: "POST",
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  },
  put(path, body, options) {
    return request(path, {
      ...(options || {}),
      method: "PUT",
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  },
};
