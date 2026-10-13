import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { KeyRound, Pencil, Plus, Power, Search, X } from "lucide-react";
import { fetchUsers, updateUser } from "../../api/users";
import { fetchDepartments } from "../../api/departments";
import { getApiErrorMessage } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { SuccessMessage } from "../../components/common/SuccessMessage";
import { EmptyState } from "../../components/common/EmptyState";
import { UserEditModal } from "../../components/admin/UserEditModal";
import { UserPasswordModal } from "../../components/admin/UserPasswordModal";
import { CreateUserModal } from "../../components/admin/CreateUserModal";
import { ROLE_ID_BY_NAME, ROLE_OPTIONS } from "../../types/user";
import type { AdminUser, AssignableRole } from "../../types/user";
import type { Department } from "../../types/department";
import styles from "./UsersPage.module.css";

const SEARCH_DEBOUNCE_MS = 350;

export function UsersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<AssignableRole | "">("");
  const [departmentFilter, setDepartmentFilter] = useState("");

  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [passwordUser, setPasswordUser] = useState<AdminUser | null>(null);
  const [creatingUser, setCreatingUser] = useState(() => searchParams.get("create") === "1");
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  const hasActiveFilters = Boolean(search || roleFilter || departmentFilter);

  // The "Create User" quick action deep-links here with ?create=1 to open
  // the modal immediately; strip it right after so it doesn't linger in the
  // address bar or re-open the modal on a later refresh/back-navigation.
  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchDepartments()
      .then(setDepartments)
      .catch(() => {
        // The department filter/edit-form dropdown is a convenience; the page still works without it.
      });
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  function load() {
    setLoading(true);
    setError(null);
    fetchUsers({
      search: search || undefined,
      role_id: roleFilter ? ROLE_ID_BY_NAME[roleFilter] : undefined,
      department_id: departmentFilter ? Number(departmentFilter) : undefined,
      limit: 500,
    })
      .then(setUsers)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load users.")))
      .finally(() => setLoading(false));
  }

  useEffect(load, [search, roleFilter, departmentFilter]); // eslint-disable-line

  function clearFilters() {
    setSearchInput("");
    setRoleFilter("");
    setDepartmentFilter("");
  }

  async function toggleActive(user: AdminUser) {
    setTogglingId(user.id);
    setToggleError(null);
    try {
      const updated = await updateUser(user.id, { is_active: !user.is_active });
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)));
      setSuccessMessage(`${updated.first_name} ${updated.last_name} ${updated.is_active ? "activated" : "deactivated"}.`);
    } catch (err) {
      setToggleError(getApiErrorMessage(err, "Could not update this user."));
    } finally {
      setTogglingId(null);
    }
  }

  function handleUserUpdated(updated: AdminUser) {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    setEditingUser(null);
    setSuccessMessage(`${updated.first_name} ${updated.last_name} updated.`);
  }

  function handleUserCreated(created: AdminUser) {
    setUsers((prev) => [created, ...prev]);
    setCreatingUser(false);
    setSuccessMessage(`${created.first_name} ${created.last_name} created.`);
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>Users</h1>
          {!loading && !error && (
            <p className={styles.count}>
              {users.length} {users.length === 1 ? "user" : "users"}
              {hasActiveFilters ? " matching your filters" : " total"}
            </p>
          )}
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreatingUser(true)}>
          <Plus size={16} /> Add User
        </button>
      </div>

      <div className={styles.filters}>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} aria-hidden="true" />
          <input
            type="search"
            placeholder="Search users..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className={`input ${styles.search}`}
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as AssignableRole | "")}
          className="select"
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          {ROLE_OPTIONS.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
        <select
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          className="select"
          aria-label="Filter by department"
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        {hasActiveFilters && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={clearFilters}>
            <X size={14} /> Clear filters
          </button>
        )}
      </div>

      {loading && <Skeleton rows={5} height={52} />}
      {error && <ErrorMessage message={error} />}
      {toggleError && <ErrorMessage message={toggleError} />}
      {successMessage && (
        <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      {!loading && !error && (
        <>
          {users.length === 0 ? (
            <div className={styles.emptyWrap}>
              <EmptyState
                title="No matching users"
                description="Try adjusting or clearing your filters."
              />
            </div>
          ) : (
            <div className="tableShell">
              <table>
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Department</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.username}</td>
                      <td>
                        {user.first_name} {user.last_name}
                      </td>
                      <td>{user.email}</td>
                      <td>{user.department?.title ?? "—"}</td>
                      <td>{user.role}</td>
                      <td>
                        <span className={user.is_active ? "pillActive" : "pillInactive"}>
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className={styles.actions}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => setEditingUser(user)}
                        >
                          <Pencil size={14} /> Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => setPasswordUser(user)}
                        >
                          <KeyRound size={14} /> Password
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => toggleActive(user)}
                          disabled={togglingId === user.id}
                        >
                          <Power size={14} />
                          {user.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {editingUser && (
        <UserEditModal
          user={editingUser}
          departments={departments}
          onClose={() => setEditingUser(null)}
          onSaved={handleUserUpdated}
        />
      )}

      {passwordUser && (
        <UserPasswordModal user={passwordUser} onClose={() => setPasswordUser(null)} />
      )}

      {creatingUser && (
        <CreateUserModal
          departments={departments}
          onClose={() => setCreatingUser(false)}
          onCreated={handleUserCreated}
        />
      )}
    </div>
  );
}
