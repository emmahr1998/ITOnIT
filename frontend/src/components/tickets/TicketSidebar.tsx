import { useEffect, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Calendar, MapPin, Tag, Trash2, User, UserCheck } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import { assignTechnician, changeTicketStatus, deleteTicket, patchTicket } from "../../api/tickets";
import { fetchUsers } from "../../api/users";
import { fetchPriorities } from "../../api/priorities";
import { getApiErrorMessage } from "../../api/client";
import { ConfirmDialog } from "../common/ConfirmDialog";
import { ErrorMessage } from "../common/ErrorMessage";
import { SuccessMessage } from "../common/SuccessMessage";
import { StatusBadge } from "../common/StatusBadge";
import { PriorityBadge } from "../common/PriorityBadge";
import { STATUS_TRANSITIONS } from "../../types/ticket";
import type { Ticket, TicketStatus } from "../../types/ticket";
import type { AdminUser } from "../../types/user";
import type { Priority } from "../../types/priority";
import styles from "./TicketSidebar.module.css";

interface TicketSidebarProps {
  ticket: Ticket;
  onUpdated: (ticket: Ticket) => void;
}

/**
 * The ticket's whole right-hand "properties" panel - both the read-only
 * fields (category, location, creator, dates) and the fields a Company
 * Administrator/assigned Technician can edit (status, priority, assignee).
 * Everyone sees the same panel; only the editable controls are conditional.
 */
