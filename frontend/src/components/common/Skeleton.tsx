import styles from "./Skeleton.module.css";

interface SkeletonProps {
  rows?: number;
  height?: number;
}

/** A simple animated placeholder block, used while a list/table is loading. */
export function Skeleton({ rows = 4, height = 44 }: SkeletonProps) {
  return (
    <div className={styles.stack}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={styles.bar} style={{ height }} />
      ))}
    </div>
  );
}
