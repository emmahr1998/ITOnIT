import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, Pencil, Plus, Power, X } from "lucide-react";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../common/Skeleton";
import { ErrorMessage } from "../common/ErrorMessage";
import { SuccessMessage } from "../common/SuccessMessage";
import { EmptyState } from "../common/EmptyState";
import styles from "./TitleResourceManager.module.css";

interface TitleResource {
  id: number;
  title: string;
  is_active?: boolean;
  created_at: string;
  updated_at: string;
}

interface TitleResourceManagerProps<T extends TitleResource> {
  resourceName: string;
  resourceNamePlural?: string;
  fetchAll: () => Promise<T[]>;
  create: (title: string) => Promise<T>;
  update: (id: number, patch: { title?: string; is_active?: boolean }) => Promise<T>;
  supportsActivation?: boolean;
}

export function TitleResourceManager<T extends TitleResource>({
  resourceName,
  resourceNamePlural,
  fetchAll,
  create,
  update,
  supportsActivation = false,
}: TitleResourceManagerProps<T>) {
  const plural = resourceNamePlural ?? `${resourceName}s`;
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const newTitleInputRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchAll()
      .then(setItems)
      .catch((err) => setError(getApiErrorMessage(err, `Could not load ${plural}.`)))
      .finally(() => setLoading(false));
    // Only ever runs once per mount - fetchAll/create/update are stable
    // props for the lifetime of a given admin page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Quick Actions deep-links here with ?create=1 to jump straight into the
  // always-visible inline create form; focus it immediately and strip the
  // param so it doesn't linger or re-focus on a later refresh/back-nav.
  useEffect(() => {
    if (searchParams.get("create") === "1") {
      newTitleInputRef.current?.focus();
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) {
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await create(newTitle.trim());
      setItems((prev) => [...prev, created]);
      setNewTitle("");
      setSuccessMessage(`${resourceName} added.`);
    } catch (err) {
      setCreateError(getApiErrorMessage(err, `Could not create this ${resourceName}.`));
    } finally {
      setCreating(false);
    }
  }

  function startEdit(item: T) {
    setEditingId(item.id);
    setEditTitle(item.title);
    setRowError(null);
  }

  async function saveEdit(id: number) {
    if (!editTitle.trim()) {
      return;
    }
    setSavingId(id);
    setRowError(null);
    try {
      const updated = await update(id, { title: editTitle.trim() });
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
      setEditingId(null);
      setSuccessMessage(`${resourceName} updated.`);
    } catch (err) {
      setRowError(getApiErrorMessage(err, `Could not update this ${resourceName}.`));
    } finally {
      setSavingId(null);
    }
  }

  async function toggleActive(item: T) {
    setSavingId(item.id);
    setRowError(null);
    try {
      const updated = await update(item.id, { is_active: !item.is_active });
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
      setSuccessMessage(`${resourceName} ${updated.is_active ? "activated" : "deactivated"}.`);
    } catch (err) {
      setRowError(getApiErrorMessage(err, `Could not update this ${resourceName}.`));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>{plural}</h1>
          {!loading && !error && (
            <p className={styles.count}>
              {items.length} {items.length === 1 ? resourceName.toLowerCase() : plural.toLowerCase()}
            </p>
          )}
        </div>
      </div>

      <form onSubmit={handleCreate} className={styles.createForm}>
        <input
          ref={newTitleInputRef}
          type="text"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder={`New ${resourceName.toLowerCase()} title`}
          className="input"
          disabled={creating}
        />
        <button type="submit" className="btn btn-primary" disabled={creating}>
          <Plus size={16} /> {creating ? "Adding..." : `Add ${resourceName}`}
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
          {items.length === 0 ? (
            <div className={styles.emptyWrap}>
              <EmptyState
                title={`No ${plural.toLowerCase()} yet`}
                description={`Add your first ${resourceName.toLowerCase()} using the form above.`}
              />
            </div>
          ) : (
            <div className="tableShell">
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    {supportsActivation && <th>Status</th>}
                    <th>Last Updated</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        {editingId === item.id ? (
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            className="input"
                            autoFocus
                          />
                        ) : (
                          item.title
                        )}
                      </td>
                      {supportsActivation && (
                        <td>
                          <span className={item.is_active ? "pillActive" : "pillInactive"}>
                            {item.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      )}
                      <td>{new Date(item.updated_at).toLocaleDateString()}</td>
                      <td className={styles.actions}>
                        {editingId === item.id ? (
                          <>
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => saveEdit(item.id)}
                              disabled={savingId === item.id}
                            >
                              <Check size={14} /> {savingId === item.id ? "Saving..." : "Save"}
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
                              onClick={() => startEdit(item)}
                            >
                              <Pencil size={14} /> Edit
                            </button>
                            {supportsActivation && (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => toggleActive(item)}
                                disabled={savingId === item.id}
                              >
                                <Power size={14} />
                                {item.is_active ? "Deactivate" : "Activate"}
                              </button>
                            )}
                          </>
                        )}
                      </td>
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
