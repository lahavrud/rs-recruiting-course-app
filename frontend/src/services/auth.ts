import api from "@/services/api";
import type {
  InviteMetadataPublic,
  LoginRequest,
  TokenResponse,
  UserWithCompanyRead,
} from "@/types/api";
import { getToken, removeToken, setToken } from "@/utils/token";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", credentials);
  setToken(response.data.access_token);
  return response.data;
}

export async function register(
  formData: FormData,
  inviteToken: string,
): Promise<UserWithCompanyRead> {
  const response = await api.post<UserWithCompanyRead>("/auth/register", formData, {
    params: { token: inviteToken },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function refreshTokens(): Promise<TokenResponse> {
  // Refresh token is an HttpOnly cookie — browser sends it automatically.
  const response = await api.post<TokenResponse>("/auth/refresh");
  setToken(response.data.access_token);
  return response.data;
}

export async function getInviteMetadata(
  token: string,
): Promise<InviteMetadataPublic> {
  const res = await api.get<InviteMetadataPublic>(`/auth/invite/${token}`);
  return res.data;
}

export async function activateAccount(token: string): Promise<void> {
  await api.post(`/auth/activate`, null, {
    params: { token },
  });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await api.post("/auth/forgot-password", { email });
}

export async function validateResetToken(token: string): Promise<void> {
  await api.get("/auth/reset-password/validate", { params: { token } });
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<void> {
  await api.post("/auth/reset-password", {
    token,
    new_password: newPassword,
  });
}

export function logout(): void {
  // Capture access token BEFORE clearing — the server endpoint requires it for
  // auth. The refresh token is an HttpOnly cookie sent automatically by the
  // browser; the server clears it via Set-Cookie on the response.
  const accessToken = getToken();
  removeToken();
  // Best-effort server-side revocation. We use `fetch` with `keepalive: true`
  // instead of axios so the request survives the navigation that almost
  // always follows logout() — otherwise Firefox cancels it mid-flight and
  // logs `NS_BINDING_ABORTED`.
  const baseURL = import.meta.env.DEV
    ? ""
    : (import.meta.env.VITE_API_BASE_URL ?? "");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  try {
    void fetch(`${baseURL}/auth/logout`, {
      method: "POST",
      keepalive: true,
      credentials: "same-origin",
      headers,
    }).catch(() => {});
  } catch {
    // sendBeacon-style fire-and-forget — swallow sync errors too
  }
}
