import { useCallback, useEffect, useMemo, useState } from "react";

import { authService } from "./authService";
import { AuthContext } from "./authContext";
import { clearStoredToken, getStoredToken, storeToken } from "./authStorage";

function readSession() {
  const token = getStoredToken();
  if (!token) return { token: "", user: null };
  return { token, user: null };
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(readSession);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    if (!session.token) {
      setStatus("anonymous");
      return () => {
        cancelled = true;
      };
    }
    authService
      .me()
      .then((payload) => {
        if (cancelled) return;
        setSession({ token: getStoredToken(), user: payload });
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        clearStoredToken();
        setSession({ token: "", user: null });
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, [session.token]);

  const applySession = useCallback((payload) => {
    storeToken(payload.access_token);
    setSession({ token: payload.access_token, user: payload.user });
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      if (session.token) await authService.logout();
    } finally {
      clearStoredToken();
      setSession({ token: "", user: null });
      setStatus("anonymous");
    }
  }, [session.token]);

  const value = useMemo(
    () => ({
      user: session.user,
      isAuthenticated: status === "authenticated",
      isLoading: status === "loading",
      login: applySession,
      register: applySession,
      logout,
    }),
    [applySession, logout, session.user, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
