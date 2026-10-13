import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, Pencil, Plus, Power, X } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import {
  createInventoryCategory,
  fetchInventoryCategories,
  updateInventoryCategory,
} from "../../api/inventoryCategories";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { SuccessMessage } from "../../components/common/SuccessMessage";
import { EmptyState } from "../../components/common/EmptyState";
import type { InventoryCategory } from "../../types/inventoryCategory";
import styles from "./InventoryCategoryPage.module.css";

/**
 * Bespoke, not built on TitleResourceManager: InventoryCategory has `name`
 * (not `title`) and no `updated_at` (CreatedAtMixin only) - the same reason
 * CategoriesPage.tsx is its own component rather than a TitleResourceManager
 * usage. Visually matches it and Locations/Priorities/Departments via the
 * same shared classes (tableShell, pillActive/pillInactive, field/input/select).
 *
 * Read-only for Technician: Company Administrator gets create/rename/
 * deactivate, Technician gets the list only - matching the backend's own
 * _VIEW_ROLES/_MANAGE_ROLES split for /inventory-categories. Employee never
 * reaches this page at all (see AppRouter's allowedRoles).
 */
export function InventoryCategoryPage() {
  const { user } = useAuth();
  const canManage = user?.role === "Company Administrator";
  const [searchParams, setSearchParams] = useSearchParams();

  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const newNameInputRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    setError(null);
    fetchInventoryCategories()
      .then(setCategories)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load inventory categories.")))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  useEffect(() => {
    if (canManage && searchParams.get("create") === "1") {
      newNameInputRef.current?.focus();
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) {
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createInventoryCategory(newName.trim());
      setCategories((prev) => [...prev, created]);
      setNewName("");
      setSuccessMessage("Inventory category added.");
    } catch (err) {
      setCreateError(getApiErrorMessage(err, "Could not create this inventory category."));
    } finally {
      setCreating(false);
    }
  }

  function startEdit(category: InventoryCategory) {
    setEditingId(category.id);
    setEditName(category.name);
    setRowError(null);
  }

  async function saveEdit(id: number) {
    if (!editName.trim()) {
      return;
    }
    setSavingId(id);
    setRowError(null);
    try {
      const updated = await updateInventoryCategory(id, { name: editName.trim() });
      setCategories((prev) => prev.map((c) => (c.id === id ? updated : c)));
      setEditingId(null);
      setSuccessMessage("Inventory category updated.");
    } catch (err) {
      setRowError(getApiErrorMessage(err, "Could not update this inventory category."));
    } finally {
      setSavingId(null);
    }
  }

  async function toggleActive(category: InventoryCategory) {
    setSavingId(category.id);
    setRowError(null);
    try {
      const updated = await updateInventoryCategory(category.id, {
        is_active: !category.is_active,
      });
      setCategories((prev) => prev.map((c) => (c.id === category.id ? updated : c)));
      setSuccessMessage(
        `Inventory category ${updated.is_active ? "activated" : "deactivated"}.`,
      );
    } catch (err) {
      setRowError(getApiErrorMessage(err, "Could not update this inventory category."));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>Inventory Categories</h1>
          {!loading && !error && (
            <p className={styles.count}>
              {categories.length} {categories.length === 1 ? "category" : "categories"}
            </p>
          )}
        </div>
      </div>

      {canManage && (
        <>
          <form onSubmit={handleCreate} className={styles.createForm}>
            <input
              ref={newNameInputRef}
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New inventory category name"
              className="input"
              disabled={creating}
            />
            <button type="submit" className="btn btn-primary" disabled={creating}>
              <Plus size={16} /> {creating ? "Adding..." : "Add Category"}
            </button>
          </form>
          {createError && <ErrorMessage message={createError} />}
        </>
      )}
      {successMessage && (
        <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      {loading && <Skeleton rows={4} height={48} />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && (
        <>
          {categories.length === 0 ? (
            <div className={styles.emptyWrap}>
              <EmptyState
                title="No inventory categories yet"
                description={
                  canManage
                    ? "Add your first inventory category using the form above."
                    : "Your Company Administrator hasn't added any inventory categories yet."
                }
              />
            </div>
          ) : (
            <div className="tableShell">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Created</th>
                    {canManage && <th aria-label="Actions" />}
                  </tr>
                </thead>
                <tbody>
                  {categories.map((category) => (
                    <tr key={category.id}>
                      <td>
                        {editingId === category.id ? (
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="input"
                            autoFocus
                          />
                        ) : (
                          category.name
                        )}
                      </td>
                      <td>
                        <span className={category.is_active ? "pillActive" : "pillInactive"}>
                          {category.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>{new Date(category.created_at).toLocaleDateString()}</td>
                      {canManage && (
                        <td className={styles.actions}>
                          {editingId === category.id ? (
                            <>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => saveEdit(category.id)}
                                disabled={savingId === category.id}
                              >
                                <Check size={14} /> {savingId === category.id ? "Saving..." : "Save"}
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => setEditingId(null)}
                              >
                                <X size={14} /> Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => startEdit(category)}
                              >
                                <Pencil size={14} /> Edit
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => toggleActive(category)}
                                disabled={savingId === category.id}
                              >
                                <Power size={14} />
                                {category.is_active ? "Deactivate" : "Activate"}
                              </button>
                            </>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {rowError && <ErrorMessage message={rowError} />}
        </>
      )}
    </div>
  );
}
