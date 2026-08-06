import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  Hourglass,
  ListTodo,
  MapPin,
  Plus,
  Tags,
  Ticket as TicketIcon,
  Timer,
  UserCheck,
  UserCog,
  UserPlus,
  Users as UsersIcon,
} from "lucide-react";
import { useAuth } from "../auth/useAuth";
import { fetchAllTickets } from "../api/tickets";
import { fetchPriorities } from "../api/priorities";
import { fetchUsers } from "../api/users";
import { getApiErrorMessage } from "../api/client";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { StatCard } from "../components/common/StatCard";
import { BreakdownList, type BreakdownColor } from "../components/common/BreakdownList";
import { MonthlyTrend, type MonthlyTrendPoint } from "../components/common/MonthlyTrend";
import { SystemHealthCard } from "../components/common/SystemHealthCard";
import { StatusBadge } from "../components/common/StatusBadge";
import { PriorityBadge } from "../components/common/PriorityBadge";
import { EmptyState } from "../components/common/EmptyState";
import type { Ticket } from "../types/ticket";
import { getHighPriorityIds } from "../utils/highPriority";
import styles from "./DashboardPage.module.css";

const STATUS_ORDER = ["NEW", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_EMPLOYEE", "RESOLVED", "CLOSED"];

/** Mirrors StatusBadge's own status→color mapping, so the chart and the badges never disagree. */
const STATUS_COLOR: Record<string, BreakdownColor> = {
  NEW: "blue",
  ASSIGNED: "blue",
  IN_PROGRESS: "amber",
  WAITING_FOR_EMPLOYEE: "amber",
  RESOLVED: "green",
  CLOSED: "gray",
};

function isToday(isoDate: string): boolean {
  const date = new Date(isoDate);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

/** Formats a millisecond duration as e.g. "3.2h" or "1.4d" - whichever reads more naturally. */
function formatDuration(ms: number): string {
  const hours = ms / (1000 * 60 * 60);
  if (hours < 24) {
    return `${hours.toFixed(1)}h`;
  }
  return `${(hours / 24).toFixed(1)}d`;
}

/**
 * A flat superset of every count any role's dashboard might show. The
 * backend already scopes `tickets` per role (Employee = their own,
 * Technician = assigned to them, Manager/Admin = everyone), so the same
 * "openCount" field is correct for "My Open Tickets", "Assigned To Me", or
 * "Open Tickets" depending only on which role is looking at it - only the
 * card label changes, never the underlying query.
 */
interface Stats {
  openCount: number;
  createdToday: number;
  resolvedToday: number;
  highPriorityOpen: number;
  pendingAssignments: number;
  inProgressCount: number;
  waitingCount: number;
  avgResolutionMs: number | null;
}

function computeStats(tickets: Ticket[], highPriorityIds: Set<number>): Stats {
  let openCount = 0;
  let createdToday = 0;
  let resolvedToday = 0;
  let highPriorityOpen = 0;
  let pendingAssignments = 0;
  let inProgressCount = 0;
  let waitingCount = 0;
  let resolutionTotalMs = 0;
  let resolutionCount = 0;

  const openStatuses = new Set(["NEW", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_EMPLOYEE"]);

  for (const ticket of tickets) {
    const isOpen = openStatuses.has(ticket.status);

    if (isOpen) {
      openCount += 1;
    }
    if (isToday(ticket.created_at)) {
      createdToday += 1;
    }
    // Resolved today = resolved_at is today, regardless of whether it has
    // since also been closed - closing doesn't clear resolved_at.
    if (ticket.resolved_at && isToday(ticket.resolved_at)) {
      resolvedToday += 1;
    }
    if (isOpen && highPriorityIds.has(ticket.priority.id)) {
      highPriorityOpen += 1;
    }
    if (ticket.status === "NEW" && !ticket.assigned_technician) {
      pendingAssignments += 1;
    }
    if (ticket.status === "IN_PROGRESS") {
      inProgressCount += 1;
    }
    if (ticket.status === "WAITING_FOR_EMPLOYEE") {
      waitingCount += 1;
    }
    if (ticket.resolved_at) {
      resolutionTotalMs += new Date(ticket.resolved_at).getTime() - new Date(ticket.created_at).getTime();
      resolutionCount += 1;
    }
  }

  return {
    openCount,
    createdToday,
    resolvedToday,
    highPriorityOpen,
    pendingAssignments,
    inProgressCount,
    waitingCount,
    avgResolutionMs: resolutionCount > 0 ? resolutionTotalMs / resolutionCount : null,
  };
}

function computeMonthlyTrend(tickets: Ticket[]): MonthlyTrendPoint[] {
  const months = new Map<string, { label: string; created: number; resolved: number; sortKey: number }>();

  function bucket(dateStr: string) {
    const date = new Date(dateStr);
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    if (!months.has(key)) {
      months.set(key, {
        label: date.toLocaleDateString(undefined, { month: "short", year: "2-digit" }),
        created: 0,
        resolved: 0,
        sortKey: date.getFullYear() * 12 + date.getMonth(),
      });
    }
    return months.get(key)!;
  }

  for (const ticket of tickets) {
    bucket(ticket.created_at).created += 1;
    if (ticket.resolved_at) {
      bucket(ticket.resolved_at).resolved += 1;
    }
  }

  return [...months.values()]
    .sort((a, b) => a.sortKey - b.sortKey)
    .slice(-6)
    .map(({ label, created, resolved }) => ({ monthLabel: label, created, resolved }));
}

export function DashboardPage() {
  const { user } = useAuth();
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [activeTechnicians, setActiveTechnicians] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const role = user?.role;
  const isAdmin = role === "Administrator";
  const isManager = role === "Manager";
  const isTechnician = role === "Technician";
  const isEmployee = role === "Employee";

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [ticketList, priorities] = await Promise.all([
          fetchAllTickets({ limit: 500 }),
          fetchPriorities(),
        ]);
        if (cancelled) {
          return;
        }
        setTickets(ticketList);
        setStats(computeStats(ticketList, getHighPriorityIds(priorities)));
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load dashboard data."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    fetchUsers({ limit: 500 })
      .then((users) => setActiveTechnicians(users.filter((u) => u.role === "Technician" && u.is_active).length))
      .catch(() => {
        // Optional widget - the rest of the dashboard still works without it.
      });
  }, [isAdmin]);

  const statusBreakdown = useMemo(() => {
    if (!tickets) return [];
    const counts = new Map<string, number>();
    for (const ticket of tickets) {
      counts.set(ticket.status, (counts.get(ticket.status) ?? 0) + 1);
    }
    return STATUS_ORDER.filter((status) => counts.has(status)).map((status) => ({
      label: status.replaceAll("_", " "),
      count: counts.get(status) ?? 0,
      color: STATUS_COLOR[status],
    }));
  }, [tickets]);

  const categoryBreakdown = useMemo(() => {
    if (!tickets) return [];
    const counts = new Map<string, number>();
    for (const ticket of tickets) {
      counts.set(ticket.category.name, (counts.get(ticket.category.name) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([label, count]) => ({ label, count }));
  }, [tickets]);

  const monthlyTrend = useMemo(() => (tickets ? computeMonthlyTrend(tickets) : []), [tickets]);

  const recentTickets = useMemo(() => {
    if (!tickets) return [];
    return [...tickets]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5);
  }, [tickets]);

  const recentActivity = useMemo(() => {
    if (!tickets) return [];
    return [...tickets]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 5)
      .map((ticket) => ({
        ticket,
        justCreated: ticket.updated_at === ticket.created_at,
      }));
  }, [tickets]);

  const firstName = user?.first_name?.trim();

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>
            {firstName ? `Welcome back, ${firstName}` : "Welcome back"} <span aria-hidden="true">👋</span>
          </h1>
          <p className={styles.subheading}>Here&rsquo;s what&rsquo;s happening in your IT environment today.</p>
        </div>
        {(isEmployee || isManager || isAdmin) && (
          <Link to="/tickets/new" className="btn btn-primary">
            + Create Ticket
          </Link>
        )}
      </div>

      {loading && <LoadingSpinner label="Loading your tickets..." />}
      {error && <ErrorMessage message={error} />}

      {stats && !loading && !error && (
        <>
          {/* -------- Primary KPI row (role-specific) -------- */}
          <div className={styles.grid}>
            {isEmployee && (
              <>
                <StatCard label="My Open Tickets" value={stats.openCount} accent="blue" icon={ListTodo} to="/tickets?view=open" />
                <StatCard label="Created Today" value={stats.createdToday} accent="blue" icon={CalendarClock} to="/tickets?view=created-today" />
                <StatCard label="Resolved Today" value={stats.resolvedToday} accent="green" icon={CheckCircle2} to="/tickets?view=resolved-today" />
                <StatCard label="High Priority Tickets" value={stats.highPriorityOpen} accent="red" icon={AlertTriangle} to="/tickets?view=high-priority" />
              </>
            )}
            {isTechnician && (
              <>
                <StatCard label="Assigned To Me" value={stats.openCount} accent="blue" icon={UserCheck} to="/tickets?view=open" />
                <StatCard label="In Progress" value={stats.inProgressCount} accent="amber" icon={Hourglass} to="/tickets?status=IN_PROGRESS" />
                <StatCard label="Waiting for Employee" value={stats.waitingCount} accent="amber" icon={Clock} to="/tickets?status=WAITING_FOR_EMPLOYEE" />
                <StatCard label="Resolved Today" value={stats.resolvedToday} accent="green" icon={CheckCircle2} to="/tickets?view=resolved-today" />
              </>
            )}
            {isManager && (
              <>
                <StatCard label="Open Tickets" value={stats.openCount} accent="blue" icon={ListTodo} to="/tickets?view=open" />
                <StatCard label="Pending Assignments" value={stats.pendingAssignments} accent="amber" icon={UserCog} to="/tickets?view=unassigned" />
                <StatCard label="High Priority Tickets" value={stats.highPriorityOpen} accent="red" icon={AlertTriangle} to="/tickets?view=high-priority" />
                <StatCard label="Resolved Today" value={stats.resolvedToday} accent="green" icon={CheckCircle2} to="/tickets?view=resolved-today" />
              </>
            )}
            {isAdmin && (
              <>
                <StatCard label="Open Tickets" value={stats.openCount} accent="blue" icon={ListTodo} to="/tickets?view=open" />
                <StatCard label="Pending Assignments" value={stats.pendingAssignments} accent="amber" icon={UserCog} to="/tickets?view=unassigned" />
                <StatCard label="High Priority Tickets" value={stats.highPriorityOpen} accent="red" icon={AlertTriangle} to="/tickets?view=high-priority" />
                <StatCard label="Created Today" value={stats.createdToday} accent="blue" icon={CalendarClock} to="/tickets?view=created-today" />
              </>
            )}
          </div>

          {/* -------- Secondary KPI row (Administrator only) -------- */}
          {isAdmin && (
            <div className={styles.secondaryGrid}>
              <StatCard label="Active Technicians" value={activeTechnicians ?? "—"} accent="blue" icon={UsersIcon} size="sm" />
              <StatCard
                label="Avg. Resolution Time"
                value={stats.avgResolutionMs !== null ? formatDuration(stats.avgResolutionMs) : "Not enough data"}
                accent="green"
                icon={Timer}
                size="sm"
              />
            </div>
          )}

          {/* -------- Breakdown charts -------- */}
          <div className={styles.breakdownGrid}>
            <BreakdownList title="Tickets by Status" items={statusBreakdown} />
            {!isTechnician && <BreakdownList title="Tickets by Category" items={categoryBreakdown} />}
          </div>

          {isAdmin && <MonthlyTrend points={monthlyTrend} />}

          {/* -------- Recent Activity + Quick Actions (Manager/Admin) -------- */}
          {(isManager || isAdmin) && (
            <div className={styles.splitGrid}>
              <div className={styles.recentCard}>
                <div className={styles.recentHeader}>
                  <h2 className={styles.recentTitle}>Recent Activity</h2>
                </div>
                {recentActivity.length === 0 ? (
                  <EmptyState message="No activity yet." />
                ) : (
                  <ul className="timelineList">
                    {recentActivity.map(({ ticket, justCreated }) => (
                      <li key={ticket.id} className="timelineItem">
                        <span className="timelineDot" aria-hidden="true" />
                        <Link
                          to={`/tickets/${ticket.id}`}
                          className={styles.activityLink}
                          aria-label={`Open ticket ${ticket.ticket_number}`}
                        >
                          <span className={styles.activityText}>
                            <strong>{ticket.ticket_number}</strong>{" "}
                            {justCreated ? "was created" : `was updated · now ${ticket.status.replaceAll("_", " ")}`}
                          </span>
                          <span className={styles.activityTime}>
                            {new Date(ticket.updated_at).toLocaleString()}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={styles.recentCard}>
                <div className={styles.recentHeader}>
                  <h2 className={styles.recentTitle}>Quick Actions</h2>
                </div>
                <div className={styles.quickActions}>
                  <Link to="/tickets/new" className={styles.quickAction}>
                    <span className={styles.quickActionIcon}>
                      <Plus size={16} />
                    </span>
                    Create Ticket
                  </Link>
                  {isAdmin && (
                    <>
                      <Link to="/admin/users?create=1" className={styles.quickAction}>
                        <span className={styles.quickActionIcon}>
                          <UserPlus size={16} />
                        </span>
                        Create User
                      </Link>
                      <Link to="/admin/departments?create=1" className={styles.quickAction}>
                        <span className={styles.quickActionIcon}>
                          <UsersIcon size={16} />
                        </span>
                        Add Department
                      </Link>
                      <Link to="/admin/categories?create=1" className={styles.quickAction}>
                        <span className={styles.quickActionIcon}>
                          <Tags size={16} />
                        </span>
                        Add Category
                      </Link>
                      <Link to="/admin/locations?create=1" className={styles.quickAction}>
                        <span className={styles.quickActionIcon}>
                          <MapPin size={16} />
                        </span>
                        Add Location
                      </Link>
                    </>
                  )}
                  {!isAdmin && (
                    <Link to="/tickets" className={styles.quickAction}>
                      <span className={styles.quickActionIcon}>
                        <TicketIcon size={16} />
                      </span>
                      View All Tickets
                    </Link>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* -------- Recent Tickets (Employee/Technician) -------- */}
          {(isEmployee || isTechnician) && (
            <div className={styles.recentCard}>
              <div className={styles.recentHeader}>
                <h2 className={styles.recentTitle}>
                  {isTechnician ? "Recent Assigned Tickets" : "Recent Tickets"}
                </h2>
                <Link to="/tickets" className="btn btn-ghost btn-sm">
                  View all
                </Link>
              </div>
              {recentTickets.length === 0 ? (
                <EmptyState
                  mascot
                  title="No tickets yet"
                  description="Once tickets are created, the latest ones will show up here."
                />
              ) : (
                <ul className={styles.recentList}>
                  {recentTickets.map((ticket) => (
                    <li key={ticket.id}>
                      <Link
                        to={`/tickets/${ticket.id}`}
                        className={styles.recentRow}
                        aria-label={`Open ticket ${ticket.ticket_number}: ${ticket.title}`}
                      >
                        <div className={styles.recentMain}>
                          <span className={styles.recentNumber}>{ticket.ticket_number}</span>
                          <span className={styles.recentTicketTitle}>{ticket.title}</span>
                        </div>
                        <div className={styles.recentMeta}>
                          <PriorityBadge priority={ticket.priority} />
                          <StatusBadge status={ticket.status} />
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {isAdmin && <SystemHealthCard />}
        </>
      )}
    </div>
  );
}
