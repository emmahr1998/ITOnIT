import { apiClient } from "./client";
import type { TicketInventoryReserve, TicketInventoryUsage } from "../types/ticketInventory";
import type { DataResponse } from "../types/response";

/** GET /tickets/{id}/inventory is wrapped in the {data, msg} envelope. */
export async function fetchTicketInventory(ticketId: number): Promise<TicketInventoryUsage[]> {
  const { data } = await apiClient.get<DataResponse<TicketInventoryUsage[]>>(
    `/tickets/${ticketId}/inventory`,
  );
  return data.data;
}

/** POST /tickets/{id}/inventory - reserve/attach an inventory item. */
export async function reserveTicketInventory(
  ticketId: number,
  payload: TicketInventoryReserve,
): Promise<TicketInventoryUsage> {
  const { data } = await apiClient.post<DataResponse<TicketInventoryUsage>>(
    `/tickets/${ticketId}/inventory`,
    payload,
  );
  return data.data;
}

/** PATCH /tickets/{id}/inventory/{usageId}/consume. */
export async function consumeTicketInventory(
  ticketId: number,
  usageId: number,
): Promise<TicketInventoryUsage> {
  const { data } = await apiClient.patch<DataResponse<TicketInventoryUsage>>(
    `/tickets/${ticketId}/inventory/${usageId}/consume`,
  );
  return data.data;
}

/** PATCH /tickets/{id}/inventory/{usageId}/release - only a RESERVED row may be released. */
export async function releaseTicketInventory(ticketId: number, usageId: number): Promise<void> {
  await apiClient.patch(`/tickets/${ticketId}/inventory/${usageId}/release`);
}

/**
 * DELETE /tickets/{id}/inventory/{usageId} - undoes a CONSUMED row (restores
 * stock/status). Company Administrator only - enforced server-side.
 */
export async function removeTicketInventory(ticketId: number, usageId: number): Promise<void> {
  await apiClient.delete(`/tickets/${ticketId}/inventory/${usageId}`);
}
