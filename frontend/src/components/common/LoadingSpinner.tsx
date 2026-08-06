import styles from "./LoadingSpinner.module.css";

interface LoadingSpinnerProps {
  label?: string;
}

export function LoadingSpinner({ label = "Loading..." }: LoadingSpinnerProps) {
  return (
    <div className={styles.container} role="status" aria-live="polite">
      <div className={styles.spinner} />
      <span className={styles.label}>{label}</span>
    </div>
  );
}
