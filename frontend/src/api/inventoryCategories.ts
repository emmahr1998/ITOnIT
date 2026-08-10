import { apiClient } from "./client";
import type { InventoryCategory } from "../types/inventoryCategory";
import type { DataResponse } from "../types/response";

/** GET /inventory-categories is wrapped in the {data, msg} envelope. */
export async function fetchInventoryCategories(): Promise<InventoryCategory[]> {
  const { data } = await apiClient.get<DataResponse<InventoryCategory[]>>(
    "/inventory-categories",
  );
  return data.data;
}

export async function createInventoryCategory(name: string): Promise<InventoryCategory> {
  const { data } = await apiClient.post<DataResponse<InventoryCategory>>(
    "/inventory-categories",
    { name },
  );
  return data.data;
}

export async function updateInventoryCategory(
  categoryId: number,
  payload: { name?: string; is_active?: boolean },
): Promise<InventoryCategory> {
  const { data } = await apiClient.patch<DataResponse<InventoryCategory>>(
    `/inventory-categories/${categoryId}`,
    payload,
  );
  return data.data;
}
