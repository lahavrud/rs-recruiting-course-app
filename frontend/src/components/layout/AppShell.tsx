import { type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";
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

/* ── Public footer ───────────────────────────────────────────────────────── */
export function PublicFooter() {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-white/8 bg-void">
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 px-6 py-8 sm:flex-row sm:justify-between">
        <Link to="/" className="shrink-0">
          <Logo size={24} />
        </Link>
        <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-white/30">
          <Link to="/jobs"    className="transition hover:text-white/60">{t("nav.jobs")}</Link>
          <Link to="/about"   className="transition hover:text-white/60">{t("nav.about")}</Link>
          <Link to="/contact" className="transition hover:text-white/60">{t("nav.contact")}</Link>
        </nav>
        <p className="text-xs text-white/20">
          &copy; {new Date().getFullYear()}{" "}
          <span className="text-copper/60">RS Recruiting</span>.{" "}
          {t("landing.footer.copyright")}
        </p>
      </div>
    </footer>
  );
}

/* ── Public header ───────────────────────────────────────────────────────── */
export function PublicHeader({ transparent = false }: { transparent?: boolean }) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);
  // When transparent=true, track scroll to solidify the bar
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  useEffect(() => {
    if (!transparent) return;
    const onScroll = () => setScrolled(window.scrollY > 60);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [transparent]);

  const links = [
    { to: "/jobs",    label: t("nav.jobs") },
    { to: "/about",   label: t("nav.about") },
    { to: "/contact", label: t("nav.contact") },
  ];

  // Glass style (landing page at top): white-tinted frosted glass
  // Solid style (all other pages, or after scrolling): dark void bar
  const solid = !transparent || scrolled;

  return (
    <>
      {/* ── Navbar — full-width, fixed to top ─────────────────────────── */}
      <header
        className="fixed inset-x-0 top-0 z-40 transition-all duration-300"
        style={{
          background: solid
            ? "color-mix(in srgb, var(--color-void) 95%, transparent)"
            : "rgba(255,255,255,0.06)",
          backdropFilter: "blur(12px)",
          borderBottom: solid
            ? "1px solid rgba(255,255,255,0.06)"
            : "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <Logo size={26} />
            <span className="font-wordmark text-[15px] tracking-widest text-gold/60 transition hover:text-gold/90">
              RS Recruiting
            </span>
          </Link>

          {/* Desktop links */}
          <nav className="hidden items-center gap-6 sm:flex">
            {links.map((l) => (
              <Link key={l.to} to={l.to}
                className="text-sm text-white/45 transition hover:text-white/80">
                {l.label}
              </Link>
            ))}
            {isAuthenticated ? (
              <Link to="/dashboard"
                className="rounded-sm border border-white/18 px-4 py-1.5 text-sm text-white/60 transition hover:border-white/35 hover:text-white/90">
                {t("nav.dashboard")}
              </Link>
            ) : (
              <Link to="/login"
                className="rounded-sm border border-copper/40 px-4 py-1.5 text-sm text-copper/80 transition hover:border-copper/70 hover:text-copper">
                {t("auth.login.submitText")}
              </Link>
            )}
          </nav>

          {/* Mobile hamburger */}
          <button
            onClick={() => setOpen(true)}
            aria-label={t("nav.menu")}
            className="flex size-9 flex-col items-center justify-center gap-[5px] sm:hidden"
          >
            <span className="block h-px w-5 rounded-full bg-white/55" />
            <span className="block h-px w-5 rounded-full bg-white/55" />
            <span className="block h-px w-3.5 self-end rounded-full bg-white/55" />
          </button>
        </div>
      </header>

      {/* ── Mobile overlay — portal to document.body so it's never clipped ── */}
      {createPortal(
        <div
          className="fixed inset-0 z-50 flex flex-col bg-void"
          style={{
            opacity: open ? 1 : 0,
            pointerEvents: open ? "auto" : "none",
            visibility: open ? "visible" : "hidden",
            transition: "opacity 0.25s ease",
          }}
        >
          {/* Top bar */}
          <div className="flex items-center justify-between border-b border-white/8 px-5 py-3.5">
            <Link to="/" onClick={() => setOpen(false)} className="flex items-center gap-2.5">
              <Logo size={26} />
              <span className="font-wordmark text-[15px] font-light tracking-widest text-gold/55">
                RS Recruiting
              </span>
            </Link>
            <button
              onClick={() => setOpen(false)}
              aria-label={t("common.close")}
              className="flex size-9 items-center justify-center text-white/35 transition hover:text-white/70"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth={1.5} className="size-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Links */}
          <nav className="flex flex-1 flex-col justify-center px-7">
            {links.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setOpen(false)}
                className="group flex items-center justify-between border-b border-white/8 py-6 text-2xl font-light text-white/60 transition-colors hover:text-white"
              >
                {l.label}
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth={1.5}
                  className="size-4 text-copper/35 transition-transform duration-200 group-hover:-translate-x-1">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
                </svg>
              </Link>
            ))}

            {isAuthenticated ? (
              <Link to="/dashboard" onClick={() => setOpen(false)}
                className="mt-8 self-start rounded-sm border border-copper/40 px-6 py-2.5 text-sm text-copper transition hover:bg-copper/10">
                {t("nav.dashboard")}
              </Link>
            ) : (
              <Link to="/login" onClick={() => setOpen(false)}
                className="mt-8 self-start rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold">
                {t("auth.login.submitText")}
              </Link>
            )}
          </nav>

          <p className="px-7 py-6 text-xs text-white/18">
            &copy; {new Date().getFullYear()} RS Recruiting
          </p>
        </div>,
        document.body
      )}
    </>
  );
}

/* ── Shell ───────────────────────────────────────────────────────────────── */
function ShellContent({ children }: Props) {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Auth pages manage their own full-screen layout
  if (
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

  // Hero pages start their own full-bleed section from y=0 (navbar floats over it)
  const heroRoutes = new Set(["/", "/about", "/contact", "/jobs"]);
  // Single-screen pages: constrain to viewport height so nothing scrolls
  const singleScreenRoutes = new Set(["/contact"]);

  // All public pages: single shell — header and footer owned here (DRY)
  return (
    <div className={`flex flex-col bg-void ${singleScreenRoutes.has(pathname) ? "h-dvh overflow-hidden" : "min-h-screen"}`}>
      <PublicHeader transparent={heroRoutes.has(pathname)} />
      {/* flex flex-col so children can use flex-1 to fill remaining height */}
      <main key={pathname} className="page-enter flex flex-1 flex-col">
        {children}
      </main>
      <PublicFooter />
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
