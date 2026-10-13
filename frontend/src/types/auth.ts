/**
 * Types below mirror the backend's Pydantic schemas exactly
 * (backend/app/schemas/auth.py) - field names and shapes must stay in sync
 * with that file, not the other way around.
 */

/** The only four roles that exist (backend/app/scripts/seed_initial_data.py). */
export type Role = "Employee" | "Technician" | "Company Administrator" | "System Administrator";

/** POST /auth/resolve-company request body. */
export interface CompanyCodeRequest {
  company_code: string;
}

/**
 * POST /auth/resolve-company response body - just enough for the login
 * screen to display which company a code belongs to.
 */
export interface CompanyResolveResponse {
  company_name: string;
  company_logo: string | null;
}

/** POST /auth/login request body. */
export interface LoginRequest {
  company_code: string;
  username: string;
  password: string;
}

/**
 * POST /companies/register request body (backend/app/schemas/company.py -
 * CompanyRegisterRequest). Deliberately has no role_id, company_id, or
 * company_code field - the backend always creates a brand new company,
 * always generates its company_code itself, and makes this the first
 * Company Administrator within it, regardless of anything the client
 * sends. Replaces the old POST /auth/register self-registration flow,
 * which always created a bare, company-less Employee account.
 *
 * System Administrator provisioning (POST /platform/companies), which does
 * need an explicit code, uses its own PlatformCompanyRegisterRequest below
 * instead of this type.
 */
export interface CompanyRegisterRequest {
  company_name: string;
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  password: string;
}

/**
 * POST /platform/companies request body
 * (backend/app/schemas/company.py - PlatformCompanyRegisterRequest).
 * System-Administrator-only: extends the public registration fields with a
 * required company_code, since a System Administrator provisioning a
 * tenant on a customer's behalf chooses it explicitly (see
 * PlatformCreateCompanyPage).
 */
export interface PlatformCompanyRegisterRequest extends CompanyRegisterRequest {
  company_code: string;
}

/**
 * POST /companies/register response body - the same tokens as TokenResponse,
 * plus the company_code the new company actually ended up with (always
 * system-generated for this endpoint - see CompanyRegisterRequest's own
 * docstring), so the registration UI can show it to the new Company
 * Administrator.
 */
export interface CompanyRegisterResponse extends TokenResponse {
  company_code: string;
}

/** POST /auth/login response body. */
export interface TokenResponse {
  access: string;
  refresh: string;
  token_type: string;
}

/** POST /auth/refresh request body. */
export interface RefreshRequest {
  refresh: string;
}

/** POST /auth/refresh response body - a new access token only. */
export interface RefreshResponse {
  access: string;
  token_type: string;
}

/** GET /auth/me response body. */
export interface CurrentUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  role: Role;
}
