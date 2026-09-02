import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  Hourglass,
  ListTodo,
  MapPin,
  Package,
  PackageCheck,
  PackageMinus,
  Plus,
  ShieldAlert,
  Tags,
  Timer,
  UserCheck,
  UserCog,
  UserPlus,
  Users as UsersIcon,
} from "lucide-react";
import { useAuth } from "../auth/useAuth";
import { fetchAllTickets } from "../api/tickets";
import { fetchUsers } from "../api/users";
import { fetchTicketAnalytics, fetchInventoryAnalytics } from "../api/analytics";
import { fetchInventoryTransactions } from "../api/inventoryTransactions";
import { getApiErrorMessage } from "../api/client";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { StatCard } from "../components/common/StatCard";
import { BreakdownList, type BreakdownColor, type BreakdownItem } from "../components/common/BreakdownList";
import { MonthlyTrend } from "../components/common/MonthlyTrend";
import { SystemHealthCard } from "../components/common/SystemHealthCard";
import { StatusBadge } from "../components/common/StatusBadge";
import { PriorityBadge } from "../components/common/PriorityBadge";
import { InventoryTransactionTypeBadge } from "../components/common/InventoryTransactionTypeBadge";
import { EmptyState } from "../components/common/EmptyState";
import type { Ticket } from "../types/ticket";
import type { TicketAnalyticsResponse, InventoryAnalyticsResponse } from "../types/analytics";
import type { InventoryTransaction } from "../types/inventoryTransaction";
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

const INVENTORY_STATUS_ORDER = ["AVAILABLE", "RESERVED", "IN_USE", "IN_REPAIR", "RETIRED"];

/** Mirrors InventoryStatusBadge's own status→color mapping (InventoryBadges.tsx). */
const INVENTORY_STATUS_COLOR: Record<string, BreakdownColor> = {
  AVAILABLE: "green",
  RESERVED: "blue",
  IN_USE: "amber",
  IN_REPAIR: "red",
  RETIRED: "gray",
};

/** Formats a minutes duration (as returned by the backend) as e.g. "3.2h" or "1.4d". */
function formatResolutionTime(minutes: number): string {
  const hours = minutes / 60;
  if (hours < 24) {
    return `${hours.toFixed(1)}h`;
  }
  return `${(hours / 24).toFixed(1)}d`;
}

function statusBreakdownFrom(items: { status: string; count: number }[]): BreakdownItem[] {
  const counts = new Map(items.map((item) => [item.status, item.count]));
  return STATUS_ORDER.filter((status) => counts.has(status)).map((status) => ({
    label: status.replaceAll("_", " "),
    count: counts.get(status) ?? 0,
    color: STATUS_COLOR[status],
  }));
}

function inventoryStatusBreakdownFrom(items: { status: string; count: number }[]): BreakdownItem[] {
  const counts = new Map(items.map((item) => [item.status, item.count]));
  return INVENTORY_STATUS_ORDER.filter((status) => counts.has(status)).map((status) => ({
    label: status.replaceAll("_", " "),
    count: counts.get(status) ?? 0,
    color: INVENTORY_STATUS_COLOR[status],
  }));
}

function priorityBreakdownFrom(items: { priority: string; count: number }[]): BreakdownItem[] {
  return [...items].sort((a, b) => b.count - a.count).map((item) => ({ label: item.priority, count: item.count }));
}

function categoryBreakdownFrom(items: { category: string; count: number }[]): BreakdownItem[] {
  return [...items].sort((a, b) => b.count - a.count).map((item) => ({ label: item.category, count: item.count }));
}

