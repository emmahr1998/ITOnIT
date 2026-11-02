/** Mirrors backend/app/schemas/company.py CompanySettingsResponse. */
export interface CompanySettings {
  id: number;
  name: string;
  company_code: string;
  contact_email: string | null;
  logo_url: string | null;
  timezone: string;
  language: string;
}

/**
 * PATCH /companies/me request body. Partial: omit a field to leave it
 * unchanged. contact_email may be explicitly cleared with an empty string.
 * company_code is not editable - the backend generates it at registration.
 */
export interface CompanyUpdateRequest {
  name?: string;
  contact_email?: string;
}
