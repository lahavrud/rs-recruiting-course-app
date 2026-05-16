import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Suspense, useEffect } from "react";
import { HelmetProvider } from "react-helmet-async";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AdminRoute from "@/components/AdminRoute";
import CompanyRoute from "@/components/CompanyRoute";
import AppShell from "@/components/layout/AppShell";
import { lazyWithRetry } from "@/utils/lazyWithRetry";

// Eager — entry funnels Google + direct visits land on most often. Keeping
// these in the main bundle is critical for LCP / Core Web Vitals on the
// pages that receive organic search traffic.
import LandingPage from "@/pages/public/LandingPage";
import JobBoardPage from "@/pages/public/JobBoardPage";
import JobDetailPage from "@/pages/public/JobDetailPage";
import LoginPage from "@/pages/LoginPage";

// Lazy — secondary public pages + every behind-auth screen. Chunked out so
// they don't bloat the initial download for a visitor landing on / or /jobs.
// `lazyWithRetry` recovers gracefully from a stale-chunk crash when a deploy
// happens while a user has the SPA open (their tab's bundle references chunk
// hashes that no longer exist on the server).
const ApplicationPage = lazyWithRetry(() => import("@/pages/public/ApplicationPage"));
const AboutPage = lazyWithRetry(() => import("@/pages/public/AboutPage"));
const ContactPage = lazyWithRetry(() => import("@/pages/public/ContactPage"));
const ArticlesIndexPage = lazyWithRetry(() => import("@/pages/public/ArticlesIndexPage"));
const ArticlePage = lazyWithRetry(() => import("@/pages/public/ArticlePage"));
const RegisterPage = lazyWithRetry(() => import("@/pages/RegisterPage"));
const ActivatePage = lazyWithRetry(() => import("@/pages/ActivatePage"));
const ForgotPasswordPage = lazyWithRetry(() => import("@/pages/ForgotPasswordPage"));
const ResetPasswordPage = lazyWithRetry(() => import("@/pages/ResetPasswordPage"));
const DashboardPage = lazyWithRetry(() => import("@/pages/DashboardPage"));
const NotFoundPage = lazyWithRetry(() => import("@/pages/NotFoundPage"));
const AdminCompaniesPage = lazyWithRetry(() => import("@/pages/admin/AdminCompaniesPage"));
const AdminJobsPage = lazyWithRetry(() => import("@/pages/admin/AdminJobsPage"));
const AdminApplicationsPage = lazyWithRetry(() => import("@/pages/admin/AdminApplicationsPage"));
const AdminCandidatesPage = lazyWithRetry(() => import("@/pages/admin/AdminCandidatesPage"));
const CompanyJobsPage = lazyWithRetry(() => import("@/pages/company/CompanyJobsPage"));

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

/** Placeholder while a lazy route chunk loads. Opaque `bg-page` so it
 *  covers the static `page-hero-bg` city image set in index.html — that
 *  background is meant for the landing route only, and would otherwise
 *  show through during nav to /jobs, /about, etc. while the chunk
 *  downloads. */
function RouteFallback() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-page">
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
