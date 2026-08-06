import { apiClient } from "./client";

export interface HealthStatus {
  status: string;
  database: string;
  version: string;
}

/** GET /health returns a bare HealthResponse, and requires no auth. */
export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await apiClient.get<HealthStatus>("/health");
  return data;
}
