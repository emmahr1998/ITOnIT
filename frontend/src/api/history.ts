import { apiClient } from "./client";
import type { TicketHistoryEntry } from "../types/history";

/** GET /tickets/{id}/history returns a bare list. */
export async function fetchTicketHistory(ticketId: number): Promise<TicketHistoryEntry[]> {
  const { data } = await apiClient.get<TicketHistoryEntry[]>(`/tickets/${ticketId}/history`);
  return data;
}
