import { apiClient } from "./client";
import type {
  InventoryItem,
  InventoryItemCreate,
  InventoryItemListParams,
  InventoryItemUpdate,
} from "../types/inventoryItem";
import type { DataResponse } from "../types/response";

/** GET /inventory-items is wrapped in the {data, msg} envelope. */
export async function fetchInventoryItems(
  params: InventoryItemListParams,
): Promise<InventoryItem[]> {
  const { data } = await apiClient.get<DataResponse<InventoryItem[]>>("/inventory-items", {
    params,
  });
  return data.data;
}

export async function createInventoryItem(payload: InventoryItemCreate): Promise<InventoryItem> {
  const { data } = await apiClient.post<DataResponse<InventoryItem>>(
    "/inventory-items",
    payload,
  );
  return data.data;
}

export async function updateInventoryItem(
  itemId: number,
  payload: InventoryItemUpdate,
): Promise<InventoryItem> {
  const { data } = await apiClient.patch<DataResponse<InventoryItem>>(
    `/inventory-items/${itemId}`,
    payload,
  );
  return data.data;
}
