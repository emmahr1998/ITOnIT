import { apiClient } from "./client";
import type { Comment } from "../types/comment";

/** GET /tickets/{id}/comments returns a bare list. */
export async function fetchComments(ticketId: number): Promise<Comment[]> {
  const { data } = await apiClient.get<Comment[]>(`/tickets/${ticketId}/comments`);
  return data;
}

/** POST /tickets/{id}/comments returns a bare CommentResponse. */
export async function addComment(ticketId: number, content: string): Promise<Comment> {
  const { data } = await apiClient.post<Comment>(`/tickets/${ticketId}/comments`, { content });
  return data;
}
