import type { InventoryItem } from "../types/inventoryItem";

/** BULK-only: (stock_quantity - reserved_quantity) <= minimum_stock - the
 * same formula the backend's low_stock filter uses (see
 * InventoryItemRepository._filtered_statement), computed here purely for
 * display, independent of whether the low_stock filter is active. */
export function isLowStock(item: InventoryItem): boolean {
  return (
    item.tracking_type === "BULK" &&
    item.minimum_stock !== null &&
    item.stock_quantity - item.reserved_quantity <= item.minimum_stock
  );
}

const WARRANTY_WARNING_DAYS = 30;

export type WarrantyState = "expired" | "expiring" | null;

export function warrantyState(item: InventoryItem): WarrantyState {
  if (!item.warranty_expiration) {
    return null;
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expiration = new Date(item.warranty_expiration);
  const daysUntil = Math.round((expiration.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (daysUntil < 0) {
    return "expired";
  }
  if (daysUntil <= WARRANTY_WARNING_DAYS) {
    return "expiring";
  }
  return null;
}
