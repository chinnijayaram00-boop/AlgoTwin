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

function isValidationFailure(detail) {
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

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 10000);
  const { token, headers, ...fetchOptions } = options;

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
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
      error.isValidationError = isValidationFailure(payload?.detail);
      throw error;
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The API request timed out.");
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
