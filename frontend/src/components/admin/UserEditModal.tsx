import { useState, type FormEvent } from "react";
import { Modal } from "../common/Modal";
import { ErrorMessage } from "../common/ErrorMessage";
import { updateUser } from "../../api/users";
import { getApiErrorMessage } from "../../api/client";
import { ROLE_ID_BY_NAME, ROLE_OPTIONS } from "../../types/user";
import type { AdminUser } from "../../types/user";
import type { Department } from "../../types/department";
import type { Role } from "../../types/auth";
import styles from "./UserEditModal.module.css";

interface UserEditModalProps {
  user: AdminUser;
  departments: Department[];
  onClose: () => void;
  onSaved: (user: AdminUser) => void;
}

export function UserEditModal({ user, departments, onClose, onSaved }: UserEditModalProps) {
  const [username, setUsername] = useState(user.username);
  const [firstName, setFirstName] = useState(user.first_name);
  const [lastName, setLastName] = useState(user.last_name);
  const [email, setEmail] = useState(user.email);
  const [phoneNumber, setPhoneNumber] = useState(user.phone_number ?? "");
  const [departmentId, setDepartmentId] = useState(user.department?.id.toString() ?? "");
  const [role, setRole] = useState<Role>(user.role);
  const [isActive, setIsActive] = useState(user.is_active);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await updateUser(user.id, {
        username: username.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone_number: phoneNumber.trim() || null,
        department_id: departmentId ? Number(departmentId) : null,
        role_id: ROLE_ID_BY_NAME[role],
        is_active: isActive,
      });
      onSaved(updated);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save this user."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={`Edit ${user.first_name} ${user.last_name}`} onClose={onClose}>
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
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="select"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className={styles.checkboxField}>
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          <span>Active</span>
        </label>

        {error && <ErrorMessage message={error} />}

        <div className={styles.actions}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
