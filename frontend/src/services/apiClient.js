import { API_BASE_URL } from "../lib/env";

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
    const payload = response.status === 204 ? null : await response.json();
    if (!response.ok) {
      const message = payload?.detail || "The API request failed.";
      throw new Error(message);
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
    return request(path, options);
  },
  post(path, body, options) {
    return request(path, {
      ...(options || {}),
      method: "POST",
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  },
};
