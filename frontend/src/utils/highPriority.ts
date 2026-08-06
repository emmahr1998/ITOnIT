import type { Priority } from "../types/priority";

/**
 * "High priority" = the top half of the configured priority scale by id
 * (e.g. High/Critical out of Low/Medium/High/Critical) - derived from
 * whatever priorities the backend has, never hardcoded titles. Shared by
 * the Dashboard's stat card and the Ticket List's "High Priority" view
 * filter so the two always agree on the same set of ids.
 */
export function getHighPriorityIds(priorities: Priority[]): Set<number> {
  const sortedIds = [...priorities].sort((a, b) => a.id - b.id).map((p) => p.id);
  const highTierCount = Math.ceil(sortedIds.length / 2);
  return new Set(sortedIds.slice(sortedIds.length - highTierCount));
}
