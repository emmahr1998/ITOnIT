import { useState } from "react";
import { Bell } from "lucide-react";
import { EmptyState } from "../common/EmptyState";
import styles from "./NotificationBell.module.css";

/**
 * A static notification bell - there is no notification data source in the
 * backend (no endpoint, no model), so this intentionally never shows a
 * badge count or real items. It's here for the modern-SaaS chrome the
 * design calls for, not a functioning notification system.
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.bellButton}
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        aria-expanded={open}
      >
        <Bell size={20} strokeWidth={2} />
      </button>

      {open && (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close notifications"
            onClick={() => setOpen(false)}
          />
          <div className={styles.panel} role="dialog" aria-label="Notifications">
            <div className={styles.panelHeader}>Notifications</div>
            <EmptyState
              mascot
              title="No notifications"
              description="Everything is running smoothly."
            />
          </div>
        </>
      )}
    </div>
  );
}
