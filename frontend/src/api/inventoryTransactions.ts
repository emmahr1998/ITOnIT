import { apiClient } from "./client";
import type {
  InventoryItemTransactionListParams,
  InventoryTransaction,
  InventoryTransactionListParams,
} from "../types/inventoryTransaction";
import type { DataResponse } from "../types/response";

/** GET /inventory-items/{item_id}/transactions - one item's audit history. */
export async function fetchInventoryItemTransactions(
  itemId: number,
  params: InventoryItemTransactionListParams = {},
): Promise<InventoryTransaction[]> {
  const { data } = await apiClient.get<DataResponse<InventoryTransaction[]>>(
    `/inventory-items/${itemId}/transactions`,
    { params },
  );
  return data.data;
}

/**
 * GET /inventory-transactions - the company-wide feed, Company
 * Administrator only (backend-enforced). Its only caller is the
 * Dashboard's Recent Inventory Activity widget.
 */
export async function fetchInventoryTransactions(
  params: InventoryTransactionListParams = {},
): Promise<InventoryTransaction[]> {
  const { data } = await apiClient.get<DataResponse<InventoryTransaction[]>>(
    "/inventory-transactions",
    { params },
  );
  return data.data;
}
