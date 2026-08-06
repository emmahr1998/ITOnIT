import { apiClient } from "./client";
import type { Location } from "../types/location";
import type { DataResponse } from "../types/response";

/** GET /locations is wrapped in the {data, msg} envelope. */
export async function fetchLocations(): Promise<Location[]> {
  const { data } = await apiClient.get<DataResponse<Location[]>>("/locations");
  return data.data;
}

export async function createLocation(title: string): Promise<Location> {
  const { data } = await apiClient.post<DataResponse<Location>>("/locations", { title });
  return data.data;
}

export async function updateLocation(
  locationId: number,
  payload: { title?: string; is_active?: boolean },
): Promise<Location> {
  const { data } = await apiClient.patch<DataResponse<Location>>(
    `/locations/${locationId}`,
    payload,
  );
  return data.data;
}
