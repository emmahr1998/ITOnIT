import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronRight, Search, X } from "lucide-react";
import { useAuth } from "../auth/useAuth";
import { fetchAllTickets } from "../api/tickets";
import { fetchCategories } from "../api/categories";
import { fetchPriorities } from "../api/priorities";
import { fetchLocations } from "../api/locations";
import { getApiErrorMessage } from "../api/client";
import { Skeleton } from "../components/common/Skeleton";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import { Pagination } from "../components/common/Pagination";
import { StatusBadge } from "../components/common/StatusBadge";
import { PriorityBadge } from "../components/common/PriorityBadge";
import {
  TICKET_STATUSES,
  VIEW_LABEL,
  type Ticket,
  type TicketDashboardView,
  type TicketStatus,
} from "../types/ticket";
import type { Category } from "../types/category";
import type { Priority } from "../types/priority";
import type { Location } from "../types/location";
import type { Role } from "../types/auth";
import { ticketAgeDays } from "../utils/ticketAge";
import { getHighPriorityIds } from "../utils/highPriority";
import styles from "./TicketListPage.module.css";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 350;
const OPEN_STATUSES = new Set<TicketStatus>(["NEW", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_EMPLOYEE"]);
const VALID_VIEWS = new Set<TicketDashboardView>([
  "open",
  "resolved-today",
  "created-today",
  "high-priority",
  "unassigned",
]);

const HEADING_BY_ROLE: Record<Role, string> = {
  Employee: "My Tickets",
  Technician: "Assigned Tickets",
  "Company Administrator": "All Tickets",
  "System Administrator": "All Tickets",
};

/** "Age" column display: days open (or, if resolved/closed, how long it stayed open). */
function formatAge(ticket: Ticket): string {
  const days = ticketAgeDays(ticket);
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

function isToday(isoDate: string): boolean {
  const date = new Date(isoDate);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

const EMPTY_STATE_BY_ROLE: Record<Role, { title: string; description: string }> = {
  Employee: {
    title: "No tickets yet",
    description: "Create your first ticket and it will show up here.",
  },
  Technician: {
    title: "Nothing assigned to you yet",
    description: "Tickets assigned to you by an administrator will appear here.",
  },
  "Company Administrator": {
    title: "No tickets yet",
    description: "Tickets created across the organization will appear here.",
  },
  "System Administrator": {
    title: "No tickets yet",
    description: "Tickets created across the organization will appear here.",
  },
};

export function TicketListPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<TicketStatus | "">(
    () => (searchParams.get("status") as TicketStatus | null) ?? "",
  );
  const [priorityId, setPriorityId] = useState(() => searchParams.get("priority_id") ?? "");
  const [categoryId, setCategoryId] = useState(() => searchParams.get("category_id") ?? "");
  const [locationId, setLocationId] = useState("");
  const [page, setPage] = useState(1);

  // A "view" is a semantic filter from a dashboard card (e.g. "open", "high
  // priority") that isn't a single backend query param - applied client-side,
  // same approach as the location filter below.
  const [view, setView] = useState<TicketDashboardView | "">(() => {
    const raw = searchParams.get("view");
    return raw && VALID_VIEWS.has(raw as TicketDashboardView) ? (raw as TicketDashboardView) : "";
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const hasActiveFilters = Boolean(search || status || priorityId || categoryId || locationId || view);

  // Load filter option lists once.
  useEffect(() => {
    Promise.all([fetchCategories(), fetchPriorities(), fetchLocations()])
      .then(([categoryList, priorityList, locationList]) => {
        setCategories(categoryList);
        setPriorities(priorityList);
        setLocations(locationList);
      })
      .catch(() => {
        // Filter dropdowns are a convenience; the list itself still works without them.
      });
  }, []);

  // Debounce the free-text search box before it drives a request.
  useEffect(() => {
    const timeout = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  // Reset to page 1 whenever any filter changes.
  useEffect(() => {
    setPage(1);
  }, [search, status, priorityId, categoryId, locationId, view]);

  // Keep the URL in sync so the current filter set is shareable/bookmarkable
  // and so a dashboard card's link is reflected once it lands here.
  useEffect(() => {
    const next = new URLSearchParams();
    if (status) next.set("status", status);
    if (priorityId) next.set("priority_id", priorityId);
    if (categoryId) next.set("category_id", categoryId);
    if (view) next.set("view", view);
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, priorityId, categoryId, view]);

  // Server-side filters: status/priority/category/search. GET /all-tickets has
  // no location filter (or "view") support, so those apply client-side below.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchAllTickets({
      status: status || undefined,
      priority_id: priorityId ? Number(priorityId) : undefined,
      category_id: categoryId ? Number(categoryId) : undefined,
      search: search || undefined,
      limit: 500,
    })
      .then((data) => {
        if (!cancelled) {
          setTickets(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load tickets."));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [search, status, priorityId, categoryId]);

  const highPriorityIds = useMemo(() => getHighPriorityIds(priorities), [priorities]);

  const filteredTickets = useMemo(() => {
    let result = tickets;
    if (locationId) {
      result = result.filter((ticket) => ticket.location?.id === Number(locationId));
    }
    switch (view) {
      case "open":
        result = result.filter((ticket) => OPEN_STATUSES.has(ticket.status));
        break;
      case "resolved-today":
        result = result.filter((ticket) => ticket.resolved_at && isToday(ticket.resolved_at));
        break;
      case "created-today":
        result = result.filter((ticket) => isToday(ticket.created_at));
        break;
      case "high-priority":
        result = result.filter((ticket) => highPriorityIds.has(ticket.priority.id));
        break;
      case "unassigned":
        result = result.filter((ticket) => ticket.status === "NEW" && !ticket.assigned_technician);
        break;
      default:
        break;
    }
    return result;
  }, [tickets, locationId, view, highPriorityIds]);

  const pageCount = Math.max(1, Math.ceil(filteredTickets.length / PAGE_SIZE));
  const pagedTickets = filteredTickets.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const rangeStart = filteredTickets.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, filteredTickets.length);

  function clearFilters() {
    setSearchInput("");
    setStatus("");
    setPriorityId("");
    setCategoryId("");
    setLocationId("");
    setView("");
  }

  const emptyCopy = user ? EMPTY_STATE_BY_ROLE[user.role] : EMPTY_STATE_BY_ROLE.Employee;

  return (
    <div className={styles.page}>
      <h1 className={styles.heading}>{user ? HEADING_BY_ROLE[user.role] : "Tickets"}</h1>

      {view && (
        <div className={styles.viewBanner}>
          <span>
            Showing: <strong>{VIEW_LABEL[view]}</strong>
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setView("")}>
            <X size={14} /> Clear
          </button>
        </div>
      )}

      <div className={styles.filters}>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} aria-hidden="true" />
          <input
            type="search"
            placeholder="Search tickets..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className={`input ${styles.search}`}
          />
        </div>

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as TicketStatus | "")}
          className="select"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {TICKET_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replaceAll("_", " ")}
            </option>
          ))}
        </select>

        <select
          value={priorityId}
          onChange={(e) => setPriorityId(e.target.value)}
          className="select"
          aria-label="Filter by priority"
        >
          <option value="">All priorities</option>
          {priorities.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>

        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="select"
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          value={locationId}
          onChange={(e) => setLocationId(e.target.value)}
          className="select"
          aria-label="Filter by location"
        >
          <option value="">All locations</option>
          {locations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.title}
            </option>
          ))}
        </select>

        {hasActiveFilters && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={clearFilters}>
            <X size={14} /> Clear filters
          </button>
        )}
      </div>

      {loading && <Skeleton rows={6} height={44} />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && filteredTickets.length === 0 && (
        <div className={styles.emptyWrap}>
          {hasActiveFilters ? (
            <EmptyState
              icon={Search}
              title="No matching tickets"
              description="Try adjusting or clearing your filters."
              action={undefined}
            />
          ) : (
            <EmptyState
              mascot
              title={emptyCopy.title}
              description={emptyCopy.description}
              action={
                user && (user.role === "Employee" || user.role === "Company Administrator")
                  ? { label: "Create Ticket", to: "/tickets/new" }
                  : undefined
              }
            />
          )}
        </div>
      )}

      {!loading && !error && filteredTickets.length > 0 && (
        <>
          <div className={`tableShell ${styles.tableWrap}`}>
            <table>
              <thead>
                <tr>
                  <th>Ticket #</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Category</th>
                  <th>Location</th>
                  <th>Requester</th>
                  <th>Assigned To</th>
                  <th>Created</th>
                  <th>Age</th>
                  <th aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {pagedTickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    className={styles.row}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open ticket ${ticket.ticket_number}: ${ticket.title}`}
                    onClick={() => navigate(`/tickets/${ticket.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        navigate(`/tickets/${ticket.id}`);
                      }
                    }}
                  >
                    <td className={styles.ticketNumberCell}>{ticket.ticket_number}</td>
                    <td className={styles.titleCell}>{ticket.title}</td>
                    <td>
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td>
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td>{ticket.category.name}</td>
                    <td>{ticket.location?.title ?? "—"}</td>
                    <td>
                      {ticket.created_by.first_name} {ticket.created_by.last_name}
                    </td>
                    <td>
                      {ticket.assigned_technician
                        ? `${ticket.assigned_technician.first_name} ${ticket.assigned_technician.last_name}`
                        : "Unassigned"}
                    </td>
                    <td>{new Date(ticket.created_at).toLocaleDateString()}</td>
                    <td className={styles.ageCell}>{formatAge(ticket)}</td>
                    <td className={styles.chevronCell}>
                      <ChevronRight size={16} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.footer}>
            <span className={styles.rangeSummary}>
              Showing {rangeStart}–{rangeEnd} of {filteredTickets.length} ticket
              {filteredTickets.length === 1 ? "" : "s"}
            </span>
            <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
          </div>
        </>
      )}
    </div>
  );
}
