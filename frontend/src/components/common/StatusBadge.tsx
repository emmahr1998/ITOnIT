import type { TicketStatus } from "../../types/ticket";
import styles from "./StatusBadge.module.css";

const STATUS_STYLE: Record<TicketStatus, string> = {
  NEW: styles.blue,
  ASSIGNED: styles.blue,
  IN_PROGRESS: styles.amber,
  WAITING_FOR_EMPLOYEE: styles.amber,
  RESOLVED: styles.green,
  CLOSED: styles.gray,
};

function formatStatus(status: TicketStatus): string {
  return status
    .toLowerCase()
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={`${styles.badge} ${STATUS_STYLE[status]}`}>{formatStatus(status)}</span>;
}
