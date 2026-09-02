import { apiClient } from "./client";
import type { InventoryAnalyticsResponse, TicketAnalyticsResponse } from "../types/analytics";
import type { DataResponse } from "../types/response";

/** GET /analytics/tickets - role scoping is entirely the backend's decision. */
export async function fetchTicketAnalytics(): Promise<TicketAnalyticsResponse> {
  const { data } = await apiClient.get<DataResponse<TicketAnalyticsResponse>>("/analytics/tickets");
  return data.data;
}

/**
 * GET /analytics/inventory - Technician + Company Administrator only
 * (Employee gets a 403 from the backend; callers must not invoke this for
 * Employee). Which fields come back non-null is entirely the backend's
 * decision based on the caller's role.
 */
export async function fetchInventoryAnalytics(): Promise<InventoryAnalyticsResponse> {
  const { data } = await apiClient.get<DataResponse<InventoryAnalyticsResponse>>(
    "/analytics/inventory",
  );
  return data.data;
}
