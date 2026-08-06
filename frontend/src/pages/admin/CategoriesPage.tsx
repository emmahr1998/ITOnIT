import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { createCategory, deleteCategory, fetchCategories, updateCategory } from "../../api/categories";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { SuccessMessage } from "../../components/common/SuccessMessage";
import { EmptyState } from "../../components/common/EmptyState";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import type { Category } from "../../types/category";
import styles from "./CategoriesPage.module.css";

export function CategoriesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const newNameInputRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const [pendingDelete, setPendingDelete] = useState<Category | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    setError(null);
    fetchCategories()
      .then(setCategories)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load categories.")))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  // Quick Actions deep-links here with ?create=1 to jump straight into the
  // always-visible inline create form; focus it immediately and strip the
  // param so it doesn't linger or re-focus on a later refresh/back-nav.
  useEffect(() => {
    if (searchParams.get("create") === "1") {
      newNameInputRef.current?.focus();
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) {
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createCategory(newName.trim(), newDescription.trim() || null);
      setCategories((prev) => [...prev, created]);
      setNewName("");
      setNewDescription("");
      setSuccessMessage("Category added.");
    } catch (err) {
      setCreateError(getApiErrorMessage(err, "Could not create this category."));
    } finally {
      setCreating(false);
    }
  }

  function startEdit(category: Category) {
    setEditingId(category.id);
    setEditName(category.name);
    setEditDescription(category.description ?? "");
    setRowError(null);
  }

  async function saveEdit(id: number) {
    if (!editName.trim()) {
      return;
    }
    setSavingId(id);
    setRowError(null);
    try {
      const updated = await updateCategory(id, editName.trim(), editDescription.trim() || null);
      setCategories((prev) => prev.map((c) => (c.id === id ? updated : c)));
      setEditingId(null);
      setSuccessMessage("Category updated.");
    } catch (err) {
      setRowError(getApiErrorMessage(err, "Could not update this category."));
    } finally {
      setSavingId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCategory(pendingDelete.id);
      setCategories((prev) => prev.filter((c) => c.id !== pendingDelete.id));
      setPendingDelete(null);
      setSuccessMessage("Category deleted.");
    } catch (err) {
      setDeleteError(getApiErrorMessage(err, "Could not delete this category."));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className={styles.page}>
      <div>
        <h1 className={styles.heading}>Categories</h1>
        {!loading && !error && (
          <p className={styles.count}>
            {categories.length} {categories.length === 1 ? "category" : "categories"}
          </p>
        )}
      </div>

      <form onSubmit={handleCreate} className={styles.createForm}>
        <input
          ref={newNameInputRef}
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Category name"
          className="input"
          disabled={creating}
        />
        <input
          type="text"
          value={newDescription}
          onChange={(e) => setNewDescription(e.target.value)}
          placeholder="Description (optional)"
          className="input"
          disabled={creating}
        />
        <button type="submit" className="btn btn-primary" disabled={creating}>
          <Plus size={16} /> {creating ? "Adding..." : "Add Category"}
        </button>
      </form>
      {createError && <ErrorMessage message={createError} />}
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
                title="No categories yet"
                description="Add your first category using the form above."
              />
            </div>
          ) : (
            <div className="tableShell">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {categories.map((category) => (
                    <tr key={category.id}>
                      {editingId === category.id ? (
                        <>
                          <td>
                            <input
                              type="text"
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              className="input"
                              autoFocus
                            />
                          </td>
                          <td>
                            <input
                              type="text"
                              value={editDescription}
                              onChange={(e) => setEditDescription(e.target.value)}
                              className="input"
                            />
                          </td>
                          <td className={styles.actions}>
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
                          </td>
                        </>
                      ) : (
                        <>
                          <td>{category.name}</td>
                          <td>{category.description ?? "—"}</td>
                          <td className={styles.actions}>
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => startEdit(category)}
                            >
                              <Pencil size={14} /> Edit
                            </button>
                            <button
                              type="button"
                              className="btn btn-ghost-danger btn-sm"
                              onClick={() => setPendingDelete(category)}
                            >
                              <Trash2 size={14} /> Delete
                            </button>
                          </td>
                        </>
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

      {pendingDelete && (
        <ConfirmDialog
          title="Delete category"
          message={`Delete "${pendingDelete.name}"? This cannot be undone. Categories still referenced by tickets can't be deleted.`}
          confirmLabel="Delete"
          danger
          busy={deleting}
          error={deleteError}
          onConfirm={confirmDelete}
          onCancel={() => {
            setPendingDelete(null);
            setDeleteError(null);
          }}
        />
      )}
    </div>
  );
}
