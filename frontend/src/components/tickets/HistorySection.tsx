import { useEffect, useState } from "react";
import { History as HistoryIcon } from "lucide-react";
import { fetchTicketHistory } from "../../api/history";
import { getApiErrorMessage } from "../../api/client";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { ErrorMessage } from "../common/ErrorMessage";
import { EmptyState } from "../common/EmptyState";
import type { TicketHistoryEntry } from "../../types/history";
import styles from "./HistorySection.module.css";

export function HistorySection({ ticketId }: { ticketId: number }) {
  const [entries, setEntries] = useState<TicketHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTicketHistory(ticketId)
      .then((data) => !cancelled && setEntries(data))
      .catch((err) => !cancelled && setError(getApiErrorMessage(err, "Could not load history.")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  return (
    <section className="sectionCard">
      <h2 className="sectionHeading">
        <HistoryIcon size={18} strokeWidth={2} /> History
      </h2>

      {loading && <LoadingSpinner label="Loading history..." />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && (
        <>
          {entries.length === 0 ? (
            <EmptyState message="No changes recorded yet." />
          ) : (
            <ul className="timelineList">
              {entries.map((entry, index) => (
                <li key={index} className="timelineItem">
                  <span className="timelineDot" aria-hidden="true" />
                  <div className={styles.entryBody}>
                    <span className={styles.timestamp}>
                      {new Date(entry.timestamp).toLocaleString()}
                    </span>
                    <span className={styles.text}>
                      <strong>
                        {entry.performed_by.first_name} {entry.performed_by.last_name}
                      </strong>{" "}
                      changed <strong>{entry.action}</strong>
                      {entry.old_value !== null || entry.new_value !== null ? (
                        <>
                          {" "}
                          from <em>{entry.old_value ?? "—"}</em> to{" "}
                          <em>{entry.new_value ?? "—"}</em>
                        </>
                      ) : null}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
