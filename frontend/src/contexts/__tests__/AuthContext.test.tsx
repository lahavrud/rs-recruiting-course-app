import { render, screen } from "@testing-library/react";
import { useContext } from "react";
import { vi } from "vitest";
import { AuthContext, AuthProvider } from "@/contexts/AuthContext";
import { UserRole } from "@/types/api";

vi.mock("@sentry/react", () => ({ setUser: vi.fn() }));

const { mockLogout } = vi.hoisted(() => ({ mockLogout: vi.fn() }));
vi.mock("@/services/auth", () => ({
  login: vi.fn(),
  logout: mockLogout,
}));

const ACCESS_TOKEN_KEY = "access_token";

function makeJwt(payload: Record<string, unknown>): string {
  const toBase64Url = (obj: unknown) =>
    btoa(JSON.stringify(obj))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=/g, "");
  return `${toBase64Url({ alg: "HS256", typ: "JWT" })}.${toBase64Url(payload)}.fakesig`;
}

function Consumer() {
  const ctx = useContext(AuthContext);
  if (!ctx) return <div data-testid="no-ctx" />;
  return (
    <>
      <span data-testid="authenticated">{String(ctx.isAuthenticated)}</span>
      <span data-testid="role">{ctx.user?.role ?? "none"}</span>
    </>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockLogout.mockClear();
});

describe("AuthContext initial state", () => {
  it("populates user from a valid token in localStorage", () => {
    const token = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) + 3600,
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("role").textContent).toBe(UserRole.ADMIN);
  });

  it("sets user to null and clears localStorage for an expired token", () => {
    const token = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) - 1,
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("role").textContent).toBe("none");
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it("sets user to null with no side-effects when localStorage is empty", () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("role").textContent).toBe("none");
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(mockLogout).not.toHaveBeenCalled();
  });
});
