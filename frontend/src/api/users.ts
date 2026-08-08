import { apiClient } from "./client";
import type { AdminUser, AdminUserCreate, AdminUserUpdate } from "../types/user";
import type { DataResponse } from "../types/response";

export interface UserListParams {
  role_id?: number;
  department_id?: number;
  is_active?: boolean;
  search?: string;
  skip?: number;
  limit?: number;
}

/** GET /users is wrapped in the {data, msg} envelope. Company Administrator only. */
export async function fetchUsers(params: UserListParams): Promise<AdminUser[]> {
  const { data } = await apiClient.get<DataResponse<AdminUser[]>>("/users", { params });
  return data.data;
}

/** POST /users - Company-Administrator-only. */
export async function createUser(payload: AdminUserCreate): Promise<AdminUser> {
  const { data } = await apiClient.post<DataResponse<AdminUser>>("/users", payload);
  return data.data;
}

/** PATCH /users/{id} - Company Administrator may set any field (enforced server-side). */
export async function updateUser(userId: number, payload: AdminUserUpdate): Promise<AdminUser> {
  const { data } = await apiClient.patch<DataResponse<AdminUser>>(`/users/${userId}`, payload);
  return data.data;
}

/** PATCH /users/{id}/password - Company-Administrator-only, no current password required. */
export async function adminSetPassword(userId: number, newPassword: string): Promise<void> {
  await apiClient.patch(`/users/${userId}/password`, { new_password: newPassword });
}
