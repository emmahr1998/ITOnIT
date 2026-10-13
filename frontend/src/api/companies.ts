import { apiClient } from "./client";
import type { CompanySettings, CompanyUpdateRequest } from "../types/company";

/** GET /companies/me - Company-Administrator-only. */
export async function fetchCompanySettings(): Promise<CompanySettings> {
  const { data } = await apiClient.get<CompanySettings>("/companies/me");
  return data;
}

/** PATCH /companies/me - Company-Administrator-only. */
export async function updateCompanySettings(
  payload: CompanyUpdateRequest,
): Promise<CompanySettings> {
  const { data } = await apiClient.patch<CompanySettings>("/companies/me", payload);
  return data;
}

/** POST /companies/me/logo - Company-Administrator-only, multipart upload. */
export async function uploadCompanyLogo(file: File): Promise<CompanySettings> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<CompanySettings>("/companies/me/logo", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
