import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { fetchTicket } from "../api/tickets";
import { getApiErrorMessage } from "../api/client";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { CommentSection } from "../components/tickets/CommentSection";
import { AttachmentSection } from "../components/tickets/AttachmentSection";
import { HistorySection } from "../components/tickets/HistorySection";
import { TicketSidebar } from "../components/tickets/TicketSidebar";
import type { Ticket } from "../types/ticket";
import { ticketAgeDays } from "../utils/ticketAge";
import styles from "./TicketDetailPage.module.css";

function ageLabel(ticket: Ticket): string {
  const days = ticketAgeDays(ticket);
  const verb = ticket.resolved_at ? "was open for" : "open for";
  if (days === 0) return `${verb} less than a day`;
  if (days === 1) return `${verb} 1 day`;
  return `${verb} ${days} days`;
}

export function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = Number(ticketId);
    if (!id) {
      setError("Invalid ticket id.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchTicket(id)
      .then((data) => !cancelled && setTicket(data))
      .catch((err) => !cancelled && setError(getApiErrorMessage(err, "Could not load ticket.")))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  if (loading) {
    return <LoadingSpinner label="Loading ticket..." />;
  }

  if (error || !ticket) {
    return <ErrorMessage message={error ?? "Ticket not found."} />;
  }

  return (
    <div className={styles.page}>
      <Link to="/tickets" className={styles.backLink}>
        <ChevronLeft size={16} /> Back to tickets
      </Link>

      <div className={styles.header}>
        <p className={styles.ticketNumber}>
          {ticket.ticket_number} &middot; {ageLabel(ticket)}
        </p>
        <h1 className={styles.title}>{ticket.title}</h1>
      </div>

      <div className={styles.layout}>
        <div className={styles.main}>
          <div className="sectionCard">
            <p className={styles.description}>{ticket.description}</p>
          </div>

          <CommentSection ticketId={ticket.id} />
          <AttachmentSection ticketId={ticket.id} />
          <HistorySection ticketId={ticket.id} />
        </div>

        <TicketSidebar ticket={ticket} onUpdated={setTicket} />
      </div>
    </div>
  );
}
