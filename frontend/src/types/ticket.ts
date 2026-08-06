import type { Category } from "./category";
import type { Location } from "./location";
import type { Priority } from "./priority";

/** Mirrors backend/app/models/enums.py TicketStatus. */
export type TicketStatus =
  | "NEW"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "WAITING_FOR_EMPLOYEE"
  | "RESOLVED"
  | "CLOSED";

export const TICKET_STATUSES: TicketStatus[] = [
  "NEW",
  "ASSIGNED",
  "IN_PROGRESS",
  "WAITING_FOR_EMPLOYEE",
  "RESOLVED",
  "CLOSED",
];

/** Mirrors backend/app/schemas/ticket.py TicketUserSummary. */
export interface TicketUserSummary {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
}

/** Mirrors backend/app/schemas/ticket.py TicketResponse. */
export interface Ticket {
  id: number;
  ticket_number: string;
  title: string;
  description: string;
  location: Location | null;
  status: TicketStatus;
  priority: Priority;
  category: Category;
  created_by: TicketUserSummary;
  assigned_technician: TicketUserSummary | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
}

/** POST /ticket-new request body (backend/app/schemas/ticket.py TicketNewCreate). */
export interface TicketNewCreate {
  title: string;
  description: string;
  category_id: number;
  priority_id: number;
  location_id?: number | null;
  requester_user_id?: number | null;
}

/** Server-side query params accepted by GET /all-tickets. */
export interface TicketListParams {
  status?: TicketStatus;
  priority_id?: number;
  category_id?: number;
  department_id?: number;
  requester?: number;
  assigned_to?: number;
  search?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  skip?: number;
  limit?: number;
}

/**
 * PATCH /tickets/{id} request body (backend/app/schemas/ticket.py TicketPatch).
 * This is also how priority changes happen - there is no dedicated endpoint.
 */
export interface TicketPatch {
  title?: string;
  description?: string;
  location_id?: number | null;
  category_id?: number;
  priority_id?: number;
}

/**
 * Semantic "view" filters the Dashboard's clickable cards link to via
 * ?view=<value> on /tickets - things that aren't a single backend query
 * param (e.g. "any open status", "resolved today") so the Ticket List
 * applies them itself as a client-side post-filter, same approach as the
 * existing location filter.
 */
export type TicketDashboardView =
  | "open"
  | "resolved-today"
  | "created-today"
  | "high-priority"
  | "unassigned";

export const VIEW_LABEL: Record<TicketDashboardView, string> = {
  open: "Open tickets",
  "resolved-today": "Resolved today",
  "created-today": "Created today",
  "high-priority": "High priority",
  unassigned: "Unassigned",
};

/**
 * Mirrors the status graph enforced server-side in
 * backend/app/services/ticket_service.py (_STATUS_TRANSITIONS) - used only
 * to keep the status dropdown from offering invalid transitions. The
 * backend remains the sole source of truth and will reject anything else.
 */
export const STATUS_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  NEW: ["ASSIGNED"],
  ASSIGNED: ["IN_PROGRESS"],
  IN_PROGRESS: ["WAITING_FOR_EMPLOYEE", "RESOLVED"],
  WAITING_FOR_EMPLOYEE: ["IN_PROGRESS"],
  RESOLVED: ["CLOSED"],
  CLOSED: [],
};
