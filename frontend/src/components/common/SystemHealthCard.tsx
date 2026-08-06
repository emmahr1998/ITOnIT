import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { fetchHealth, type HealthStatus } from "../../api/health";
import styles from "./SystemHealthCard.module.css";

type CheckState = "checking" | "ok" | "down";

/**
 * Only ever reports what GET /health actually says - API reachability and
 * the database status it verifies with a live query. No other "services"
 * are shown, because the backend has no other health signal to check.
 */
export function SystemHealthCard() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [state, setState] = useState<CheckState>("checking");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const check = useCallback(async () => {
    try {
      const result = await fetchHealth();
      setHealth(result);
      setState(result.status === "healthy" ? "ok" : "down");
    } catch {
      setHealth(null);
      setState("down");
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  async function handleRefresh() {
    setRefreshing(true);
    await check();
    setRefreshing(false);
  }

  const apiOk = state === "ok";
  const dbOk = health?.database === "connected";

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <h2 className={styles.title}>System Health</h2>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={handleRefresh}
          disabled={refreshing}
          aria-label="Refresh system health"
        >
          <RefreshCw size={14} className={refreshing ? styles.spinning : ""} />
          Refresh
        </button>
      </div>

      <div className={styles.rows}>
        <div className={styles.row}>
          <span className={`${styles.dot} ${apiOk ? styles.dotOk : styles.dotDown}`} aria-hidden="true" />
          <span className={styles.label}>Backend API</span>
          <span className={apiOk ? styles.statusOk : styles.statusDown}>
            {state === "checking" ? "Checking..." : apiOk ? "Online" : "Unreachable"}
          </span>
        </div>
        <div className={styles.row}>
          <span className={`${styles.dot} ${dbOk ? styles.dotOk : styles.dotDown}`} aria-hidden="true" />
          <span className={styles.label}>Database</span>
          <span className={dbOk ? styles.statusOk : styles.statusDown}>
            {state === "checking" ? "Checking..." : dbOk ? "Connected" : "Unavailable"}
          </span>
        </div>
      </div>

      <div className={styles.footer}>
        {health && <span>v{health.version}</span>}
        {lastChecked && <span>Last checked {lastChecked.toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}
