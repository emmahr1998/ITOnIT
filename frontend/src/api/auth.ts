import { apiClient } from "./client";
import type {
  CompanyCodeRequest,
  CompanyRegisterRequest,
  CompanyResolveResponse,
  CurrentUser,
  LoginRequest,
  TokenResponse,
} from "../types/auth";

export async function resolveCompanyRequest(
  payload: CompanyCodeRequest,
): Promise<CompanyResolveResponse> {
  const { data } = await apiClient.post<CompanyResolveResponse>(
    "/auth/resolve-company",
    payload,
  );
  return data;
}

export async function loginRequest(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
  return data;
}

export async function registerCompanyRequest(
  payload: CompanyRegisterRequest,
): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/companies/register", payload);
  return data;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const { data } = await apiClient.get<CurrentUser>("/auth/me");
  return data;
}
