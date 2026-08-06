import { apiClient } from "./client";
import type { Priority } from "../types/priority";
import type { DataResponse } from "../types/response";

/**
 * GET /priorities is wrapped in the {data, msg} envelope. There is no
 * frontend management page for priorities (the four levels are fixed
 * system values, not admin-editable records) so this is the only function
 * this module needs - it still backs ticket creation, editing, filters,
 * badges, and dashboard analytics everywhere else.
 */
export async function fetchPriorities(): Promise<Priority[]> {
  const { data } = await apiClient.get<DataResponse<Priority[]>>("/priorities");
  return data.data;
}
