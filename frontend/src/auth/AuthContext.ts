import { createContext } from "react";
import type { CompanyRegisterRequest, CurrentUser } from "../types/auth";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  user: CurrentUser | null;
  status: AuthStatus;
  error: string | null;
  login: (companyCode: string, username: string, password: string) => Promise<void>;
  registerCompany: (payload: CompanyRegisterRequest) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
