import { apiClient } from "./client";
import type { CompanyRegisterRequest, TokenResponse } from "../types/auth";
import type { DataResponse } from "../types/response";
import type {
  PlatformCompanyDetail,
  PlatformCompanyListParams,
  PlatformCompanyListResponse,
  PlatformLoginRequest,
  PlatformOverview,
} from "../types/platform";

/** POST /platform/login. Returns the same {access, refresh, token_type}
 * shape as POST /auth/login - see AuthProvider's loginPlatform for how the
 * token/session machinery is shared, not duplicated, between the two. */
export async function loginPlatformRequest(payload: PlatformLoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/platform/login", payload);
  return data;
}

export async function fetchPlatformOverview(): Promise<PlatformOverview> {
  const { data } = await apiClient.get<DataResponse<PlatformOverview>>("/platform/overview");
  return data.data;
}

/** GET /platform/companies - server-driven search/filter/sort/pagination.
 * The response's `total` (not len(data)) is the filtered count to page
 * against; see PlatformCompanyListResponse's own docstring. */
export async function fetchPlatformCompanies(
  params: PlatformCompanyListParams,
): Promise<PlatformCompanyListResponse> {
  const { data } = await apiClient.get<PlatformCompanyListResponse>("/platform/companies", { params });
  return data;
}

export async function fetchPlatformCompanyDetail(companyId: number): Promise<PlatformCompanyDetail> {
  const { data } = await apiClient.get<DataResponse<PlatformCompanyDetail>>(
    `/platform/companies/${companyId}`,
  );
  return data.data;
}

export async function activatePlatformCompany(companyId: number): Promise<PlatformCompanyDetail> {
  const { data } = await apiClient.patch<DataResponse<PlatformCompanyDetail>>(
    `/platform/companies/${companyId}/activate`,
  );
  return data.data;
}

export async function deactivatePlatformCompany(companyId: number): Promise<PlatformCompanyDetail> {
  const { data } = await apiClient.patch<DataResponse<PlatformCompanyDetail>>(
    `/platform/companies/${companyId}/deactivate`,
  );
  return data.data;
}

/**
 * POST /platform/companies. Reuses the exact same CompanyRegisterRequest
 * shape as self-service registration - sends only the seven fields that
 * type defines, never company_id/role_id. Deliberately not routed through
 * AuthContext.registerCompany: the response has no tokens at all (a System
 * Administrator provisioning a company is never signed in as its new
 * admin), so this is a plain data call like every other function here.
 */
export async function createPlatformCompany(
  payload: CompanyRegisterRequest,
): Promise<PlatformCompanyDetail> {
  const { data } = await apiClient.post<DataResponse<PlatformCompanyDetail>>(
    "/platform/companies",
    payload,
  );
  return data.data;
}
