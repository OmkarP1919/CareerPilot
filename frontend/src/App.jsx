import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { LanguageProvider } from "./context/LanguageContext";
import { ToastProvider } from "./components/Toast";
import MainLayout from "./layouts/MainLayout";
import AuthLayout from "./layouts/AuthLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import SignUpPage from "./pages/SignUpPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import DashboardPage from "./pages/DashboardPage";
import ProfilePage from "./pages/ProfilePage";
import ResumesPage from "./pages/ResumesPage";
import JobsPage from "./pages/JobsPage";
import JobDetailsPage from "./pages/JobDetailsPage";
import MatchAnalysisPage from "./pages/MatchAnalysisPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>
          <ToastProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<LandingPage />} />

                <Route element={<AuthLayout />}>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/signup" element={<SignUpPage />} />
                  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                </Route>

                <Route element={<ProtectedRoute />}>
                  <Route element={<MainLayout />}>
                    {/* Primary navigation routes */}
                    <Route path="/home" element={<DashboardPage />} />
                    <Route path="/discover" element={<JobsPage />} />
                    <Route path="/discover/:id" element={<JobDetailsPage />} />
                    <Route path="/discover/:id/match" element={<MatchAnalysisPage />} />
                    <Route path="/resumes" element={<ResumesPage />} />
                    <Route path="/pipeline" element={<ApplicationsPage />} />
                    <Route path="/insights" element={<AnalyticsPage />} />
                    <Route path="/profile" element={<ProfilePage />} />
                    <Route path="/settings" element={<SettingsPage />} />

                    {/* Route Aliases */}
                    <Route path="/dashboard" element={<Navigate to="/home" replace />} />
                    <Route path="/jobs" element={<Navigate to="/discover" replace />} />
                    <Route path="/jobs/:id" element={<Navigate to="/discover/:id" replace />} />
                    <Route path="/jobs/:id/match" element={<Navigate to="/discover/:id/match" replace />} />
                    <Route path="/resume" element={<Navigate to="/resumes" replace />} />
                    <Route path="/applications" element={<Navigate to="/pipeline" replace />} />
                    <Route path="/analytics" element={<Navigate to="/insights" replace />} />
                  </Route>
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  );
}
