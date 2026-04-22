import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/api";

interface NavItem {
  label: string;
  to: string;
}

const adminNav: NavItem[] = [
  { label: "Dashboard", to: "/" },
  { label: "Companies", to: "/admin/companies" },
  { label: "Jobs", to: "/admin/jobs" },
  { label: "Applications", to: "/admin/applications" },
  { label: "Candidates", to: "/admin/candidates" },
];

const companyNav: NavItem[] = [
  { label: "Dashboard", to: "/" },
  { label: "Job Board", to: "/jobs" },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user } = useAuth();
  const navItems = user?.role === UserRole.ADMIN ? adminNav : companyNav;

  // Close sidebar when route changes on mobile (via click on nav link)
  // also close on Escape key
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const navContent = (
    <nav className="flex-1 space-y-1 p-4">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={onClose}
          className={({ isActive }) =>
            `block rounded-md px-3 py-2 text-sm font-medium ${
              isActive
                ? "bg-blue-50 text-blue-700"
                : "text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            }`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <>
      {/* ── Mobile: backdrop + drawer ── */}
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`
          fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r border-gray-200
          bg-white transition-transform duration-200 ease-in-out
          md:static md:translate-x-0 md:bg-gray-50
          ${isOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        {/* Mobile: close button inside drawer */}
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 md:hidden">
          <span className="text-sm font-semibold text-gray-700">Menu</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-gray-500 hover:bg-gray-100"
            aria-label="Close navigation"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        {navContent}
      </aside>
    </>
  );
}
