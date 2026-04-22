import { useAuth } from "@/hooks/useAuth";

interface HeaderProps {
  onMenuToggle: () => void;
}

export default function Header({ onMenuToggle }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 sm:px-6">
      <div className="flex items-center gap-3">
        {/* Hamburger — visible only on mobile */}
        <button
          type="button"
          onClick={onMenuToggle}
          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 md:hidden"
          aria-label="Toggle navigation"
        >
          <svg
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
        <h1 className="text-base font-semibold text-gray-900 sm:text-lg">RS Recruitment</h1>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <span className="hidden max-w-[140px] truncate text-sm text-gray-600 sm:block">
          {user?.email}
        </span>
        <span className="hidden rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700 sm:inline-block">
          {user?.role}
        </span>
        <button
          onClick={logout}
          className="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
