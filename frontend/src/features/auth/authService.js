import { apiClient } from "../../services/apiClient";
import { getStoredToken } from "./authStorage";

function authOptions() {
  const token = getStoredToken();
  return token ? { token } : {};
}

export const authService = {
  register(credentials) {
    return apiClient.post("/auth/register", credentials);
  },

  login(credentials) {
    return apiClient.post("/auth/login", credentials);
  },

  me() {
    return apiClient.get("/auth/me", authOptions());
  },

  logout() {
    return apiClient.post("/auth/logout", undefined, authOptions());
  },
};
