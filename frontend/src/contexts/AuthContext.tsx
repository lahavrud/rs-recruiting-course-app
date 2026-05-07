import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";
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
    // Clear tokens and navigate without calling setUser(null) — if we set
    // user=null first, React re-renders AdminRoute which fires <Navigate to="/login">
    // before the browser starts the page replacement, causing a flash.
    // Skipping setUser(null) is safe: the page reloads and getInitialUser()
    // finds no token, so the app starts cleanly with user=null.
    logoutService();
    window.location.replace("/");
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      login,
      logout,
    }),
    [user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
