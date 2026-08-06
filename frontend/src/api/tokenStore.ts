/**
 * Holds the current access/refresh tokens outside of React state, so the
 * axios interceptors in client.ts (which are not React components) can
 * read and update them without a circular import against AuthContext.
 *
 * Storage strategy: the backend has no cookie support at all - it returns
 * both tokens as plain JSON and expects `Authorization: Bearer <access>`
 * on every request, so httpOnly cookies simply aren't an option here
 * without backend changes. Given that constraint:
 *   - the access token lives in memory only (this module's variable) and
 *     is never written to disk, so it doesn't survive a page reload;
 *   - the refresh token is mirrored to localStorage, so a page reload can
 *     silently obtain a new access token (see AuthContext's bootstrap
 *     effect) instead of forcing the user to log in again.
 * The tradeoff: a refresh token sitting in localStorage is readable by any
 * script that gets injected via XSS. That risk is bounded by the backend's
 * existing input validation/output escaping, but is worth knowing about -
 * moving to httpOnly cookies later would remove it entirely, at the cost
 * of the backend also needing to set/rotate cookies and add CSRF defenses.
 */

const REFRESH_TOKEN_STORAGE_KEY = "itonit.refreshToken";

type ClearListener = () => void;

let accessToken: string | null = null;
let refreshToken: string | null = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);

const clearListeners = new Set<ClearListener>();

export const tokenStore = {
  getAccessToken(): string | null {
    return accessToken;
  },

  getRefreshToken(): string | null {
    return refreshToken;
  },

  /** Called on successful login and on every successful silent refresh. */
  setTokens(next: { access: string; refresh: string }): void {
    accessToken = next.access;
    refreshToken = next.refresh;
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, next.refresh);
  },

  /**
   * Called on explicit logout, and internally whenever a silent refresh
   * fails (e.g. the refresh token itself expired) - notifies subscribers
   * so AuthContext's own state stays in sync even when the clear happens
   * deep inside an unrelated API call, not through logout().
   */
  clear(): void {
    accessToken = null;
    refreshToken = null;
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    clearListeners.forEach((listener) => listener());
  },

  subscribeToClear(listener: ClearListener): () => void {
    clearListeners.add(listener);
    return () => clearListeners.delete(listener);
  },
};
