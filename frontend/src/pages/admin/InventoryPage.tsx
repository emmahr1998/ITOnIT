import { useEffect, useMemo, useState } from "react";
import { History, Pencil, Plus, Search, X } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import { fetchInventoryItems } from "../../api/inventoryItems";
import { fetchInventoryCategories } from "../../api/inventoryCategories";
import { fetchLocations } from "../../api/locations";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { SuccessMessage } from "../../components/common/SuccessMessage";
import { EmptyState } from "../../components/common/EmptyState";
import { Pagination } from "../../components/common/Pagination";
import {
  ConditionBadge,
  InventoryStatusBadge,
  LowStockBadge,
  TrackingTypeBadge,
  WarrantyBadge,
} from "../../components/common/InventoryBadges";
import { isLowStock, warrantyState } from "../../utils/inventoryStatus";
import { InventoryItemFormModal } from "../../components/admin/InventoryItemFormModal";
import { InventoryHistoryModal } from "../../components/admin/InventoryHistoryModal";
import {
  INVENTORY_CONDITIONS,
  INVENTORY_SORT_OPTIONS,
  INVENTORY_TRACKING_TYPES,
  SERIALIZED_STATUSES,
  type InventoryCondition,
  type InventoryHolderSummary,
  type InventoryItem,
  type InventoryStatus,
  type InventoryTrackingType,
} from "../../types/inventoryItem";
import type { InventoryCategory } from "../../types/inventoryCategory";
import type { Location } from "../../types/location";
import styles from "./InventoryPage.module.css";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 350;
const FETCH_LIMIT = 500;
const WARRANTY_WINDOW_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "30", label: "Next 30 days" },
  { value: "60", label: "Next 60 days" },
  { value: "90", label: "Next 90 days" },
];

function uniqueBy<T, K>(items: T[], keyFn: (item: T) => K): T[] {
  const seen = new Set<K>();
  const result: T[] = [];
  for (const item of items) {
    const key = keyFn(item);
    if (!seen.has(key)) {
      seen.add(key);
      result.push(item);
    }
  }
  return result;
}

