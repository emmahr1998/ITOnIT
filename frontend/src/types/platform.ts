/**
 * Types below mirror the backend's Pydantic schemas exactly
 * (backend/app/schemas/platform.py) - field names and shapes must stay in
 * sync with that file, not the other way around.
 */

/** POST /platform/login request body. No company_code - this resolves the
 * one platform-level System Administrator account, not a tenant user. */
export interface PlatformLoginRequest {
  username: string;
  password: string;
}

/** One row of GET /platform/companies, and each entry of
 * GET /platform/overview's recent_companies. */
export interface PlatformCompanySummary {
  id: number;
  name: string;
  company_code: string;
  is_active: boolean;
  contact_email: string | null;
  timezone: string;
  language: string;
  created_at: string;
}

/** GET /platform/companies/{id} and POST /platform/companies response data. */
export interface PlatformCompanyDetail extends PlatformCompanySummary {
  updated_at: string;
  user_count: number;
  ticket_count: number;
  inventory_item_count: number;
}

/** GET /platform/overview. total_users is tenant users only - the System
 * Administrator's own account is excluded by the backend (see
 * UserRepository.count_all_tenant_users). */
export interface PlatformOverview {
  total_companies: number;
  active_companies: number;
  inactive_companies: number;
  total_users: number;
  recent_companies: PlatformCompanySummary[];
}

/** GET /platform/companies query params. */
export interface PlatformCompanyListParams {
  search?: string;
  is_active?: boolean;
  sort_by?: "created_at" | "name" | "company_code";
  sort_dir?: "asc" | "desc";
  skip?: number;
  limit?: number;
}

/**
 * GET /platform/companies response - a platform-specific list envelope, not
 * the generic DataResponse<T> (types/response.ts). `total` is the filtered
 * count (search/is_active applied, skip/limit not applied) - see
 * backend/app/schemas/platform.py's CompanyListResponse docstring.
 */
export interface PlatformCompanyListResponse {
  data: PlatformCompanySummary[];
  total: number;
  msg: string;
}
