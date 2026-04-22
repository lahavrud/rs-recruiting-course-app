/**
 * AppShell — single persistent wrapper rendered once at the root.
 *
 * It owns the navigation so the nav is never unmounted during in-app
 * navigation. Only the <main> content re-animates on route changes.
 *
 * Three visual modes, chosen at render time:
 *   1. /login  → bare page, no nav
 *   2. authenticated → app header + collapsible sidebar
 *   3. public  → minimal public header
 */
import { type ReactNode, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import Header from "./Header";
import Sidebar from "./Sidebar";

interface Props {
  children: ReactNode;
}

function PublicHeader() {
  const { isAuthenticated } = useAuth();

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:py-4">
        <Link
          to="/jobs"
          className="text-base font-semibold text-gray-900 hover:text-blue-600 sm:text-lg"
        >
          RS Recruitment
        </Link>
        <nav className="flex items-center gap-2 sm:gap-4">
          <Link to="/jobs" className="text-sm text-gray-600 hover:text-gray-900">
            Jobs
          </Link>
          {isAuthenticated ? (
            <Link
              to="/"
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 sm:px-4"
            >
              Dashboard
            </Link>
          ) : (
            <Link
              to="/login"
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 sm:px-4"
            >
              Login
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

export default function AppShell({ children }: Props) {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // ── Login page: no chrome at all ──────────────────────────────────────
  if (pathname === "/login") {
    return <>{children}</>;
  }

  // ── Authenticated app shell ───────────────────────────────────────────
  if (isAuthenticated) {
    return (
      <div className="flex h-screen flex-col">
        <Header onMenuToggle={() => setSidebarOpen((o) => !o)} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          {/* key re-triggers the fade animation on every navigation */}
          <main
            key={pathname}
            className="page-enter flex-1 overflow-y-auto bg-gray-50 p-4 sm:p-6"
          >
            {children}
          </main>
        </div>
      </div>
    );
  }

  // ── Public shell ──────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      <PublicHeader />
      <main
        key={pathname}
        className="page-enter mx-auto max-w-5xl px-4 py-6 sm:py-8"
      >
        {children}
      </main>
    </div>
  );
}