export function DashboardPage() {
  const { user } = useAuth();

  const role = user?.role;
  const isCompanyAdmin = role === "Company Administrator";
  const isTechnician = role === "Technician";
  const isEmployee = role === "Employee";
  const canViewInventoryAnalytics = isCompanyAdmin || isTechnician;

  // ---- Ticket analytics (required - powers every role's primary KPIs) ----
  const [ticketAnalytics, setTicketAnalytics] = useState<TicketAnalyticsResponse | null>(null);
  const [ticketAnalyticsLoading, setTicketAnalyticsLoading] = useState(true);
  const [ticketAnalyticsError, setTicketAnalyticsError] = useState<string | null>(null);

  const loadTicketAnalytics = useCallback(() => {
    setTicketAnalyticsLoading(true);
    setTicketAnalyticsError(null);
    return fetchTicketAnalytics()
      .then(setTicketAnalytics)
      .catch((err) => setTicketAnalyticsError(getApiErrorMessage(err, "Could not load ticket analytics.")))
      .finally(() => setTicketAnalyticsLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    loadTicketAnalytics();
  }, [user, loadTicketAnalytics]);

  // ---- Inventory analytics (optional widget - Technician + Company Administrator only) ----
  const [inventoryAnalytics, setInventoryAnalytics] = useState<InventoryAnalyticsResponse | null>(null);
  const [inventoryAnalyticsLoading, setInventoryAnalyticsLoading] = useState(false);
  const [inventoryAnalyticsError, setInventoryAnalyticsError] = useState<string | null>(null);

  const loadInventoryAnalytics = useCallback(() => {
    setInventoryAnalyticsLoading(true);
    setInventoryAnalyticsError(null);
    return fetchInventoryAnalytics()
      .then(setInventoryAnalytics)
      .catch((err) => setInventoryAnalyticsError(getApiErrorMessage(err, "Could not load inventory analytics.")))
      .finally(() => setInventoryAnalyticsLoading(false));
  }, []);

  useEffect(() => {
    if (!user || !canViewInventoryAnalytics) return;
    loadInventoryAnalytics();
  }, [user, canViewInventoryAnalytics, loadInventoryAnalytics]);

  // ---- Recent tickets (display-only, optional widget - a small limit, never used to calculate counts) ----
  const [recentTickets, setRecentTickets] = useState<Ticket[] | null>(null);
  const [recentTicketsLoading, setRecentTicketsLoading] = useState(false);
  const [recentTicketsError, setRecentTicketsError] = useState<string | null>(null);

  const loadRecentTickets = useCallback(() => {
    setRecentTicketsLoading(true);
    setRecentTicketsError(null);
    // Employee sees their own newest tickets; Technician/Company Administrator
    // see the most recently *updated* ones - a more useful "what's moving"
    // view once counts no longer come from this list at all.
    const sortBy = isEmployee ? "created_at" : "updated_at";
    return fetchAllTickets({ sort_by: sortBy, sort_dir: "desc", limit: 5 })
      .then(setRecentTickets)
      .catch((err) => setRecentTicketsError(getApiErrorMessage(err, "Could not load recent tickets.")))
      .finally(() => setRecentTicketsLoading(false));
  }, [isEmployee]);

  useEffect(() => {
    if (!user) return;
    loadRecentTickets();
  }, [user, loadRecentTickets]);

  // ---- Recent inventory activity (optional widget - Company Administrator only) ----
  const [recentTransactions, setRecentTransactions] = useState<InventoryTransaction[] | null>(null);
  const [recentTransactionsLoading, setRecentTransactionsLoading] = useState(false);
  const [recentTransactionsError, setRecentTransactionsError] = useState<string | null>(null);

  const loadRecentTransactions = useCallback(() => {
    setRecentTransactionsLoading(true);
    setRecentTransactionsError(null);
    return fetchInventoryTransactions({ limit: 5 })
      .then(setRecentTransactions)
      .catch((err) => setRecentTransactionsError(getApiErrorMessage(err, "Could not load recent inventory activity.")))
      .finally(() => setRecentTransactionsLoading(false));
  }, []);

  useEffect(() => {
    if (!user || !isCompanyAdmin) return;
    loadRecentTransactions();
  }, [user, isCompanyAdmin, loadRecentTransactions]);

  // ---- Active technicians (optional widget, unrelated to ticket/inventory analytics) ----
  const [activeTechnicians, setActiveTechnicians] = useState<number | null>(null);

  useEffect(() => {
    if (!isCompanyAdmin) {
      return;
    }
    fetchUsers({ limit: 500 })
      .then((users) => setActiveTechnicians(users.filter((u) => u.role === "Technician" && u.is_active).length))
      .catch(() => {
        // Optional widget - the rest of the dashboard still works without it.
      });
  }, [isCompanyAdmin]);

  const statusBreakdown = useMemo(
    () => (ticketAnalytics ? statusBreakdownFrom(ticketAnalytics.by_status) : []),
    [ticketAnalytics],
  );
  const priorityBreakdown = useMemo(
    () => (ticketAnalytics ? priorityBreakdownFrom(ticketAnalytics.by_priority) : []),
    [ticketAnalytics],
  );
  const categoryBreakdown = useMemo(
    () => (ticketAnalytics ? categoryBreakdownFrom(ticketAnalytics.by_category) : []),
    [ticketAnalytics],
  );
  const monthlyTrend = useMemo(
    () =>
      ticketAnalytics
        ? ticketAnalytics.monthly_trend.map((point) => ({
            monthLabel: point.month,
            created: point.created,
            resolved: point.resolved,
          }))
        : [],
    [ticketAnalytics],
  );

  const inventoryStatusBreakdown = useMemo(
    () => (inventoryAnalytics?.by_status ? inventoryStatusBreakdownFrom(inventoryAnalytics.by_status) : []),
    [inventoryAnalytics],
  );
  const inventoryCategoryBreakdown = useMemo(
    () => (inventoryAnalytics?.by_category ? categoryBreakdownFrom(inventoryAnalytics.by_category) : []),
    [inventoryAnalytics],
  );

  const recentActivity = useMemo(() => {
    if (!recentTickets) return [];
    return recentTickets.map((ticket) => ({
      ticket,
      justCreated: ticket.updated_at === ticket.created_at,
    }));
  }, [recentTickets]);

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
        {(isEmployee || isCompanyAdmin) && (
          <Link to="/tickets/new" className="btn btn-primary">
            + Create Ticket
          </Link>
        )}
      </div>

      {/* -------- Ticket analytics: KPIs, breakdowns, trend (required) -------- */}
      {ticketAnalyticsLoading && <LoadingSpinner label="Loading your dashboard..." />}
      {ticketAnalyticsError && !ticketAnalyticsLoading && (
        <div className={styles.errorWrap}>
          <ErrorMessage message={ticketAnalyticsError} />
          <button type="button" className="btn btn-secondary btn-sm" onClick={loadTicketAnalytics}>
            Retry
          </button>
        </div>
      )}

      {ticketAnalytics && !ticketAnalyticsLoading && !ticketAnalyticsError && (
        <>
          {/* -------- Primary KPI row (role-specific) -------- */}
          <div className={styles.grid}>
            {isEmployee && (
              <>
                <StatCard label="My Open Tickets" value={ticketAnalytics.open_count} accent="blue" icon={ListTodo} to="/tickets?view=open" />
                <StatCard label="Created Today" value={ticketAnalytics.created_today} accent="blue" icon={CalendarClock} to="/tickets?view=created-today" />
                <StatCard label="Resolved Today" value={ticketAnalytics.resolved_today} accent="green" icon={CheckCircle2} to="/tickets?view=resolved-today" />
                <StatCard label="High Priority Tickets" value={ticketAnalytics.high_priority_open_count} accent="red" icon={AlertTriangle} to="/tickets?view=high-priority" />
              </>
            )}
            {isTechnician && (
              <>
                <StatCard label="Assigned To Me" value={ticketAnalytics.open_count} accent="blue" icon={UserCheck} to="/tickets?view=open" />
                <StatCard label="In Progress" value={ticketAnalytics.in_progress_count} accent="amber" icon={Hourglass} to="/tickets?status=IN_PROGRESS" />
                <StatCard label="Waiting for Employee" value={ticketAnalytics.waiting_for_employee_count} accent="amber" icon={Clock} to="/tickets?status=WAITING_FOR_EMPLOYEE" />
                <StatCard label="High Priority Tickets" value={ticketAnalytics.high_priority_open_count} accent="red" icon={AlertTriangle} to="/tickets?view=high-priority" />
                <StatCard label="Resolved Today" value={ticketAnalytics.resolved_today} accent="green" icon={CheckCircle2} to="/tickets?view=resolved-today" />
              </>
            )}
            {isCompanyAdmin && (
              <>
                <StatCard label="Open Tickets" value={ticketAnalytics.open_count} accent="blue" icon={ListTodo} to="/tickets?view=open" />
                <StatCard label="In Progress" value={ticketAnalytics.in_progress_count} accent="amber" icon={Hourglass} to="/tickets?status=IN_PROGRESS" />
                <StatCard label="Waiting for Employee" value={ticketAnalytics.waiting_for_employee_count} accent="amber" icon={Clock} to="/tickets?status=WAITING_FOR_EMPLOYEE" />
                <StatCard label="Pending Assignments" value={ticketAnalytics.unassigned_count ?? 0} accent="amber" icon={UserCog} to="/tickets?view=unassigned" />
                <StatCard label="High Priority Tickets" value={ticketAnalytics.high_priority_open_count} accent="red" icon={AlertTriangle} to="/tickets?view=high-priority" />
                <StatCard label="Created Today" value={ticketAnalytics.created_today} accent="blue" icon={CalendarClock} to="/tickets?view=created-today" />
                <StatCard label="Resolved Today" value={ticketAnalytics.resolved_today} accent="green" icon={CheckCircle2} to="/tickets?view=resolved-today" />
              </>
            )}
          </div>

          {/* -------- Secondary KPI row (Company Administrator only) -------- */}
          {isCompanyAdmin && (
            <div className={styles.secondaryGrid}>
              <StatCard label="Active Technicians" value={activeTechnicians ?? "—"} accent="blue" icon={UsersIcon} size="sm" />
              <StatCard
                label="Avg. Resolution Time"
                value={ticketAnalytics.avg_resolution_minutes !== null ? formatResolutionTime(ticketAnalytics.avg_resolution_minutes) : "Not enough data"}
                accent="green"
                icon={Timer}
                size="sm"
              />
            </div>
          )}

          {/* -------- Ticket breakdown charts -------- */}
          <div className={styles.breakdownGrid}>
            <BreakdownList title="Tickets by Status" items={statusBreakdown} />
            {!isTechnician && <BreakdownList title="Tickets by Category" items={categoryBreakdown} />}
            {isCompanyAdmin && <BreakdownList title="Tickets by Priority" items={priorityBreakdown} />}
          </div>

          {isCompanyAdmin && <MonthlyTrend points={monthlyTrend} />}
        </>
      )}

      {/* -------- Inventory analytics (Company Administrator: full picture) -------- */}
      {isCompanyAdmin && (
        <>
          {inventoryAnalyticsLoading && <LoadingSpinner label="Loading inventory analytics..." />}
          {inventoryAnalyticsError && !inventoryAnalyticsLoading && (
            <div className={styles.errorWrap}>
              <ErrorMessage message={inventoryAnalyticsError} />
              <button type="button" className="btn btn-secondary btn-sm" onClick={loadInventoryAnalytics}>
                Retry
              </button>
            </div>
          )}
          {inventoryAnalytics && !inventoryAnalyticsLoading && !inventoryAnalyticsError && (
            <>
              <div className={styles.secondaryGrid}>
                <StatCard label="Total Inventory Items" value={inventoryAnalytics.total_items ?? 0} accent="blue" icon={Package} size="sm" />
                <StatCard label="Low Stock" value={inventoryAnalytics.low_stock_count ?? 0} accent="amber" icon={PackageMinus} size="sm" />
                <StatCard label="Warranty Expiring" value={inventoryAnalytics.warranty_expiring_count ?? 0} accent="red" icon={ShieldAlert} size="sm" />
              </div>
              <div className={styles.breakdownGrid}>
                <BreakdownList title="Inventory by Status" items={inventoryStatusBreakdown} />
                <BreakdownList title="Inventory by Category" items={inventoryCategoryBreakdown} />
              </div>
            </>
          )}
        </>
      )}

      {/* -------- Inventory Reserved (Technician only) - never the company-wide dataset -------- */}
      {isTechnician && (
        <>
          {inventoryAnalyticsLoading && <LoadingSpinner label="Loading inventory analytics..." />}
          {inventoryAnalyticsError && !inventoryAnalyticsLoading && (
            <div className={styles.errorWrap}>
              <ErrorMessage message={inventoryAnalyticsError} />
              <button type="button" className="btn btn-secondary btn-sm" onClick={loadInventoryAnalytics}>
                Retry
              </button>
            </div>
          )}
          {inventoryAnalytics && !inventoryAnalyticsLoading && !inventoryAnalyticsError && (
            <div className={styles.secondaryGrid}>
              <StatCard
                label="Inventory Reserved"
                value={inventoryAnalytics.reserved_for_my_tickets_count ?? 0}
                accent="blue"
                icon={PackageCheck}
                size="sm"
              />
            </div>
          )}
        </>
      )}

      {/* -------- Recent Activity + Recent Inventory Activity + Quick Actions (Company Administrator) -------- */}
      {isCompanyAdmin && (
        <div className={styles.splitGrid}>
          <div className={styles.recentCard}>
            <div className={styles.recentHeader}>
              <h2 className={styles.recentTitle}>Recent Activity</h2>
            </div>
            {recentTicketsLoading && <LoadingSpinner label="Loading recent activity..." />}
            {recentTicketsError && !recentTicketsLoading && (
              <div className={styles.errorWrap}>
                <ErrorMessage message={recentTicketsError} />
                <button type="button" className="btn btn-secondary btn-sm" onClick={loadRecentTickets}>
                  Retry
                </button>
              </div>
            )}
            {!recentTicketsLoading && !recentTicketsError && recentActivity.length === 0 && (
              <EmptyState message="No activity yet." />
            )}
            {!recentTicketsLoading && !recentTicketsError && recentActivity.length > 0 && (
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
              <h2 className={styles.recentTitle}>Recent Inventory Activity</h2>
            </div>
            {recentTransactionsLoading && <LoadingSpinner label="Loading inventory activity..." />}
            {recentTransactionsError && !recentTransactionsLoading && (
              <div className={styles.errorWrap}>
                <ErrorMessage message={recentTransactionsError} />
                <button type="button" className="btn btn-secondary btn-sm" onClick={loadRecentTransactions}>
                  Retry
                </button>
              </div>
            )}
            {!recentTransactionsLoading && !recentTransactionsError && recentTransactions?.length === 0 && (
              <EmptyState message="No inventory activity yet." />
            )}
            {!recentTransactionsLoading && !recentTransactionsError && recentTransactions && recentTransactions.length > 0 && (
              <ul className={styles.recentList}>
                {recentTransactions.map((txn) => (
                  <li key={txn.id}>
                    <div className={styles.recentRow}>
                      <div className={styles.recentMain}>
                        <InventoryTransactionTypeBadge transactionType={txn.transaction_type} />
                        <span className={styles.recentTicketTitle}>
                          {txn.inventory_item.name}
                          {" · "}
                          {txn.performed_by.first_name} {txn.performed_by.last_name}
                          {txn.ticket && (
                            <>
                              {" · "}
                              <Link to={`/tickets/${txn.ticket.id}`}>{txn.ticket.ticket_number}</Link>
                            </>
                          )}
                        </span>
                      </div>
                      <span className={styles.activityTime}>{new Date(txn.created_at).toLocaleString()}</span>
                    </div>
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
              <Link to="/admin/inventory" className={styles.quickAction}>
                <span className={styles.quickActionIcon}>
                  <Package size={16} />
                </span>
                Manage Inventory
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* -------- Recent Tickets (Employee/Technician) -------- */}
      {(isEmployee || isTechnician) && (
        <div className={styles.recentCard}>
          <div className={styles.recentHeader}>
            <h2 className={styles.recentTitle}>
              {isTechnician ? "Recently Updated Tickets" : "Recent Tickets"}
            </h2>
            <Link to="/tickets" className="btn btn-ghost btn-sm">
              View all
            </Link>
          </div>
          {recentTicketsLoading && <LoadingSpinner label="Loading recent tickets..." />}
          {recentTicketsError && !recentTicketsLoading && (
            <div className={styles.errorWrap}>
              <ErrorMessage message={recentTicketsError} />
              <button type="button" className="btn btn-secondary btn-sm" onClick={loadRecentTickets}>
                Retry
              </button>
            </div>
          )}
          {!recentTicketsLoading && !recentTicketsError && recentTickets?.length === 0 && (
            <EmptyState
              mascot
              title="No tickets yet"
              description="Once tickets are created, the latest ones will show up here."
            />
          )}
          {!recentTicketsLoading && !recentTicketsError && recentTickets && recentTickets.length > 0 && (
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

      {isCompanyAdmin && <SystemHealthCard />}
    </div>
  );
}
