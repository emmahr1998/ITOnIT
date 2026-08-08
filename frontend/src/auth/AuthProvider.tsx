import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchCurrentUser, loginRequest, registerCompanyRequest } from "../api/auth";
import { getApiErrorMessage } from "../api/client";
import { tokenStore } from "../api/tokenStore";
import type { CompanyRegisterRequest, CurrentUser } from "../types/auth";
import { AuthContext, type AuthStatus } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  // Bootstrap on app load: a refresh token surviving in localStorage means
  // we can silently obtain a fresh access token and reload the user,
  // instead of forcing a full re-login on every page reload.
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (!tokenStore.getRefreshToken()) {
        setStatus("unauthenticated");
        return;
      }
      try {
        // There is no access token yet at this point, so this call is
        // expected to 401 once - apiClient's response interceptor catches
        // that, silently refreshes using the stored refresh token, and
        // retries this same request automatically.
        const currentUser = await fetchCurrentUser();
        if (!cancelled) {
          setUser(currentUser);
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) {
          tokenStore.clear();
          setStatus("unauthenticated");
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // If a silent refresh fails deep inside some unrelated API call (the
  // refresh token itself expired), tokenStore.clear() fires without ever
  // going through logout() - this keeps this context's own state in sync
  // with that, so protected routes redirect correctly.
  useEffect(() => {
    return tokenStore.subscribeToClear(() => {
      setUser(null);
      setStatus("unauthenticated");
    });
  }, []);

  const login = useCallback(async (companyCode: string, username: string, password: string) => {
    setError(null);
    try {
      const tokens = await loginRequest({ company_code: companyCode, username, password });
      tokenStore.setTokens({ access: tokens.access, refresh: tokens.refresh });
      const currentUser = await fetchCurrentUser();
      setUser(currentUser);
      setStatus("authenticated");
    } catch (err) {
      tokenStore.clear();
      setStatus("unauthenticated");
      setError(getApiErrorMessage(err, "Login failed. Please try again."));
      throw err;
    }
  }, []);

  const registerCompany = useCallback(async (payload: CompanyRegisterRequest) => {
    setError(null);
    try {
      const tokens = await registerCompanyRequest(payload);
      tokenStore.setTokens({ access: tokens.access, refresh: tokens.refresh });
      const currentUser = await fetchCurrentUser();
      setUser(currentUser);
      setStatus("authenticated");
    } catch (err) {
      tokenStore.clear();
      setStatus("unauthenticated");
      setError(getApiErrorMessage(err, "Company registration failed. Please try again."));
      throw err;
    }
  }, []);

  const value = useMemo(
    () => ({ user, status, error, login, registerCompany, logout }),
    [user, status, error, login, registerCompany, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
