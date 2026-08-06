import type { TicketUserSummary } from "./ticket";

/** Mirrors backend/app/schemas/history.py TicketHistoryResponse. */
export interface TicketHistoryEntry {
  action: string;
  performed_by: TicketUserSummary;
  old_value: string | null;
  new_value: string | null;
  timestamp: string;
}
