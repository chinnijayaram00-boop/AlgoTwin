import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "./components/layout/AppShell";
import LoginPage from "./features/auth/LoginPage";
import ProtectedRoute from "./features/auth/ProtectedRoute";
import PublicOnlyRoute from "./features/auth/PublicOnlyRoute";
import RegisterPage from "./features/auth/RegisterPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ComparePage from "./pages/ComparePage";
import DashboardPage from "./pages/DashboardPage";
import InterviewsPage from "./pages/InterviewsPage";
import LearningPathPage from "./pages/LearningPathPage";
import NotFoundPage from "./pages/NotFoundPage";
import ProblemsPage from "./pages/ProblemsPage";
import PersonalizationPage from "./pages/PersonalizationPage";
import SettingsPage from "./pages/SettingsPage";
import SubmissionsPage from "./pages/SubmissionsPage";
import VisualizerPage from "./pages/VisualizerPage";
import WorkspacePage from "./pages/WorkspacePage";

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
