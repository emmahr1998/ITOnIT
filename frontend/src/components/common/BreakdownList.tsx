import styles from "./BreakdownList.module.css";

export type BreakdownColor = "blue" | "amber" | "green" | "gray" | "red";

export interface BreakdownItem {
  label: string;
  count: number;
  /** Ties a bar's color to what it represents (e.g. a status's own badge color). Defaults to the brand accent. */
  color?: BreakdownColor;
}

const FILL_CLASS: Record<BreakdownColor, string> = {
  blue: styles.fillBlue,
  amber: styles.fillAmber,
  green: styles.fillGreen,
  gray: styles.fillGray,
  red: styles.fillRed,
};

interface BreakdownListProps {
  title: string;
  items: BreakdownItem[];
  emptyMessage?: string;
}

/** A simple horizontal bar breakdown - no charting library needed for this. */
export function BreakdownList({ title, items, emptyMessage = "No data yet." }: BreakdownListProps) {
  const total = items.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className={styles.card}>
      <h2 className={styles.title}>{title}</h2>
      {total === 0 ? (
        <p className={styles.empty}>{emptyMessage}</p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => {
            const percent = total === 0 ? 0 : Math.round((item.count / total) * 100);
            return (
              <li key={item.label} className={styles.row}>
                <div className={styles.rowHeader}>
                  <span className={styles.label}>{item.label}</span>
                  <span className={styles.count}>{item.count}</span>
                </div>
                <div className={styles.track}>
                  <div
                    className={`${styles.fill} ${item.color ? FILL_CLASS[item.color] : styles.fillDefault}`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
