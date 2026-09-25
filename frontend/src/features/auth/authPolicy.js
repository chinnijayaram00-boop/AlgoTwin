/**
 * Auth form policy, shared by the login and register pages.
 *
 * The values mirror the backend contract in `backend/app/schemas/auth.py`.
 * Keep both sides in step: the backend remains authoritative and re-validates
 * every request, this only drives client-side hints and early feedback.
 */
export const MIN_PASSWORD_LENGTH = 10;
export const MIN_NAME_LENGTH = 1;
export const MAX_EMAIL_LENGTH = 320;

export const PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters`;

export const AUTH_ROUTES = {
  login: "/login",
  register: "/register",
  workspace: "/dashboard",
};

/**
 * Where to send the user after a successful sign-in.
 *
 * A redirect captured by `ProtectedRoute` wins, so a deep link survives the
 * trip through the login form. Only same-origin absolute paths are honoured to
 * keep this from becoming an open redirect.
 */
export function resolveDestination(locationState, fallback = AUTH_ROUTES.workspace) {
  const candidate = locationState?.from;
  if (typeof candidate !== "string") return fallback;

  const trimmed = candidate.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) return fallback;
  if (trimmed.startsWith(AUTH_ROUTES.login) || trimmed.startsWith(AUTH_ROUTES.register)) {
    return fallback;
  }
  return trimmed;
}
