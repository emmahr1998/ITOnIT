import type { ComponentType } from "react";
import { Link } from "react-router-dom";
import { Inbox } from "lucide-react";
import { Mascot } from "./Mascot";
import styles from "./EmptyState.module.css";

interface EmptyStateAction {
  label: string;
  to: string;
}

interface EmptyStateProps {
  /** Short one-line form, e.g. inside a comment/attachment/history list. */
  message?: string;
  /** Richer form: icon + title + description + optional call-to-action link. */
  title?: string;
  description?: string;
  icon?: ComponentType<{ size?: number; strokeWidth?: number }>;
  action?: EmptyStateAction;
  /** Show the ITOnIT mascot instead of a generic icon - used sparingly, for the friendlier states. */
  mascot?: boolean;
}

export function EmptyState({ message, title, description, icon, action, mascot }: EmptyStateProps) {
  if (!title) {
    return <p className={styles.simple}>{message}</p>;
  }

  const Icon = icon ?? Inbox;

  return (
    <div className={styles.rich}>
      {mascot ? (
        <Mascot size={64} className={styles.mascot} />
      ) : (
        <span className={styles.iconWrap}>
          <Icon size={22} strokeWidth={2} />
        </span>
      )}
      <p className={styles.title}>{title}</p>
      {description && <p className={styles.description}>{description}</p>}
      {action && (
        <Link to={action.to} className={`btn btn-primary btn-sm ${styles.action}`}>
          {action.label}
        </Link>
      )}
    </div>
  );
}
