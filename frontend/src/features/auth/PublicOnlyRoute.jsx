import { Navigate } from "react-router-dom";

import { LoadingState } from "../../components/ui/Feedback";
import { useAuth } from "./useAuth";

/**
 * Guard for pages that only make sense while signed out.
 *
 * Keeps a signed-in user away from `/login` and `/register` by sending them
 * back to the workspace instead of rendering a redundant form.
 */
export default function PublicOnlyRoute({ children, redirectTo = "/dashboard" }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingState label="Restoring your session" />;
  }

  if (isAuthenticated) {
    return <Navigate replace to={redirectTo} />;
  }

  return children;
}
