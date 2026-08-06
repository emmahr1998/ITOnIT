import type { TicketUserSummary } from "./ticket";

/** Mirrors backend/app/schemas/comment.py CommentResponse. */
export interface Comment {
  id: number;
  ticket_id: number;
  content: string;
  author: TicketUserSummary;
  created_at: string;
  updated_at: string | null;
}
