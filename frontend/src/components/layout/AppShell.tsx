import { type ReactNode, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { ToastProvider } from "@/contexts/ToastContext";
import Header from "./Header";
import Sidebar from "./Sidebar";
import Logo from "@/components/ui/Logo";
import Toaster from "@/components/ui/Toaster";

interface Props {
  children: ReactNode;
}

export function PublicHeader() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();

  return (
    <header className="border-b border-white/8 bg-void">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center gap-2.5">
          <Logo size={28} />
          <span className="text-sm font-medium tracking-wide text-white/60 transition hover:text-white/85">
            {t("auth.appName")}
          </span>
        </Link>
        <nav className="flex items-center gap-5">
          <Link
            to="/jobs"
            className="text-sm text-white/40 transition hover:text-white/70"
          >
            {t("nav.jobs")}
          </Link>
          <Link
            to="/about"
            className="text-sm text-white/40 transition hover:text-white/70"
          >
            {t("nav.about")}
          </Link>
          <Link
            to="/contact"
            className="text-sm text-white/40 transition hover:text-white/70"
          >
            {t("nav.contact")}
          </Link>
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="rounded-sm border border-white/20 px-4 py-1.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
            >
              {t("nav.dashboard")}
            </Link>
          ) : (
            <Link
              to="/login"
              className="rounded-sm border border-white/20 px-4 py-1.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
            >
              {t("auth.login.submitText")}
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

function ShellContent({ children }: Props) {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (
    pathname === "/" ||
    pathname === "/about" ||
    pathname === "/login" ||
    pathname === "/register" ||
    pathname === "/forgot-password" ||
    pathname === "/reset-password"
  ) {
    return <>{children}</>;
  }

  if (isAuthenticated) {
    return (
      <div className="flex h-screen flex-col">
        <Header onMenuToggle={() => setSidebarOpen((o) => !o)} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          {/* key={pathname} unmounts/remounts on every navigation to trigger the
              page-enter animation. Routes must not rely on cross-page state. */}
          <main
            key={pathname}
            className="page-enter flex-1 overflow-y-auto bg-page p-4 sm:p-6"
          >
            {children}
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-page">
      <PublicHeader />
      {/* key={pathname}: same as authenticated shell above — triggers page-enter animation on navigation */}
      <main key={pathname} className="page-enter mx-auto max-w-4xl px-6 py-10 sm:py-14">
        {children}
      </main>
    </div>
  );
}

export default function AppShell({ children }: Props) {
  return (
    <ToastProvider>
      <ShellContent>{children}</ShellContent>
      <Toaster />
    </ToastProvider>
  );
}
