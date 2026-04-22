import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/layout/AppShell";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import NotFoundPage from "@/pages/NotFoundPage";
import JobBoardPage from "@/pages/public/JobBoardPage";
import JobDetailPage from "@/pages/public/JobDetailPage";
import ApplicationPage from "@/pages/public/ApplicationPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/*
         * AppShell wraps <Routes> so the nav is mounted once and never
         * remounted during navigation. The shell inspects location +
         * auth state to decide which chrome (header/sidebar) to render.
         */}
        <AppShell>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            {/* Public job board */}
            <Route path="/jobs" element={<JobBoardPage />} />
            <Route path="/jobs/:id" element={<JobDetailPage />} />
            <Route path="/jobs/:id/apply" element={<ApplicationPage />} />

            {/* Protected — ProtectedRoute redirects to /login if not authed */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
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
