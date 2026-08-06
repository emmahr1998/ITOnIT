import type { ComponentType } from "react";
import { Link } from "react-router-dom";
import styles from "./StatCard.module.css";

interface StatCardProps {
  label: string;
  value: number | string;
  accent?: "blue" | "amber" | "green" | "red";
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  /** "sm" is used for secondary/supplementary KPIs, to keep a clear hierarchy against the primary row. */
  size?: "md" | "sm";
  /** When given, the whole card becomes a link (not just the icon/title) to the relevant filtered ticket list. */
  to?: string;
  /** Required whenever `to` is set - describes the destination for screen readers, since the value/label alone don't say "navigates to...". */
  ariaLabel?: string;
}

export function StatCard({ label, value, accent = "blue", icon: Icon, size = "md", to, ariaLabel }: StatCardProps) {
  const compact = size === "sm";
  const content = (
    <>
      <span className={`${styles.iconWrap} ${compact ? styles.iconWrapCompact : ""} ${styles[accent]}`}>
        <Icon size={compact ? 16 : 20} strokeWidth={2} />
      </span>
      <div>
        <p className={`${styles.value} ${compact ? styles.valueCompact : ""}`}>{value}</p>
        <p className={styles.label}>{label}</p>
      </div>
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className={`${styles.card} ${compact ? styles.compact : ""} ${styles.clickable} cardInteractive`}
        aria-label={ariaLabel ?? `${label}: ${value}. View filtered tickets.`}
      >
        {content}
      </Link>
    );
  }

  return (
    <div className={`${styles.card} ${compact ? styles.compact : ""} cardInteractive`}>{content}</div>
  );
}
