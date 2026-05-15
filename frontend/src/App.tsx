import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { lazy, Suspense, useEffect } from "react";
import { HelmetProvider } from "react-helmet-async";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AdminRoute from "@/components/AdminRoute";
import CompanyRoute from "@/components/CompanyRoute";
import AppShell from "@/components/layout/AppShell";

// Eager — entry funnels Google + direct visits land on most often. Keeping
// these in the main bundle is critical for LCP / Core Web Vitals on the
// pages that receive organic search traffic.
import LandingPage from "@/pages/public/LandingPage";
import JobBoardPage from "@/pages/public/JobBoardPage";
import JobDetailPage from "@/pages/public/JobDetailPage";
import LoginPage from "@/pages/LoginPage";

// Lazy — secondary public pages + every behind-auth screen. Chunked out so
// they don't bloat the initial download for a visitor landing on / or /jobs.
const ApplicationPage = lazy(() => import("@/pages/public/ApplicationPage"));
const AboutPage = lazy(() => import("@/pages/public/AboutPage"));
const ContactPage = lazy(() => import("@/pages/public/ContactPage"));
const ArticlesIndexPage = lazy(() => import("@/pages/public/ArticlesIndexPage"));
const ArticlePage = lazy(() => import("@/pages/public/ArticlePage"));
const RegisterPage = lazy(() => import("@/pages/RegisterPage"));
const ActivatePage = lazy(() => import("@/pages/ActivatePage"));
const ForgotPasswordPage = lazy(() => import("@/pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("@/pages/ResetPasswordPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));
const AdminCompaniesPage = lazy(() => import("@/pages/admin/AdminCompaniesPage"));
const AdminJobsPage = lazy(() => import("@/pages/admin/AdminJobsPage"));
const AdminApplicationsPage = lazy(() => import("@/pages/admin/AdminApplicationsPage"));
const AdminCandidatesPage = lazy(() => import("@/pages/admin/AdminCandidatesPage"));
const CompanyJobsPage = lazy(() => import("@/pages/company/CompanyJobsPage"));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

/** Push a page_view event to GTM's dataLayer on every SPA route change.
 *  GTM only fires once on initial load by default — without this, every
 *  client-side navigation would be invisible to GA4 / Tag Manager.
 *  No-ops when dataLayer isn't present (dev build with no VITE_GTM_ID). */
function GtmPageView() {
  const { pathname } = useLocation();
  useEffect(() => {
    const dl = (window as unknown as { dataLayer?: unknown[] }).dataLayer;
    if (Array.isArray(dl)) {
      dl.push({ event: "page_view", page_path: pathname });
    }
  }, [pathname]);
  return null;
}

/** Minimal placeholder while a lazy route chunk loads. Matches the dark
 *  page background so there's no light-flash, and shows a subtle copper
 *  ring so the user knows something is happening. */
function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page">
      <div
        className="h-9 w-9 animate-spin rounded-full border-2 border-copper/30 border-t-copper"
        role="status"
        aria-label="טוען…"
      />
    </div>
  );
}

export default function App() {
  return (
    <HelmetProvider>
    <BrowserRouter>
      <ScrollToTop />
      <GtmPageView />
      <AuthProvider>
        <AppShell>
          <Suspense fallback={<RouteFallback />}>
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
          </Suspense>
        </AppShell>
      </AuthProvider>
    </BrowserRouter>
    </HelmetProvider>
  );
}
