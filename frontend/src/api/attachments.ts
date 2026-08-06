import { apiClient } from "./client";
import type { Attachment } from "../types/attachment";

/** GET /tickets/{id}/attachments returns a bare list. */
export async function fetchAttachments(ticketId: number): Promise<Attachment[]> {
  const { data } = await apiClient.get<Attachment[]>(`/tickets/${ticketId}/attachments`);
  return data;
}

/** POST /tickets/{id}/attachments - multipart upload, returns a bare AttachmentResponse. */
export async function uploadAttachment(ticketId: number, file: File): Promise<Attachment> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<Attachment>(
    `/tickets/${ticketId}/attachments`,
    formData,
  );
  return data;
}

/**
 * GET /tickets/{id}/attachments/{attachmentId} returns the raw file bytes.
 * Triggers a browser download by creating a temporary object URL.
 */
export async function downloadAttachment(
  ticketId: number,
  attachmentId: number,
  filename: string,
): Promise<void> {
  const response = await apiClient.get(`/tickets/${ticketId}/attachments/${attachmentId}`, {
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
