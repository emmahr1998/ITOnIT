import { apiClient } from "./client";
import type { SupportContactRequest, SupportContactResponse } from "../types/support";

/**
 * POST /support/contact. Public - called from the Help Center's contact
 * form, never through an authenticated flow. A 503 (SMTP/SUPPORT_EMAIL not
 * configured, or the send itself failing) is surfaced like any other
 * apiClient error - see getApiErrorMessage - the backend never includes
 * SMTP/server exception detail in it.
 */
export async function submitContactMessage(
  payload: SupportContactRequest,
): Promise<SupportContactResponse> {
  const { data } = await apiClient.post<SupportContactResponse>("/support/contact", payload);
  return data;
}
