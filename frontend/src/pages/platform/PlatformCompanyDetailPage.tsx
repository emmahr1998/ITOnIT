import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Boxes, Power, Ticket, Users as UsersIcon } from "lucide-react";
import {
  activatePlatformCompany,
  deactivatePlatformCompany,
  fetchPlatformCompanyDetail,
} from "../../api/platform";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { SuccessMessage } from "../../components/common/SuccessMessage";
import { StatCard } from "../../components/common/StatCard";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import type { PlatformCompanyDetail } from "../../types/platform";
import dashboardStyles from "../DashboardPage.module.css";
import styles from "../admin/CompanySettingsPage.module.css";

const DEACTIVATE_MESSAGE =
  "This company's data will not be deleted. Its users will immediately lose access - " +
  "they will not be able to sign in, and any already-signed-in session will stop working " +
  "on their next request. You can reactivate this company at any time.";

const ACTIVATE_MESSAGE =
  "This company's users will immediately be able to sign in and use ITOnIT again.";

export function PlatformCompanyDetailPage() {
  const { companyId } = useParams<{ companyId: string }>();
  const id = Number(companyId);

  const [detail, setDetail] = useState<PlatformCompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [confirming, setConfirming] = useState<"activate" | "deactivate" | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchPlatformCompanyDetail(id)
      .then(setDetail)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load this company.")))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleConfirm() {
    if (!confirming || !detail) return;
    setBusy(true);
    setActionError(null);
    try {
      const updated =
        confirming === "activate"
          ? await activatePlatformCompany(detail.id)
          : await deactivatePlatformCompany(detail.id);
      setDetail(updated);
      setSuccessMessage(confirming === "activate" ? "Company activated." : "Company deactivated.");
      setConfirming(null);
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Could not update this company."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <h1 className={styles.heading}>Company Detail</h1>
        <Skeleton rows={6} height={44} />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className={styles.page}>
        <h1 className={styles.heading}>Company Detail</h1>
        <ErrorMessage message={error ?? "Company not found."} />
        <Link to="/platform/companies" className="btn btn-secondary btn-sm">
          <ArrowLeft size={14} /> Back to Companies
        </Link>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Link to="/platform/companies" className="btn btn-ghost btn-sm">
        <ArrowLeft size={14} /> Back to Companies
      </Link>

      <div>
        <h1 className={styles.heading}>
          {detail.name} <span className={detail.is_active ? "pillActive" : "pillInactive"}>
            {detail.is_active ? "Active" : "Inactive"}
          </span>
        </h1>
        <p className={styles.subtitle}>Company code: {detail.company_code}</p>
      </div>

      {successMessage && (
        <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <div className={dashboardStyles.grid}>
        <StatCard label="Users" value={detail.user_count} accent="blue" icon={UsersIcon} />
        <StatCard label="Tickets" value={detail.ticket_count} accent="amber" icon={Ticket} />
        <StatCard label="Inventory Items" value={detail.inventory_item_count} accent="green" icon={Boxes} />
      </div>

      <section className={`sectionCard ${styles.section}`}>
        <h2 className={styles.sectionTitle}>Company Information</h2>
        <dl className={styles.preferencesGrid}>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Contact Email</dt>
            <dd className={styles.preferenceValue}>{detail.contact_email ?? "—"}</dd>
          </div>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Timezone</dt>
            <dd className={styles.preferenceValue}>{detail.timezone}</dd>
          </div>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Language</dt>
            <dd className={styles.preferenceValue}>{detail.language}</dd>
          </div>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Created</dt>
            <dd className={styles.preferenceValue}>{new Date(detail.created_at).toLocaleString()}</dd>
          </div>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Last Updated</dt>
            <dd className={styles.preferenceValue}>{new Date(detail.updated_at).toLocaleString()}</dd>
          </div>
        </dl>

        {actionError && !confirming && <ErrorMessage message={actionError} />}

        <div className={styles.actions}>
          {detail.is_active ? (
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => {
                setActionError(null);
                setConfirming("deactivate");
              }}
            >
              <Power size={16} /> Deactivate Company
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setActionError(null);
                setConfirming("activate");
              }}
            >
              <Power size={16} /> Activate Company
            </button>
          )}
        </div>
      </section>

      {confirming && (
        <ConfirmDialog
          title={confirming === "activate" ? "Activate Company" : "Deactivate Company"}
          message={confirming === "activate" ? ACTIVATE_MESSAGE : DEACTIVATE_MESSAGE}
          confirmLabel={confirming === "activate" ? "Activate" : "Deactivate"}
          danger={confirming === "deactivate"}
          busy={busy}
          error={actionError}
          onConfirm={handleConfirm}
          onCancel={() => {
            setConfirming(null);
            setActionError(null);
          }}
        />
      )}
    </div>
  );
}
