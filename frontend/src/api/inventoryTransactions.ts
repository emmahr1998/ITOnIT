import { apiClient } from "./client";
import type {
  InventoryItemTransactionListParams,
  InventoryTransaction,
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

// GET /inventory-transactions (the company-wide feed, Company Administrator
// only) has no frontend caller yet - no page needs it this phase. Add the
// wrapper back alongside whatever page first needs it, rather than keeping
// it here unused.
