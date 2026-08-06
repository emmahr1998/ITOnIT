import type { Ticket } from "../types/ticket";

/** Days a ticket has been open (or, if resolved, how long it stayed open). */
export function ticketAgeDays(ticket: Ticket): number {
  const end = ticket.resolved_at ?? new Date().toISOString();
  return Math.max(
    0,
    Math.floor((new Date(end).getTime() - new Date(ticket.created_at).getTime()) / 86_400_000),
  );
}
