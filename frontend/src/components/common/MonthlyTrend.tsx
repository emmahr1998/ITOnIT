import styles from "./MonthlyTrend.module.css";

export interface MonthlyTrendPoint {
  monthLabel: string;
  created: number;
  resolved: number;
}

interface MonthlyTrendProps {
  points: MonthlyTrendPoint[];
}

/**
 * Ticket volume by month, computed purely from each ticket's created_at/
 * resolved_at (already fetched for the dashboard) - no new backend data.
 * Shown only when there's more than one month of history to actually
 * trend across; otherwise an honest empty state explains why.
 */
export function MonthlyTrend({ points }: MonthlyTrendProps) {
  const maxValue = Math.max(1, ...points.map((p) => Math.max(p.created, p.resolved)));

  if (points.length < 2) {
    return (
      <div className={styles.card}>
        <h2 className={styles.title}>Monthly Ticket Trend</h2>
        <p className={styles.empty}>
          Not enough history yet to show a trend - check back once tickets span more than one month.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <h2 className={styles.title}>Monthly Ticket Trend</h2>
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchCreated}`} /> Created
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchResolved}`} /> Resolved
        </span>
      </div>
      <ul className={styles.list}>
        {points.map((point) => (
          <li key={point.monthLabel} className={styles.row}>
            <span className={styles.month}>{point.monthLabel}</span>
            <div className={styles.bars}>
              <div
                className={styles.barTrack}
                title={`${point.created} created in ${point.monthLabel}`}
              >
                <div
                  className={`${styles.barFill} ${styles.barCreated}`}
                  style={{ width: `${(point.created / maxValue) * 100}%` }}
                />
              </div>
              <div
                className={styles.barTrack}
                title={`${point.resolved} resolved in ${point.monthLabel}`}
              >
                <div
                  className={`${styles.barFill} ${styles.barResolved}`}
                  style={{ width: `${(point.resolved / maxValue) * 100}%` }}
                />
              </div>
            </div>
            <span className={styles.counts}>
              {point.created}/{point.resolved}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
