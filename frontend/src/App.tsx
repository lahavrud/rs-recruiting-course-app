import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { HelmetProvider } from "react-helmet-async";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AdminRoute from "@/components/AdminRoute";
import CompanyRoute from "@/components/CompanyRoute";
import AppShell from "@/components/layout/AppShell";
import ActivatePage from "@/pages/ActivatePage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/ResetPasswordPage";
import DashboardPage from "@/pages/DashboardPage";
import NotFoundPage from "@/pages/NotFoundPage";
// Public
import JobBoardPage from "@/pages/public/JobBoardPage";
import JobDetailPage from "@/pages/public/JobDetailPage";
import ApplicationPage from "@/pages/public/ApplicationPage";
import LandingPage from "@/pages/public/LandingPage";
import AboutPage from "@/pages/public/AboutPage";
import ContactPage from "@/pages/public/ContactPage";
import ArticlesIndexPage from "@/pages/public/ArticlesIndexPage";
import ArticlePage from "@/pages/public/ArticlePage";
// Admin
import AdminCompaniesPage from "@/pages/admin/AdminCompaniesPage";
import AdminJobsPage from "@/pages/admin/AdminJobsPage";
import AdminApplicationsPage from "@/pages/admin/AdminApplicationsPage";
import AdminCandidatesPage from "@/pages/admin/AdminCandidatesPage";
// Company
import CompanyJobsPage from "@/pages/company/CompanyJobsPage";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

export default function App() {
  return (
    <HelmetProvider>
    <BrowserRouter>
      <ScrollToTop />
      <AuthProvider>
        <AppShell>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/activate" element={<ActivatePage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* Public landing page */}
            <Route path="/" element={<LandingPage />} />

            {/* Public informational pages */}
            <Route path="/about" element={<AboutPage />} />
            <Route path="/contact" element={<ContactPage />} />

            {/* Public job board */}
            <Route path="/jobs" element={<JobBoardPage />} />
            <Route path="/jobs/:id" element={<JobDetailPage />} />
            <Route path="/jobs/:id/apply" element={<ApplicationPage />} />

            {/* Public articles */}
            <Route path="/articles" element={<ArticlesIndexPage />} />
            <Route path="/articles/:slug" element={<ArticlePage />} />

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
    </HelmetProvider>
  );
}
