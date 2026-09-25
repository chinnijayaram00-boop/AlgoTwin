import { apiClient } from "./apiClient";

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, value);
    }
  });
  return query.toString();
}

function withQuery(path, params) {
  const query = toQuery(params);
  return query ? `${path}?${query}` : path;
}

export const platformApi = {
  health() {
    return apiClient.get("/health");
  },
  aiStatus() {
    return apiClient.get("/ai/status");
  },
  algorithms() {
    return apiClient.get("/algorithms");
  },
  dashboardSummary() {
    return apiClient.get("/dashboard/summary");
  },
};

export const problemApi = {
  list(params = {}) {
    return apiClient.get(withQuery("/problems", params));
  },
  get(slug) {
    return apiClient.get(`/problems/${encodeURIComponent(slug)}`);
  },
};