export function InventoryPage() {
  const { user } = useAuth();
  const canManage = user?.role === "Company Administrator";

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [trackingTypeFilter, setTrackingTypeFilter] = useState<InventoryTrackingType | "">("");
  const [statusFilter, setStatusFilter] = useState<InventoryStatus | "">("");
  const [conditionFilter, setConditionFilter] = useState<InventoryCondition | "">("");
  const [locationFilter, setLocationFilter] = useState("");
  const [holderFilter, setHolderFilter] = useState("");
  const [manufacturerFilter, setManufacturerFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [lowStockFilter, setLowStockFilter] = useState(false);
  const [warrantyWindow, setWarrantyWindow] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const [formModalMode, setFormModalMode] = useState<"create" | "edit" | null>(null);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [historyItem, setHistoryItem] = useState<InventoryItem | null>(null);

  const hasActiveFilters = Boolean(
    search ||
      categoryFilter ||
      trackingTypeFilter ||
      statusFilter ||
      conditionFilter ||
      locationFilter ||
      holderFilter ||
      manufacturerFilter ||
      modelFilter ||
      lowStockFilter ||
      warrantyWindow,
  );

  // Filter option lists: categories/locations are readable by both
  // Company Administrator and Technician (matching the backend's own
  // _VIEW_ROLES on each), so both roles get full dropdowns. There's no
  // equivalent fetch for holders here - see the holderOptions/manufacturer/
  // model derivation below.
  useEffect(() => {
    Promise.all([fetchInventoryCategories(), fetchLocations()])
      .then(([categoryList, locationList]) => {
        setCategories(categoryList);
        setLocations(locationList);
      })
      .catch(() => {
        // Filter dropdowns are a convenience; the list itself still works without them.
      });
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [
    search,
    categoryFilter,
    trackingTypeFilter,
    statusFilter,
    conditionFilter,
    locationFilter,
    holderFilter,
    manufacturerFilter,
    modelFilter,
    lowStockFilter,
    warrantyWindow,
    sortBy,
    sortDir,
  ]);

  function load() {
    setLoading(true);
    setError(null);
    fetchInventoryItems({
      search: search || undefined,
      inventory_category_id: categoryFilter ? Number(categoryFilter) : undefined,
      tracking_type: trackingTypeFilter || undefined,
      status: statusFilter || undefined,
      condition: conditionFilter || undefined,
      current_location_id: locationFilter ? Number(locationFilter) : undefined,
      current_holder_user_id: holderFilter ? Number(holderFilter) : undefined,
      manufacturer: manufacturerFilter || undefined,
      model: modelFilter || undefined,
      low_stock: lowStockFilter || undefined,
      warranty_expiring_days: warrantyWindow ? Number(warrantyWindow) : undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: FETCH_LIMIT,
    })
      .then(setItems)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load inventory items.")))
      .finally(() => setLoading(false));
  }

  useEffect(
    load,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      search,
      categoryFilter,
      trackingTypeFilter,
      statusFilter,
      conditionFilter,
      locationFilter,
      holderFilter,
      manufacturerFilter,
      modelFilter,
      lowStockFilter,
      warrantyWindow,
      sortBy,
      sortDir,
    ],
  );

  // Manufacturer/model/holder filters are exact-match server-side (see
  // InventoryItemRepository), so free-text inputs would force a user to
  // type the exact stored string. Deriving the option lists from whatever
  // is currently loaded - rather than a separate endpoint - sidesteps that
  // entirely (only real values are ever offered) and, for holders
  // specifically, avoids depending on GET /users, which Technician (a
  // read-only inventory role) has no permission to call at all.
  const holderOptions = useMemo<InventoryHolderSummary[]>(
    () =>
      uniqueBy(
        items.map((i) => i.current_holder).filter((h): h is InventoryHolderSummary => h !== null),
        (h) => h.id,
      ).sort((a, b) => `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`)),
    [items],
  );
  const manufacturerOptions = useMemo(
    () =>
      uniqueBy(
        items.map((i) => i.manufacturer).filter((m): m is string => Boolean(m)),
        (m) => m,
      ).sort(),
    [items],
  );
  const modelOptions = useMemo(
    () =>
      uniqueBy(
        items.map((i) => i.model).filter((m): m is string => Boolean(m)),
        (m) => m,
      ).sort(),
    [items],
  );

  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const pagedItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const rangeStart = items.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, items.length);

  function clearFilters() {
    setSearchInput("");
    setCategoryFilter("");
    setTrackingTypeFilter("");
    setStatusFilter("");
    setConditionFilter("");
    setLocationFilter("");
    setHolderFilter("");
    setManufacturerFilter("");
    setModelFilter("");
    setLowStockFilter(false);
    setWarrantyWindow("");
  }

  function handleSaved(item: InventoryItem) {
    if (formModalMode === "create") {
      setItems((prev) => [item, ...prev]);
      setSuccessMessage(`${item.name} added.`);
    } else {
      setItems((prev) => prev.map((i) => (i.id === item.id ? item : i)));
      setSuccessMessage(`${item.name} updated.`);
    }
    setFormModalMode(null);
    setEditingItem(null);
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>Inventory</h1>
          {!loading && !error && (
            <p className={styles.count}>
              {items.length} {items.length === 1 ? "item" : "items"}
              {hasActiveFilters ? " matching your filters" : " total"}
            </p>
          )}
        </div>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setFormModalMode("create")}>
            <Plus size={16} /> Add Item
          </button>
        )}
      </div>

      <div className={styles.filters}>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} aria-hidden="true" />
          <input
            type="search"
            placeholder="Search by tag, name, manufacturer, model, serial, supplier, invoice..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className={`input ${styles.search}`}
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
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
          value={trackingTypeFilter}
          onChange={(e) => setTrackingTypeFilter(e.target.value as InventoryTrackingType | "")}
          className="select"
          aria-label="Filter by tracking type"
        >
          <option value="">All tracking types</option>
          {INVENTORY_TRACKING_TYPES.map((t) => (
            <option key={t} value={t}>
              {t[0] + t.slice(1).toLowerCase()}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as InventoryStatus | "")}
          className="select"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {SERIALIZED_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replaceAll("_", " ")}
            </option>
          ))}
        </select>

        <select
          value={conditionFilter}
          onChange={(e) => setConditionFilter(e.target.value as InventoryCondition | "")}
          className="select"
          aria-label="Filter by condition"
        >
          <option value="">All conditions</option>
          {INVENTORY_CONDITIONS.map((c) => (
            <option key={c} value={c}>
              {c[0] + c.slice(1).toLowerCase()}
            </option>
          ))}
        </select>

        <select
          value={locationFilter}
          onChange={(e) => setLocationFilter(e.target.value)}
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

        <select
          value={holderFilter}
          onChange={(e) => setHolderFilter(e.target.value)}
          className="select"
          aria-label="Filter by current holder"
        >
          <option value="">All holders</option>
          {holderOptions.map((h) => (
            <option key={h.id} value={h.id}>
              {h.first_name} {h.last_name}
            </option>
          ))}
        </select>

        <select
          value={manufacturerFilter}
          onChange={(e) => setManufacturerFilter(e.target.value)}
          className="select"
          aria-label="Filter by manufacturer"
        >
          <option value="">All manufacturers</option>
          {manufacturerOptions.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <select
          value={modelFilter}
          onChange={(e) => setModelFilter(e.target.value)}
          className="select"
          aria-label="Filter by model"
        >
          <option value="">All models</option>
          {modelOptions.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <select
          value={warrantyWindow}
          onChange={(e) => setWarrantyWindow(e.target.value)}
          className="select"
          aria-label="Filter by warranty expiration window"
        >
          {WARRANTY_WINDOW_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <label className={styles.checkboxFilter}>
          <input
            type="checkbox"
            checked={lowStockFilter}
            onChange={(e) => setLowStockFilter(e.target.checked)}
          />
          Low stock only
        </label>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="select"
          aria-label="Sort by"
        >
          {INVENTORY_SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              Sort: {o.label}
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

      {loading && <Skeleton rows={6} height={44} />}
      {error && <ErrorMessage message={error} />}
      {successMessage && (
        <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      {!loading && !error && items.length === 0 && (
        <div className={styles.emptyWrap}>
          <EmptyState
            icon={hasActiveFilters ? Search : undefined}
            title={hasActiveFilters ? "No matching inventory items" : "No inventory items yet"}
            description={
              hasActiveFilters
                ? "Try adjusting or clearing your filters."
                : canManage
                  ? "Add your first inventory item to get started."
                  : "Your Company Administrator hasn't added any inventory items yet."
            }
          />
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <>
          <div className={`tableShell ${styles.tableWrap}`}>
            <table>
              <thead>
                <tr>
                  <th>Asset Tag</th>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Tracking Type</th>
                  <th>Status</th>
                  <th>Condition</th>
                  <th>Manufacturer</th>
                  <th>Model</th>
                  <th>Location</th>
                  <th>Current Holder</th>
                  <th>Purchase Date</th>
                  <th>Warranty Expiration</th>
                  <th>Stock</th>
                  <th>Reserved</th>
                  <th>Minimum Stock</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((item) => (
                  <tr key={item.id}>
                    <td className={styles.mono}>{item.asset_tag ?? "—"}</td>
                    <td className={styles.nameCell}>{item.name}</td>
                    <td>{item.inventory_category.name}</td>
                    <td>
                      <TrackingTypeBadge trackingType={item.tracking_type} />
                    </td>
                    <td>
                      <InventoryStatusBadge status={item.status} />
                    </td>
                    <td>
                      <ConditionBadge condition={item.condition} />
                    </td>
                    <td>{item.manufacturer ?? "—"}</td>
                    <td>{item.model ?? "—"}</td>
                    <td>{item.current_location?.title ?? "—"}</td>
                    <td>
                      {item.current_holder
                        ? `${item.current_holder.first_name} ${item.current_holder.last_name}`
                        : "—"}
                    </td>
                    <td>
                      {item.purchase_date ? new Date(item.purchase_date).toLocaleDateString() : "—"}
                    </td>
                    <td className={styles.warrantyCell}>
                      {item.warranty_expiration
                        ? new Date(item.warranty_expiration).toLocaleDateString()
                        : "—"}
                      <WarrantyBadge state={warrantyState(item)} />
                    </td>
                    <td className={styles.numCell}>{item.stock_quantity}</td>
                    <td className={styles.numCell}>{item.reserved_quantity}</td>
                    <td className={styles.numCell}>
                      {item.minimum_stock ?? "—"}
                      {isLowStock(item) && <LowStockBadge />}
                    </td>
                    <td className={styles.actions}>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => setHistoryItem(item)}
                      >
                        <History size={14} /> History
                      </button>
                      {canManage && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            setEditingItem(item);
                            setFormModalMode("edit");
                          }}
                        >
                          <Pencil size={14} /> Edit
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.footer}>
            <span className={styles.rangeSummary}>
              Showing {rangeStart}–{rangeEnd} of {items.length} item{items.length === 1 ? "" : "s"}
            </span>
            <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
          </div>
        </>
      )}

      {formModalMode && (
        <InventoryItemFormModal
          mode={formModalMode}
          item={formModalMode === "edit" ? (editingItem ?? undefined) : undefined}
          categories={categories}
          locations={locations}
          onClose={() => {
            setFormModalMode(null);
            setEditingItem(null);
          }}
          onSaved={handleSaved}
        />
      )}

      {historyItem && (
        <InventoryHistoryModal item={historyItem} onClose={() => setHistoryItem(null)} />
      )}
    </div>
  );
}
