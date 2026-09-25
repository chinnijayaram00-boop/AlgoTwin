import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { authService } from "./authService";
import { AuthContext } from "./authContext";
import { clearStoredToken, getStoredToken, storeToken } from "./authStorage";

const ANONYMOUS = Object.freeze({ token: "", user: null });

function readStoredSession() {
  const token = getStoredToken();
  return token ? { token, user: null } : ANONYMOUS;
}

/**
 * Owns the client-side session.
 *
 * The access token lives in `localStorage` so a browser refresh can restore the
 * session. On start-up, and whenever a token appears that this provider has not
 * already validated, it calls `/auth/me` to confirm the token is still usable
 * before treating the visitor as signed in. A token the API rejects is
 * discarded, which is how an expired session signs the user out.
 */
export function AuthProvider({ children }) {
  const [session, setSession] = useState(readStoredSession);
  const [status, setStatus] = useState("loading");
  const validatedToken = useRef(null);

  useEffect(() => {
    const token = session.token;

    if (!token) {
      validatedToken.current = null;
      setStatus("anonymous");
      return undefined;
    }

    // A token we just issued ourselves is already trusted; re-checking it would
    // cost a round trip and could throw away a perfectly good session.
    if (validatedToken.current === token && session.user) {
      setStatus("authenticated");
      return undefined;
    }

    let cancelled = false;
    setStatus("loading");

    authService
      .me()
      .then((profile) => {
        if (cancelled) return;
        validatedToken.current = token;
        setSession({ token, user: profile });
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        validatedToken.current = null;
        clearStoredToken();
        setSession(ANONYMOUS);
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, [session.token, session.user]);

  const applySession = useCallback((payload) => {
    const token = payload?.access_token;
    if (!token) {
      throw new Error("The authentication response did not include an access token.");
    }
    storeToken(token);
    validatedToken.current = token;
    setSession({ token, user: payload.user ?? null });
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    // The local session is cleared no matter what the API says, so a failed
    // sign-out call must not surface as a rejection the caller has to handle.
    try {
      if (getStoredToken()) {
        await authService.logout();
      }
    } catch {
      // Access tokens are stateless, so discarding the token locally is the
      // authoritative sign-out. The acknowledgement is best effort.
    } finally {
      validatedToken.current = null;
      clearStoredToken();
      setSession(ANONYMOUS);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo(
    () => ({
      user: session.user,
      token: session.token,
      status,
      isAuthenticated: status === "authenticated",
      isLoading: status === "loading",
      login: applySession,
      register: applySession,
      logout,
    }),
    [applySession, logout, session.token, session.user, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
