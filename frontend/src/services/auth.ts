import api from "@/services/api";
import type {
  InviteMetadataPublic,
  LoginRequest,
  TokenResponse,
  UserWithCompanyRead,
} from "@/types/api";
import {
  getRefreshToken,
  removeRefreshToken,
  removeToken,
  setRefreshToken,
  setToken,
} from "@/utils/token";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", credentials);
  setToken(response.data.access_token);
  setRefreshToken(response.data.refresh_token);
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
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  const response = await api.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  setToken(response.data.access_token);
  setRefreshToken(response.data.refresh_token);
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

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  try {
    await api.post("/auth/logout", refreshToken ? { refresh_token: refreshToken } : null);
  } catch {
    // Best-effort server-side revocation — always clear local state
  } finally {
    removeToken();
    removeRefreshToken();
    window.location.href = "/login";
  }
}
