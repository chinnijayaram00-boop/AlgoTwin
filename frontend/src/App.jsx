import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "./components/layout/AppShell";
import LoginPage from "./features/auth/LoginPage";
import ProtectedRoute from "./features/auth/ProtectedRoute";
import PublicOnlyRoute from "./features/auth/PublicOnlyRoute";
import RegisterPage from "./features/auth/RegisterPage";
import NotFoundPage from "./pages/NotFoundPage";

// The authenticated pages are split into their own chunks and fetched when their
// route is visited. Two of them would otherwise dominate the initial download for
// every visitor, including anonymous ones on the login screen: the workspace pulls
// in Monaco, and the dashboard and analytics pull in Recharts. `AppShell`, the
// route guards, and the small auth/not-found pages stay eager so the first screen
// does not wait on a chunk. `AppShell` supplies the Suspense boundary around its
// outlet, so the shell stays on screen while a page chunk arrives.
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LearningPathPage = lazy(() => import("./pages/LearningPathPage"));
const ProblemsPage = lazy(() => import("./pages/ProblemsPage"));
const WorkspacePage = lazy(() => import("./pages/WorkspacePage"));
const SubmissionsPage = lazy(() => import("./pages/SubmissionsPage"));
const VisualizerPage = lazy(() => import("./pages/VisualizerPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const InterviewsPage = lazy(() => import("./pages/InterviewsPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const PersonalizationPage = lazy(() => import("./pages/PersonalizationPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

export default function App() {
  return (
    <Routes>
      <Route
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
        path="/login"
      />
      <Route
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
        path="/register"
      />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="learning-path" element={<LearningPathPage />} />
        <Route path="problems" element={<ProblemsPage />} />
        <Route path="problems/:slug" element={<WorkspacePage />} />
        <Route path="submissions" element={<SubmissionsPage />} />
        <Route path="visualizer" element={<VisualizerPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="interviews" element={<InterviewsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="coach" element={<PersonalizationPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
