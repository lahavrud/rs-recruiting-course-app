import axios from "axios";
import { getRefreshToken, getToken, removeRefreshToken, removeToken, setRefreshToken, setToken } from "@/utils/token";

/**
 * Axios instance configured for the backend API.
 *
 * In development, Vite proxies /auth and /api to the backend,
 * so we use an empty baseURL (relative paths).
 * In production, set VITE_API_BASE_URL to the backend origin.
 */
const baseURL = import.meta.env.DEV ? "" : import.meta.env.VITE_API_BASE_URL || "";

const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: attach JWT token
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

function drainQueue(newToken: string) {
  refreshQueue.forEach((resolve) => resolve(newToken));
  refreshQueue = [];
}

function clearSession() {
  removeToken();
  removeRefreshToken();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// Response interceptor: on 401, attempt token refresh before giving up
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      !axios.isAxiosError(error) ||
      error.response?.status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.includes("/auth/refresh") ||
      originalRequest.url?.includes("/auth/login") ||
      originalRequest.url?.includes("/auth/logout")
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise((resolve) => {
        refreshQueue.push((token: string) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(api(originalRequest));
        });
      });
    }

    isRefreshing = true;
    const refreshToken = getRefreshToken();

    if (!refreshToken) {
      isRefreshing = false;
      clearSession();
      return Promise.reject(error);
    }

    try {
      const response = await axios.post(`${baseURL}/auth/refresh`, {
        refresh_token: refreshToken,
      });
      const { access_token, refresh_token } = response.data;
      setToken(access_token);
      setRefreshToken(refresh_token);
      drainQueue(access_token);
      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return api(originalRequest);
    } catch {
      clearSession();
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;
