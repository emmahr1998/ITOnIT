import type { Role } from "./auth";
import type { Department } from "./department";

/** Mirrors backend/app/schemas/user.py UserResponse. */
export interface AdminUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string | null;
  department: Department | null;
  role: Role;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * PATCH /users/{id} request body (backend/app/schemas/user.py UserUpdate) -
 * only the Administrator-editable fields this app's admin UI uses.
 */
export interface AdminUserUpdate {
  username?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  phone_number?: string | null;
  department_id?: number | null;
  role_id?: number;
  is_active?: boolean;
}

/** POST /users request body (backend/app/schemas/user.py UserCreate). Administrator-only. */
export interface AdminUserCreate {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  department_id?: number | null;
  phone_number?: string | null;
  password: string;
  role_id: number;
}

/**
 * Roles a Company Administrator can assign to a user they create/edit.
 * Excludes "System Administrator" - the backend refuses to assign it
 * through user management at all.
 */
export type AssignableRole = Exclude<Role, "System Administrator">;

/**
 * GET /roles item (backend/app/schemas/role.py RoleResponse). Role ids
 * depend on install history and must always come from GET /roles - never
 * hardcode them. A hardcoded name->id map was the cause of "Technician
 * saves as Employee" (and "Employee saves as System Administrator").
 */
export interface RoleOption {
  id: number;
  name: AssignableRole;
}
