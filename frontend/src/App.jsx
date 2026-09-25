import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import AppShell from "./components/layout/AppShell";
import { LoadingState } from "./components/ui/Feedback";
import LoginPage from "./features/auth/LoginPage";
import RegisterPage from "./features/auth/RegisterPage";
import { useAuth } from "./features/auth/useAuth";
import AnalyticsPage from "./pages/AnalyticsPage";
import ComparePage from "./pages/ComparePage";
import DashboardPage from "./pages/DashboardPage";
import InterviewsPage from "./pages/InterviewsPage";
import NotFoundPage from "./pages/NotFoundPage";
import ProblemsPage from "./pages/ProblemsPage";
import SettingsPage from "./pages/SettingsPage";
import VisualizerPage from "./pages/VisualizerPage";
import WorkspacePage from "./pages/WorkspacePage";

function RequireAuth({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingState label="Restoring your session" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}

function PublicOnly({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingState label="Restoring your session" />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

export default function App() {
  return (
    <Routes>
      <Route
        element={
          <PublicOnly>
            <LoginPage />
          </PublicOnly>
        }
        path="/login"
      />
      <Route
        element={
          <PublicOnly>
            <RegisterPage />
          </PublicOnly>
        }
        path="/register"
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="problems" element={<ProblemsPage />} />
        <Route path="problems/:slug" element={<WorkspacePage />} />
        <Route path="visualizer" element={<VisualizerPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="interviews" element={<InterviewsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
