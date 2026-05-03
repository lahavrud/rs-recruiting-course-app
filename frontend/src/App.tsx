import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AdminRoute from "@/components/AdminRoute";
import CompanyRoute from "@/components/CompanyRoute";
import AppShell from "@/components/layout/AppShell";
import ActivatePage from "@/pages/ActivatePage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import DashboardPage from "@/pages/DashboardPage";
import NotFoundPage from "@/pages/NotFoundPage";
// Public
import JobBoardPage from "@/pages/public/JobBoardPage";
import JobDetailPage from "@/pages/public/JobDetailPage";
import ApplicationPage from "@/pages/public/ApplicationPage";
import LandingPage from "@/pages/public/LandingPage";
// Admin
import AdminCompaniesPage from "@/pages/admin/AdminCompaniesPage";
import AdminJobsPage from "@/pages/admin/AdminJobsPage";
import AdminApplicationsPage from "@/pages/admin/AdminApplicationsPage";
import AdminCandidatesPage from "@/pages/admin/AdminCandidatesPage";
// Company
import CompanyJobsPage from "@/pages/company/CompanyJobsPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/activate" element={<ActivatePage />} />

            {/* Public landing page */}
            <Route path="/" element={<LandingPage />} />

            {/* Public job board */}
            <Route path="/jobs" element={<JobBoardPage />} />
            <Route path="/jobs/:id" element={<JobDetailPage />} />
            <Route path="/jobs/:id/apply" element={<ApplicationPage />} />

            {/* Shared authenticated dashboard */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />

            {/* Admin-only routes */}
            <Route
              path="/admin/companies"
              element={
                <AdminRoute>
                  <AdminCompaniesPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/jobs"
              element={
                <AdminRoute>
                  <AdminJobsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/applications"
              element={
                <AdminRoute>
                  <AdminApplicationsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/candidates"
              element={
                <AdminRoute>
                  <AdminCandidatesPage />
                </AdminRoute>
              }
            />

            {/* Company-only routes */}
            <Route
              path="/company/jobs"
              element={
                <CompanyRoute>
                  <CompanyJobsPage />
                </CompanyRoute>
              }
            />

            {/* Catch-all */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AppShell>
      </AuthProvider>
    </BrowserRouter>
  );
}
