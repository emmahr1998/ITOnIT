import type { TicketUserSummary } from "./ticket";

/** Mirrors backend/app/schemas/attachment.py AttachmentResponse. */
export interface Attachment {
  id: number;
  ticket_id: number;
  original_filename: string;
  content_type: string | null;
  file_size: number;
  uploaded_by: TicketUserSummary;
  created_at: string;
}
