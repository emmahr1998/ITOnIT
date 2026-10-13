import type { InventoryStatus } from "./inventoryItem";
import type { TicketStatus } from "./ticket";

/** Mirrors backend/app/schemas/analytics.py StatusBreakdownItem. */
export interface TicketStatusBreakdownItem {
  status: TicketStatus;
  count: number;
}

/** Mirrors backend/app/schemas/analytics.py PriorityBreakdownItem. */
export interface TicketPriorityBreakdownItem {
  priority: string;
  count: number;
}

/** Mirrors backend/app/schemas/analytics.py CategoryBreakdownItem. */
export interface TicketCategoryBreakdownItem {
  category: string;
  count: number;
}

/** Mirrors backend/app/schemas/analytics.py MonthlyTrendItem. */
export interface TicketMonthlyTrendItem {
  month: string;
  created: number;
  resolved: number;
}

/**
 * Mirrors backend/app/schemas/analytics.py TicketAnalyticsResponse exactly -
 * field names are not renamed. Already scoped server-side to exactly what
 * the caller is allowed to see (Employee: created-by-only, Technician:
 * assigned-only, Company Administrator: company-wide) - the frontend makes
 * no scoping decisions of its own.
 *
 * unassigned_count is null for Technician/Employee - "unassigned" has no
 * scoped-to-me meaning for them.
 */
export interface TicketAnalyticsResponse {
  open_count: number;
  in_progress_count: number;
  waiting_for_employee_count: number;
  high_priority_open_count: number;
  unassigned_count: number | null;
  created_today: number;
  resolved_today: number;
  avg_resolution_minutes: number | null;
  by_status: TicketStatusBreakdownItem[];
  by_priority: TicketPriorityBreakdownItem[];
  by_category: TicketCategoryBreakdownItem[];
  monthly_trend: TicketMonthlyTrendItem[];
}

/** Mirrors backend/app/schemas/analytics.py InventoryStatusBreakdownItem. */
export interface InventoryStatusBreakdownItem {
  status: InventoryStatus;
  count: number;
}

/** Mirrors backend/app/schemas/analytics.py InventoryCategoryBreakdownItem. */
export interface InventoryCategoryBreakdownItem {
  category: string;
  count: number;
}

/**
 * Mirrors backend/app/schemas/analytics.py InventoryAnalyticsResponse exactly.
 * Company Administrator gets every company-wide field populated and
 * reserved_for_my_tickets_count null; Technician gets the reverse - every
 * company-wide field null and reserved_for_my_tickets_count populated. The
 * backend decides which shape to build; the frontend must render exactly
 * what came back, not assume a shape based on the caller's own role.
 */
export interface InventoryAnalyticsResponse {
  total_items: number | null;
  low_stock_count: number | null;
  warranty_expiring_count: number | null;
  by_status: InventoryStatusBreakdownItem[] | null;
  by_category: InventoryCategoryBreakdownItem[] | null;
  reserved_for_my_tickets_count: number | null;
}
