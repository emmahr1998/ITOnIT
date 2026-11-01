import { apiClient } from "./client";
import type { RoleOption } from "../types/user";
import type { DataResponse } from "../types/response";

/**
 * GET /roles - Company-Administrator-only. The roles user management may
 * assign (never System Administrator), with their real database ids. Role
 * ids differ between installs, so this is the only valid source of role_id.
 */
export async function fetchAssignableRoles(): Promise<RoleOption[]> {
  const { data } = await apiClient.get<DataResponse<RoleOption[]>>("/roles");
  return data.data;
}
