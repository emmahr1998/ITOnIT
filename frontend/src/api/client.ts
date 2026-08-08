import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { tokenStore } from "./tokenStore";

/**
 * Environment-based backend URL (Vite requirement) - never hardcode the
 * backend origin anywhere else in the app; import API_BASE_URL/apiClient
 * from here instead.
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

/**
 * Turns a backend-relative asset path (e.g. a company logo's `/companies/
 * {id}/logo`) into a URL the browser can actually fetch. The one place this
 * concatenation happens - never repeat `${API_BASE_URL}${path}` elsewhere.
 * Already-absolute URLs pass through unchanged, which keeps this safe to
 * call on a field that might someday point somewhere other than this API.
 */
export function resolveAssetUrl(path: string | null | undefined): string | undefined {
  if (!path) {
    return undefined;
  }
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

/** Attaches the current access token to every outgoing request, if present. */
apiClient.interceptors.request.use((config) => {
  const token = tokenStore.getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retriedAfterRefresh?: boolean;
}

/**
 * At most one /auth/refresh call is ever in flight at a time - if several
 * requests 401 at once (e.g. a page that fires multiple calls on load),
 * they all await this same promise instead of each triggering their own
 * refresh.
 */
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.getRefreshToken();
  if (!refresh) {
    return null;
  }
  try {
    // A plain axios call, not apiClient - this must never go through the
    // response interceptor below (that would recurse on a failed refresh).
    const { data } = await axios.post<{ access: string; token_type: string }>(
      `${API_BASE_URL}/auth/refresh`,
      { refresh },
    );
    tokenStore.setTokens({ access: data.access, refresh });
    return data.access;
  } catch {
    tokenStore.clear();
    return null;
  }
}

/**
 * Transparent refresh-on-401: any request made through apiClient that
 * fails with 401 gets exactly one retry, after a fresh access token has
 * been obtained via the refresh token. If that also fails (refresh token
 * itself expired/invalid), the original 401 is rethrown and tokenStore.clear()
 * has already fired, so AuthContext will react and redirect to /login.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;

    if (
      error.response?.status === 401 &&
      original &&
      !original._retriedAfterRefresh &&
      tokenStore.getRefreshToken()
    ) {
      original._retriedAfterRefresh = true;
      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null;
      });

      const newAccessToken = await refreshPromise;
      if (newAccessToken) {
        original.headers.set("Authorization", `Bearer ${newAccessToken}`);
        return apiClient(original);
      }
    }

    return Promise.reject(error);
  },
);

/** Extracts a human-readable message from a failed apiClient call. */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (!error.response) {
      return "Could not reach the server. Check your connection and try again.";
    }
  }
  return fallback;
}
