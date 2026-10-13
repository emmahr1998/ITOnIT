import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Building2, CheckCircle2, Users as UsersIcon, XCircle } from "lucide-react";
import { fetchPlatformOverview } from "../../api/platform";
import { getApiErrorMessage } from "../../api/client";
import { LoadingSpinner } from "../../components/common/LoadingSpinner";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { StatCard } from "../../components/common/StatCard";
import { EmptyState } from "../../components/common/EmptyState";
import type { PlatformOverview } from "../../types/platform";
import styles from "../DashboardPage.module.css";

/**
 * GET /platform/overview is the only data source here - every number shown
 * comes straight from the backend's own aggregate counts (including
 * total_users, which the backend already excludes the System
 * Administrator's own account from). Nothing here is recomputed from a
 * company list.
 */
export function PlatformDashboardPage() {
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchPlatformOverview()
      .then(setOverview)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load the platform overview.")))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>Platform Overview</h1>
          <p className={styles.subheading}>Every company on ITOnIT, at a glance.</p>
        </div>
      </div>

      {loading && <LoadingSpinner label="Loading platform overview..." />}
      {error && !loading && (
        <div className={styles.errorWrap}>
          <ErrorMessage message={error} />
          <button type="button" className="btn btn-secondary btn-sm" onClick={load}>
            Retry
          </button>
        </div>
      )}

      {overview && !loading && !error && (
        <>
          <div className={styles.grid}>
            <StatCard
              label="Total Companies"
              value={overview.total_companies}
              accent="blue"
              icon={Building2}
            />
            <StatCard
              label="Active Companies"
              value={overview.active_companies}
              accent="green"
              icon={CheckCircle2}
            />
            <StatCard
              label="Inactive Companies"
              value={overview.inactive_companies}
              accent="red"
              icon={XCircle}
            />
            <StatCard label="Total Users" value={overview.total_users} accent="blue" icon={UsersIcon} />
          </div>

          <div className={styles.recentCard}>
            <div className={styles.recentHeader}>
              <h2 className={styles.recentTitle}>Recent Companies</h2>
              <Link to="/platform/companies" className="btn btn-ghost btn-sm">
                View all
              </Link>
            </div>
            {overview.recent_companies.length === 0 ? (
              <EmptyState message="No companies yet." />
            ) : (
              <ul className={styles.recentList}>
                {overview.recent_companies.map((company) => (
                  <li key={company.id}>
                    <Link
                      to={`/platform/companies/${company.id}`}
                      className={styles.recentRow}
                      aria-label={`Open ${company.name}`}
                    >
                      <div className={styles.recentMain}>
                        <span className={styles.recentTicketTitle}>{company.name}</span>
                        <span className={company.is_active ? "pillActive" : "pillInactive"}>
                          {company.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      <span className={styles.activityTime}>
                        {new Date(company.created_at).toLocaleDateString()}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
