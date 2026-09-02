import type { TicketUserSummary } from "./ticket";

/** Mirrors backend/app/models/enums.py InventoryTransactionType. */
export type InventoryTransactionType =
  | "CREATED"
  | "EDITED"
  | "STOCK_ADJUSTED"
  | "STATUS_CHANGED"
  | "HOLDER_CHANGED"
  | "LOCATION_CHANGED"
  | "RESERVED"
  | "RELEASED"
  | "CONSUMED"
  | "CONSUME_UNDONE";

/** Mirrors backend/app/schemas/inventory_transaction.py InventoryTransactionItemSummary. */
export interface InventoryTransactionItemSummary {
  id: number;
  name: string;
  asset_tag: string | null;
}

/** Mirrors backend/app/schemas/inventory_transaction.py InventoryTransactionTicketSummary. */
export interface InventoryTransactionTicketSummary {
  id: number;
  ticket_number: string;
}

/**
 * Mirrors backend/app/schemas/inventory_transaction.py InventoryTransactionResponse.
 * `ticket` is null both for item-only transactions and for transactions
 * whose ticket has since been deleted (ticket_id is ON DELETE SET NULL -
 * the row itself is permanent, only the reference is cleared).
 */
export interface InventoryTransaction {
  id: number;
  inventory_item: InventoryTransactionItemSummary;
  ticket: InventoryTransactionTicketSummary | null;
  performed_by: TicketUserSummary;
  transaction_type: InventoryTransactionType;
  quantity_delta: number | null;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  notes: string | null;
  created_at: string;
}

/** Query params accepted by GET /inventory-items/{item_id}/transactions. */
export interface InventoryItemTransactionListParams {
  skip?: number;
  limit?: number;
}

/** Query params accepted by GET /inventory-transactions (the company-wide feed). */
export interface InventoryTransactionListParams {
  inventory_item_id?: number;
  ticket_id?: number;
  transaction_type?: InventoryTransactionType;
  performed_by_user_id?: number;
  skip?: number;
  limit?: number;
}
