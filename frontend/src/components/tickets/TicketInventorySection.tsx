import { useEffect, useState } from "react";
import { Boxes, Plus } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import {
  consumeTicketInventory,
  fetchTicketInventory,
  releaseTicketInventory,
  removeTicketInventory,
} from "../../api/ticketInventory";
import { getApiErrorMessage } from "../../api/client";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { ErrorMessage } from "../common/ErrorMessage";
import { SuccessMessage } from "../common/SuccessMessage";
import { EmptyState } from "../common/EmptyState";
import { TrackingTypeBadge } from "../common/InventoryBadges";
import { TicketInventoryReserveModal } from "./TicketInventoryReserveModal";
import type { TicketInventoryUsage } from "../../types/ticketInventory";
import styles from "./TicketInventorySection.module.css";

function UsageStatusBadge({ status }: { status: TicketInventoryUsage["status"] }) {
  return (
    <span className={status === "RESERVED" ? styles.badgeReserved : styles.badgeConsumed}>
      {status === "RESERVED" ? "Reserved" : "Consumed"}
    </span>
  );
}

export function TicketInventorySection({ ticketId }: { ticketId: number }) {
  const { user } = useAuth();
  const canManage = user?.role === "Company Administrator";

  const [usages, setUsages] = useState<TicketInventoryUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showReserveModal, setShowReserveModal] = useState(false);
  const [busyUsageId, setBusyUsageId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTicketInventory(ticketId)
      .then((data) => !cancelled && setUsages(data))
      .catch((err) => !cancelled && setError(getApiErrorMessage(err, "Could not load inventory.")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  function handleReserved(usage: TicketInventoryUsage) {
    setUsages((prev) => {
      const existingIndex = prev.findIndex((u) => u.id === usage.id);
      if (existingIndex === -1) {
        return [...prev, usage];
      }
      const next = [...prev];
      next[existingIndex] = usage;
      return next;
    });
    setShowReserveModal(false);
    setSuccessMessage(`Reserved ${usage.inventory_item.name}.`);
  }

  async function handleConsume(usage: TicketInventoryUsage) {
    setBusyUsageId(usage.id);
    setActionError(null);
    try {
      const updated = await consumeTicketInventory(ticketId, usage.id);
      setUsages((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setSuccessMessage(`Consumed ${updated.inventory_item.name}.`);
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Could not consume this item."));
    } finally {
      setBusyUsageId(null);
    }
  }

  async function handleRelease(usage: TicketInventoryUsage) {
    setBusyUsageId(usage.id);
    setActionError(null);
    try {
      await releaseTicketInventory(ticketId, usage.id);
      setUsages((prev) => prev.filter((u) => u.id !== usage.id));
      setSuccessMessage(`Released ${usage.inventory_item.name}.`);
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Could not release this item."));
    } finally {
      setBusyUsageId(null);
    }
  }

  async function handleRemove(usage: TicketInventoryUsage) {
    setBusyUsageId(usage.id);
    setActionError(null);
    try {
      await removeTicketInventory(ticketId, usage.id);
      setUsages((prev) => prev.filter((u) => u.id !== usage.id));
      setSuccessMessage(`Removed ${usage.inventory_item.name}.`);
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Could not remove this item."));
    } finally {
      setBusyUsageId(null);
    }
  }

  return (
    <section className="sectionCard">
      <div className={styles.header}>
        <h2 className="sectionHeading">
          <Boxes size={18} strokeWidth={2} /> Inventory
          {usages.length > 0 && <span className={styles.count}>{usages.length}</span>}
        </h2>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowReserveModal(true)}>
          <Plus size={14} /> Reserve Item
        </button>
      </div>

      {loading && <LoadingSpinner label="Loading inventory..." />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && (
        <>
          {usages.length === 0 ? (
            <EmptyState message="No inventory attached to this ticket yet." />
          ) : (
            <div className={`tableShell ${styles.tableWrap}`}>
              <table>
                <thead>
                  <tr>
                    <th>Asset Tag</th>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Quantity</th>
                    <th>Status</th>
                    <th>Tracking Type</th>
                    <th>Current Holder</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {usages.map((usage) => {
                    const item = usage.inventory_item;
                    const busy = busyUsageId === usage.id;
                    return (
                      <tr key={usage.id}>
                        <td className={styles.mono}>{item.asset_tag ?? "—"}</td>
                        <td>{item.name}</td>
                        <td>{item.inventory_category.name}</td>
                        <td className={styles.numCell}>{usage.quantity}</td>
                        <td>
                          <UsageStatusBadge status={usage.status} />
                        </td>
                        <td>
                          <TrackingTypeBadge trackingType={item.tracking_type} />
                        </td>
                        <td>
                          {item.current_holder
                            ? `${item.current_holder.first_name} ${item.current_holder.last_name}`
                            : "—"}
                        </td>
                        <td className={styles.actions}>
                          {usage.status === "RESERVED" && (
                            <>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                disabled={busy}
                                onClick={() => handleConsume(usage)}
                              >
                                Consume
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                disabled={busy}
                                onClick={() => handleRelease(usage)}
                              >
                                Release
                              </button>
                            </>
                          )}
                          {usage.status === "CONSUMED" && canManage && (
                            <button
                              type="button"
                              className="btn btn-ghost-danger btn-sm"
                              disabled={busy}
                              onClick={() => handleRemove(usage)}
                            >
                              Remove
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {actionError && <ErrorMessage message={actionError} />}
          {successMessage && (
            <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
          )}
        </>
      )}

      {showReserveModal && (
        <TicketInventoryReserveModal
          ticketId={ticketId}
          onClose={() => setShowReserveModal(false)}
          onReserved={handleReserved}
        />
      )}
    </section>
  );
}
