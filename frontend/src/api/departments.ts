import { apiClient } from "./client";
import type { Department } from "../types/department";
import type { DataResponse } from "../types/response";

/** GET /departments is wrapped in the {data, msg} envelope. */
export async function fetchDepartments(): Promise<Department[]> {
  const { data } = await apiClient.get<DataResponse<Department[]>>("/departments");
  return data.data;
}

export async function createDepartment(title: string): Promise<Department> {
  const { data } = await apiClient.post<DataResponse<Department>>("/departments", { title });
  return data.data;
}

export async function updateDepartment(departmentId: number, title: string): Promise<Department> {
  const { data } = await apiClient.patch<DataResponse<Department>>(
    `/departments/${departmentId}`,
    { title },
  );
  return data.data;
}
