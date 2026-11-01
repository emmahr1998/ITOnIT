import { useState, type FormEvent } from "react";
import { Modal } from "../common/Modal";
import { ErrorMessage } from "../common/ErrorMessage";
import { createUser } from "../../api/users";
import { getApiErrorMessage } from "../../api/client";
import type { AdminUser, RoleOption } from "../../types/user";
import type { Department } from "../../types/department";
import styles from "./UserEditModal.module.css";

interface CreateUserModalProps {
  departments: Department[];
  /** From GET /roles - the only source of real role ids. */
  roles: RoleOption[];
  rolesError: string | null;
  onClose: () => void;
  onCreated: (user: AdminUser) => void;
}

export function CreateUserModal({
  departments,
  roles,
  rolesError,
  onClose,
  onCreated,
}: CreateUserModalProps) {
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  // Defaults to Employee by *name*, resolved to its real id from GET /roles.
  const [roleId, setRoleId] = useState("");
  const effectiveRoleId = roleId || roles.find((r) => r.name === "Employee")?.id.toString() || "";
  const [password, setPassword] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!effectiveRoleId) {
      setError(rolesError ?? "Select a role for this user.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createUser({
        username: username.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone_number: phoneNumber.trim() || null,
        department_id: departmentId ? Number(departmentId) : null,
        role_id: Number(effectiveRoleId),
        password,
      });
      onCreated(created);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not create this user."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="Create User" onClose={onClose}>
      <form onSubmit={handleSubmit} className={styles.form}>
        <label className="field">
          <span className="fieldLabel">
            Username<span className="requiredMark">*</span>
          </span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="input"
            autoFocus
          />
        </label>

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">
              First Name<span className="requiredMark">*</span>
            </span>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              className="input"
            />
          </label>
          <label className="field">
            <span className="fieldLabel">
              Last Name<span className="requiredMark">*</span>
            </span>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              className="input"
            />
          </label>
        </div>

        <label className="field">
          <span className="fieldLabel">
            Email<span className="requiredMark">*</span>
          </span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="input"
          />
        </label>

        <label className="field">
          <span className="fieldLabel">Phone Number</span>
          <input
            type="tel"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            className="input"
          />
        </label>

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">Department</span>
            <select
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              className="select"
            >
              <option value="">No department</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="fieldLabel">Role</span>
            <select
              value={effectiveRoleId}
              onChange={(e) => setRoleId(e.target.value)}
              className="select"
              required
              disabled={roles.length === 0}
            >
              {roles.length === 0 && <option value="">Roles unavailable</option>}
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field">
          <span className="fieldLabel">
            Password<span className="requiredMark">*</span>
          </span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="input"
            autoComplete="new-password"
          />
        </label>

        {error && <ErrorMessage message={error} />}

        <div className={styles.actions}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Creating..." : "Create User"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
