import axios from "axios";
import { getToken, removeToken } from "@/utils/token";

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

// Response interceptor: handle 401 (unauthorized)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      removeToken();
      // Redirect to login if not already there
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default api;
