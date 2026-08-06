import type { Priority } from "../../types/priority";
import styles from "./StatusBadge.module.css";

/**
 * Colors by known priority titles, with a neutral fallback for anything
 * else - priority options themselves always come from the backend, this
 * is purely a cosmetic hint, not a source of truth.
 */
const KNOWN_STYLE: Record<string, string> = {
  low: styles.gray,
  medium: styles.blue,
  high: styles.amber,
  critical: styles.red,
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  const style = KNOWN_STYLE[priority.title.toLowerCase()] ?? styles.gray;
  return <span className={`${styles.badge} ${style}`}>{priority.title}</span>;
}
