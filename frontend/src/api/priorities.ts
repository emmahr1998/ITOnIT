import { apiClient } from "./client";
import type { Priority } from "../types/priority";
import type { DataResponse } from "../types/response";

/**
 * GET /priorities is wrapped in the {data, msg} envelope. Priorities are
 * company-owned, admin-editable records (see the Priorities admin page) -
 * this same list also backs ticket creation, editing, filters, badges, and
 * dashboard analytics everywhere else in the app.
 */
export async function fetchPriorities(): Promise<Priority[]> {
  const { data } = await apiClient.get<DataResponse<Priority[]>>("/priorities");
  return data.data;
}

export async function createPriority(title: string): Promise<Priority> {
  const { data } = await apiClient.post<DataResponse<Priority>>("/priorities", { title });
  return data.data;
}

export async function updatePriority(priorityId: number, title: string): Promise<Priority> {
  const { data } = await apiClient.patch<DataResponse<Priority>>(`/priorities/${priorityId}`, {
    title,
  });
  return data.data;
}
