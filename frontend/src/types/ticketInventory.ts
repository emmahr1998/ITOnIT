import type { InventoryItem } from "./inventoryItem";
import type { TicketUserSummary } from "./ticket";

/** Mirrors backend/app/models/enums.py TicketInventoryUsageStatus. */
export type TicketInventoryUsageStatus = "RESERVED" | "CONSUMED";

/** Mirrors backend/app/schemas/ticket_inventory_usage.py TicketInventoryUsageResponse. */
export interface TicketInventoryUsage {
  id: number;
  ticket_id: number;
  inventory_item: InventoryItem;
  quantity: number;
  status: TicketInventoryUsageStatus;
  selected_by: TicketUserSummary;
  created_at: string;
  updated_at: string;
}

/** POST /tickets/{id}/inventory request body (backend TicketInventoryReserve). */
export interface TicketInventoryReserve {
  inventory_item_id: number;
  quantity?: number;
}
