import { Navigate, useLocation } from "react-router-dom";

import { LoadingState } from "../../components/ui/Feedback";
import { useAuth } from "./useAuth";

/**
 * Guard for authenticated pages.
 *
 * While the stored token is being revalidated the route renders a loading
 * state rather than redirecting, so a page refresh on a deep link does not
 * bounce the user to the login screen. Anonymous visitors are redirected to
 * `/login`, carrying the path they wanted so login can return them there.
 */
export default function ProtectedRoute({ children, redirectTo = "/login" }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingState label="Restoring your session" />;
  }

  if (!isAuthenticated) {
    return <Navigate replace state={{ from: location.pathname + location.search }} to={redirectTo} />;
  }

  return children;
}
