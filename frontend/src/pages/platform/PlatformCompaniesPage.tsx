import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, X } from "lucide-react";
import { fetchPlatformCompanies } from "../../api/platform";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { EmptyState } from "../../components/common/EmptyState";
import { Pagination } from "../../components/common/Pagination";
import type { PlatformCompanyListParams, PlatformCompanySummary } from "../../types/platform";
import pageStyles from "../admin/UsersPage.module.css";
import listStyles from "../TicketListPage.module.css";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 350;

const SORT_OPTIONS: { value: NonNullable<PlatformCompanyListParams["sort_by"]>; label: string }[] = [
  { value: "created_at", label: "Created" },
  { value: "name", label: "Company Name" },
  { value: "company_code", label: "Company Code" },
];

/**
 * GET /platform/companies with true server-driven search/filter/sort/
 * pagination - every change re-fetches, never fetches everything and
 * slices client-side (deliberately unlike UsersPage/InventoryPage/
 * TicketListPage's own fetch-then-slice pattern). `total` comes from the
 * response's structured field (Phase 8.5's backend addition), not len(data)
 * and not parsed from `msg`, so the page count shown is always exact.
 */
export function PlatformCompaniesPage() {
  const navigate = useNavigate();

  const [companies, setCompanies] = useState<PlatformCompanySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState<"" | "true" | "false">("");
  const [sortBy, setSortBy] = useState<NonNullable<PlatformCompanyListParams["sort_by"]>>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const hasActiveFilters = Boolean(search || isActiveFilter);

  useEffect(() => {
    const timeout = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, isActiveFilter, sortBy, sortDir]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchPlatformCompanies({
      search: search || undefined,
      is_active: isActiveFilter ? isActiveFilter === "true" : undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    })
      .then((response) => {
        if (!cancelled) {
          setCompanies(response.data);
          setTotal(response.total);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load companies."));
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
  }, [search, isActiveFilter, sortBy, sortDir, page]);

  function clearFilters() {
    setSearchInput("");
    setIsActiveFilter("");
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const rangeStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, total);

  return (
    <div className={pageStyles.page}>
      <div className={pageStyles.header}>
        <div>
          <h1 className={pageStyles.heading}>Companies</h1>
          {!loading && !error && (
            <p className={pageStyles.count}>
              {total} {total === 1 ? "company" : "companies"}
              {hasActiveFilters ? " matching your filters" : " total"}
            </p>
          )}
        </div>
        <button type="button" className="btn btn-primary" onClick={() => navigate("/platform/companies/new")}>
          <Plus size={16} /> Create Company
        </button>
      </div>

      <div className={pageStyles.filters}>
        <div className={pageStyles.searchWrap}>
          <Search size={16} className={pageStyles.searchIcon} aria-hidden="true" />
          <input
            type="search"
            placeholder="Search companies..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className={`input ${pageStyles.search}`}
          />
        </div>

        <select
          value={isActiveFilter}
          onChange={(e) => setIsActiveFilter(e.target.value as "" | "true" | "false")}
          className="select"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as NonNullable<PlatformCompanyListParams["sort_by"]>)}
          className="select"
          aria-label="Sort by"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              Sort: {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
          aria-label={`Sort direction: ${sortDir === "asc" ? "ascending" : "descending"}`}
        >
          {sortDir === "asc" ? "Asc" : "Desc"}
        </button>

        {hasActiveFilters && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={clearFilters}>
            <X size={14} /> Clear filters
          </button>
        )}
      </div>

      {loading && <Skeleton rows={5} height={52} />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && (
        <>
          {companies.length === 0 ? (
            <div className={pageStyles.emptyWrap}>
              <EmptyState
                title="No matching companies"
                description={
                  hasActiveFilters
                    ? "Try adjusting or clearing your filters."
                    : "Companies created through platform provisioning will appear here."
                }
              />
            </div>
          ) : (
            <>
              <div className="tableShell">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Company Code</th>
                      <th>Status</th>
                      <th>Contact Email</th>
                      <th>Timezone</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {companies.map((company) => (
                      <tr
                        key={company.id}
                        className={listStyles.row}
                        tabIndex={0}
                        role="button"
                        aria-label={`Open ${company.name}`}
                        onClick={() => navigate(`/platform/companies/${company.id}`)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            navigate(`/platform/companies/${company.id}`);
                          }
                        }}
                      >
                        <td>{company.name}</td>
                        <td>{company.company_code}</td>
                        <td>
                          <span className={company.is_active ? "pillActive" : "pillInactive"}>
                            {company.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td>{company.contact_email ?? "—"}</td>
                        <td>{company.timezone}</td>
                        <td>{new Date(company.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className={listStyles.footer}>
                <span className={listStyles.rangeSummary}>
                  Showing {rangeStart}–{rangeEnd} of {total} {total === 1 ? "company" : "companies"}
                </span>
                <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
