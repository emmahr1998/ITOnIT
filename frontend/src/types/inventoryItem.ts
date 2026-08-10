import type { Location } from "./location";
import type { InventoryCategory } from "./inventoryCategory";

/** Mirrors backend/app/models/enums.py InventoryTrackingType. */
export type InventoryTrackingType = "SERIALIZED" | "BULK";

/** Mirrors backend/app/models/enums.py InventoryStatus. */
export type InventoryStatus = "AVAILABLE" | "RESERVED" | "IN_USE" | "IN_REPAIR" | "RETIRED";

/** Mirrors backend/app/models/enums.py InventoryCondition. */
export type InventoryCondition = "NEW" | "GOOD" | "FAIR" | "DAMAGED" | "BROKEN";

export const INVENTORY_TRACKING_TYPES: InventoryTrackingType[] = ["SERIALIZED", "BULK"];

/** Every status value, for the SERIALIZED create/edit form. */
export const SERIALIZED_STATUSES: InventoryStatus[] = [
  "AVAILABLE",
  "RESERVED",
  "IN_USE",
  "IN_REPAIR",
  "RETIRED",
];

/**
 * BULK items are restricted to these two statuses server-side
 * (ck_inventory_items_bulk_status) - the create/edit form only offers
 * these when tracking_type is BULK, so the client can't even construct a
 * request the backend would reject on this rule.
 */
export const BULK_STATUSES: InventoryStatus[] = ["AVAILABLE", "RETIRED"];

export const INVENTORY_CONDITIONS: InventoryCondition[] = [
  "NEW",
  "GOOD",
  "FAIR",
  "DAMAGED",
  "BROKEN",
];

export const INVENTORY_SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "created_at", label: "Created" },
  { value: "updated_at", label: "Last Updated" },
  { value: "name", label: "Name" },
  { value: "purchase_date", label: "Purchase Date" },
  { value: "warranty_expiration", label: "Warranty Expiration" },
];

/** Mirrors backend/app/schemas/inventory_item.py InventoryHolderSummary. */
export interface InventoryHolderSummary {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
}

/** Mirrors backend/app/schemas/inventory_item.py InventoryItemResponse. */
export interface InventoryItem {
  id: number;
  inventory_category: InventoryCategory;
  current_location: Location | null;
  current_holder: InventoryHolderSummary | null;
  asset_tag: string | null;
  name: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  tracking_type: InventoryTrackingType;
  status: InventoryStatus;
  condition: InventoryCondition | null;
  stock_quantity: number;
  reserved_quantity: number;
  minimum_stock: number | null;
  purchase_date: string | null;
  warranty_expiration: string | null;
  supplier: string | null;
  // Pydantic serializes Decimal as a string, not a number - confirmed
  // against the live API response ("purchase_cost": "1299.99").
  purchase_cost: string | null;
  invoice_number: string | null;
  image_path: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** POST /inventory-items request body (backend InventoryItemCreate). */
export interface InventoryItemCreate {
  inventory_category_id: number;
  name: string;
  tracking_type: InventoryTrackingType;
  status?: InventoryStatus;
  condition?: InventoryCondition | null;
  asset_tag?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  serial_number?: string | null;
  stock_quantity?: number | null;
  minimum_stock?: number | null;
  current_location_id?: number | null;
  current_holder_user_id?: number | null;
  purchase_date?: string | null;
  warranty_expiration?: string | null;
  supplier?: string | null;
  purchase_cost?: string | null;
  invoice_number?: string | null;
  image_path?: string | null;
  notes?: string | null;
}

/**
 * PATCH /inventory-items/{id} request body (backend InventoryItemUpdate) -
 * everything is optional, and tracking_type is absent entirely since it's
 * immutable after creation (see the backend schema's own docstring).
 */
export type InventoryItemUpdate = Partial<Omit<InventoryItemCreate, "tracking_type">>;

/** Server-side query params accepted by GET /inventory-items. */
export interface InventoryItemListParams {
  inventory_category_id?: number;
  tracking_type?: InventoryTrackingType;
  status?: InventoryStatus;
  condition?: InventoryCondition;
  current_location_id?: number;
  current_holder_user_id?: number;
  manufacturer?: string;
  model?: string;
  search?: string;
  low_stock?: boolean;
  warranty_expiring_days?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  skip?: number;
  limit?: number;
}
