/**
 * Types below mirror the backend's Pydantic schemas exactly
 * (backend/app/schemas/auth.py) - field names and shapes must stay in sync
 * with that file, not the other way around.
 */

/** The only four roles that exist (backend/app/scripts/seed_initial_data.py). */
export type Role = "Employee" | "Technician" | "Manager" | "Administrator";

/** POST /auth/login request body. */
export interface LoginRequest {
  username: string;
  password: string;
}

/**
 * POST /auth/register request body. Deliberately has no role_id field - the
 * backend always creates a self-registered account as an Employee.
 */
export interface RegisterRequest {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
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
