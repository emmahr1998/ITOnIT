import { apiClient } from "./client";
import type { Ticket, TicketListParams, TicketNewCreate, TicketPatch } from "../types/ticket";
import type { TicketStatus } from "../types/ticket";
import type { DataResponse } from "../types/response";

/** GET /all-tickets is wrapped in the {data, msg} envelope. */
export async function fetchAllTickets(params: TicketListParams): Promise<Ticket[]> {
  const { data } = await apiClient.get<DataResponse<Ticket[]>>("/all-tickets", { params });
  return data.data;
}

/** GET /tickets/{id} returns a bare TicketResponse. */
export async function fetchTicket(ticketId: number): Promise<Ticket> {
  const { data } = await apiClient.get<Ticket>(`/tickets/${ticketId}`);
  return data;
}

/** POST /ticket-new is wrapped in the {data, msg} envelope. */
export async function createTicket(payload: TicketNewCreate): Promise<Ticket> {
  const { data } = await apiClient.post<DataResponse<Ticket>>("/ticket-new", payload);
  return data.data;
}

/** PATCH /tickets/{id} (content fields, incl. priority) is wrapped in the envelope. */
export async function patchTicket(ticketId: number, payload: TicketPatch): Promise<Ticket> {
  const { data } = await apiClient.patch<DataResponse<Ticket>>(`/tickets/${ticketId}`, payload);
  return data.data;
}

/** PATCH /tickets/{id}/assign returns a bare TicketResponse. */
export async function assignTechnician(ticketId: number, technicianId: number): Promise<Ticket> {
  const { data } = await apiClient.patch<Ticket>(`/tickets/${ticketId}/assign`, {
    technician_id: technicianId,
  });
  return data;
}

/** PATCH /tickets/{id}/status returns a bare TicketResponse. */
export async function changeTicketStatus(
  ticketId: number,
  status: TicketStatus,
): Promise<Ticket> {
  const { data } = await apiClient.patch<Ticket>(`/tickets/${ticketId}/status`, { status });
  return data;
}

/** DELETE /tickets/{id}. Company Administrator only - enforced server-side. */
export async function deleteTicket(ticketId: number): Promise<void> {
  await apiClient.delete(`/tickets/${ticketId}`);
}