export function TicketSidebar({ ticket, onUpdated }: TicketSidebarProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canManage = user?.role === "Company Administrator";
  const canChangeStatus = canManage || user?.role === "Technician";

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [technicians, setTechnicians] = useState<AdminUser[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);

  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const [changingPriority, setChangingPriority] = useState(false);
  const [priorityError, setPriorityError] = useState<string | null>(null);

  const [changingStatus, setChangingStatus] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!canManage) {
      return;
    }
    fetchUsers({ limit: 500 })
      .then((users) => setTechnicians(users.filter((u) => u.role === "Technician" && u.is_active)))
      .catch(() => {
        // The assignment dropdown is a convenience; the rest of the panel still works without it.
      });
    fetchPriorities().then(setPriorities).catch(() => {});
  }, [canManage]);

  async function handleAssign(e: ChangeEvent<HTMLSelectElement>) {
    const technicianId = Number(e.target.value);
    if (!technicianId) {
      return;
    }
    const technician = technicians.find((t) => t.id === technicianId);
    setAssigning(true);
    setAssignError(null);
    try {
      const updated = await assignTechnician(ticket.id, technicianId);
      onUpdated(updated);
      setSuccessMessage(`Assigned to ${technician?.first_name ?? "technician"}.`);
    } catch (err) {
      setAssignError(getApiErrorMessage(err, "Could not assign this technician."));
    } finally {
      setAssigning(false);
    }
  }

  async function handlePriorityChange(e: ChangeEvent<HTMLSelectElement>) {
    const priorityId = Number(e.target.value);
    if (!priorityId) {
      return;
    }
    setChangingPriority(true);
    setPriorityError(null);
    try {
      const updated = await patchTicket(ticket.id, { priority_id: priorityId });
      onUpdated(updated);
      setSuccessMessage(`Priority changed to ${updated.priority.title}.`);
    } catch (err) {
      setPriorityError(getApiErrorMessage(err, "Could not change the priority."));
    } finally {
      setChangingPriority(false);
    }
  }

  async function handleStatusChange(e: ChangeEvent<HTMLSelectElement>) {
    const nextStatus = e.target.value as TicketStatus;
    if (!nextStatus) {
      return;
    }
    setChangingStatus(true);
    setStatusError(null);
    try {
      const updated = await changeTicketStatus(ticket.id, nextStatus);
      onUpdated(updated);
      setSuccessMessage(`Status changed to ${updated.status.replaceAll("_", " ")}.`);
    } catch (err) {
      setStatusError(getApiErrorMessage(err, "Could not change the status."));
    } finally {
      setChangingStatus(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteTicket(ticket.id);
      navigate("/tickets", { replace: true });
    } catch (err) {
      setDeleteError(getApiErrorMessage(err, "Could not delete this ticket."));
      setDeleting(false);
    }
  }

  const nextStatuses = STATUS_TRANSITIONS[ticket.status];

  return (
    <aside className={styles.sidebar}>
      <div className={`sectionCard ${styles.panel}`}>
        <div className={styles.group}>
          <span className={styles.label}>Status</span>
          <StatusBadge status={ticket.status} />
          {canChangeStatus && (
            <>
              <select
                value=""
                onChange={handleStatusChange}
                disabled={changingStatus || nextStatuses.length === 0}
                className={`select ${styles.control}`}
              >
                <option value="" disabled>
                  {nextStatuses.length === 0 ? "No further changes" : "Move to..."}
                </option>
                {nextStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
              {statusError && <ErrorMessage message={statusError} />}
            </>
          )}
        </div>

        <div className={styles.group}>
          <span className={styles.label}>Priority</span>
          <PriorityBadge priority={ticket.priority} />
          {canManage && (
            <>
              <select
                value={ticket.priority.id}
                onChange={handlePriorityChange}
                disabled={changingPriority}
                className={`select ${styles.control}`}
              >
                {priorities.map((priority) => (
                  <option key={priority.id} value={priority.id}>
                    {priority.title}
                  </option>
                ))}
              </select>
              {priorityError && <ErrorMessage message={priorityError} />}
            </>
          )}
        </div>

        <div className={styles.group}>
          <span className={styles.label}>
            <UserCheck size={14} /> Assigned Technician
          </span>
          <span className={styles.value}>
            {ticket.assigned_technician
              ? `${ticket.assigned_technician.first_name} ${ticket.assigned_technician.last_name}`
              : "Unassigned"}
          </span>
          {canManage && (
            <>
              <select
                value={ticket.assigned_technician?.id ?? ""}
                onChange={handleAssign}
                disabled={assigning || ticket.status === "CLOSED"}
                className={`select ${styles.control}`}
              >
                <option value="" disabled>
                  {ticket.status === "CLOSED" ? "Ticket is closed" : "Reassign to..."}
                </option>
                {technicians.map((tech) => (
                  <option key={tech.id} value={tech.id}>
                    {tech.first_name} {tech.last_name}
                  </option>
                ))}
              </select>
              {assignError && <ErrorMessage message={assignError} />}
            </>
          )}
        </div>

        {successMessage && (
          <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
        )}

        <div className={styles.divider} />

        <div className={styles.group}>
          <span className={styles.label}>
            <Tag size={14} /> Category
          </span>
          <span className={styles.value}>{ticket.category.name}</span>
        </div>

        <div className={styles.group}>
          <span className={styles.label}>
            <MapPin size={14} /> Location
          </span>
          <span className={styles.value}>{ticket.location?.title ?? "—"}</span>
        </div>

        <div className={styles.group}>
          <span className={styles.label}>
            <User size={14} /> Creator
          </span>
          <span className={styles.value}>
            {ticket.created_by.first_name} {ticket.created_by.last_name}
          </span>
        </div>

        <div className={styles.divider} />

        <div className={styles.dates}>
          <div className={styles.dateRow}>
            <Calendar size={13} />
            <span>Created</span>
            <span className={styles.dateValue}>
              {new Date(ticket.created_at).toLocaleDateString()}
            </span>
          </div>
          <div className={styles.dateRow}>
            <Calendar size={13} />
            <span>Updated</span>
            <span className={styles.dateValue}>
              {new Date(ticket.updated_at).toLocaleDateString()}
            </span>
          </div>
          <div className={styles.dateRow}>
            <Calendar size={13} />
            <span>Resolved</span>
            <span className={styles.dateValue}>
              {ticket.resolved_at ? new Date(ticket.resolved_at).toLocaleDateString() : "—"}
            </span>
          </div>
          <div className={styles.dateRow}>
            <Calendar size={13} />
            <span>Closed</span>
            <span className={styles.dateValue}>
              {ticket.closed_at ? new Date(ticket.closed_at).toLocaleDateString() : "—"}
            </span>
          </div>
        </div>

        {canManage && (
          <>
            <div className={styles.divider} />
            <button
              type="button"
              className="btn btn-ghost-danger"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 size={14} /> Delete Ticket
            </button>
          </>
        )}
      </div>

      {confirmingDelete && (
        <ConfirmDialog
          title="Delete ticket"
          message={`Delete ${ticket.ticket_number}? This permanently removes the ticket, its comments, attachments, and history. This cannot be undone.`}
          confirmLabel="Delete"
          danger
          busy={deleting}
          error={deleteError}
          onConfirm={handleDelete}
          onCancel={() => {
            setConfirmingDelete(false);
            setDeleteError(null);
          }}
        />
      )}
    </aside>
  );
}
