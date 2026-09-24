import { createContext } from "react";
import type { CompanyRegisterRequest, CurrentUser } from "../types/auth";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  user: CurrentUser | null;
  status: AuthStatus;
  error: string | null;
  login: (companyCode: string, username: string, password: string) => Promise<void>;
  /** POST /platform/login - the System Administrator equivalent of login()
   * above, with no company code/resolution at all. Shares every other piece
   * of session infrastructure (tokenStore, the apiClient refresh
   * interceptor, GET /auth/me, logout) with tenant login unchanged - see
   * AuthProvider's implementation. */
  loginPlatform: (username: string, password: string) => Promise<void>;
  registerCompany: (payload: CompanyRegisterRequest) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
