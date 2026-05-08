import { createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { login as loginService, logout as logoutService } from "@/services/auth";
import type { JwtPayload, LoginRequest } from "@/types/api";
import type { UserRole } from "@/types/api";
import { decodeToken, getToken } from "@/utils/token";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
}

export interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  /** True while logout is in progress. Route guards render null instead of
   *  redirecting so the page-replacement completes without a /login flash. */
  loggingOut: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextType | null>(null);

function payloadToUser(payload: JwtPayload): AuthUser {
  return {
    id: payload.sub,
    email: payload.email,
    role: payload.role,
  };
}

/**
 * Resolve initial auth state synchronously from localStorage.
 * getToken() and decodeToken() are synchronous (localStorage + base64),
 * so there's no need for an async effect or loading state.
 */
function getInitialUser(): AuthUser | null {
  const token = getToken();
  if (token) {
    const payload = decodeToken(token);
    if (payload) {
      return payloadToUser(payload);
    }

    logoutService();
  }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(getInitialUser);
  const [loggingOut, setLoggingOut] = useState(false);
  const logoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (logoutTimerRef.current !== null) clearTimeout(logoutTimerRef.current);
    };
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await loginService(credentials);
    const payload = decodeToken(response.access_token);

    if (!payload) {
      logoutService();
      throw new Error("Authentication failed: invalid access token");
    }

    setUser(payloadToUser(payload));
  }, []);

  const logout = useCallback(() => {
    // Set loggingOut first so route guards render null instead of redirecting to
    // /login — prevents a flash of the login page while the browser replaces the
    // document.  After that, clear tokens and user state before navigating so
    // guards never see a stale "logged-in" user if the redirect stalls.
    setLoggingOut(true);
    logoutService();
    setUser(null);
    window.location.replace("/");
    // Safety valve: if navigation is blocked (e.g. browser extension), reset
    // the sentinel so route guards can fall through to /login on their own.
    logoutTimerRef.current = setTimeout(() => setLoggingOut(false), 500);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      loggingOut,
      login,
      logout,
    }),
    [user, loggingOut, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
