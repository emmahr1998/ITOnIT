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
  theme: string | null;
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
 * There is no GET /roles endpoint, and UserResponse only ever exposes a
 * role's name - never its id - yet PATCH /users/{id} requires role_id.
 * This mapping was confirmed by reading the seeded roles table directly
 * (read-only) rather than guessed: 1=Employee, 2=Technician, 3=Manager,
 * 4=Administrator. Roles are fixed, admin-managed-nowhere seed data, so
 * this is stable, but it is not a documented API contract.
 */
export const ROLE_ID_BY_NAME: Record<Role, number> = {
  Employee: 1,
  Technician: 2,
  Manager: 3,
  Administrator: 4,
};

export const ROLE_OPTIONS: Role[] = ["Employee", "Technician", "Manager", "Administrator"];
