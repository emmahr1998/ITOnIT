import { useState, type FormEvent } from "react";
import { Modal } from "../common/Modal";
import { ErrorMessage } from "../common/ErrorMessage";
import { SuccessMessage } from "../common/SuccessMessage";
import { adminSetPassword } from "../../api/users";
import { getApiErrorMessage } from "../../api/client";
import type { AdminUser } from "../../types/user";
import styles from "./UserEditModal.module.css";

interface UserPasswordModalProps {
  user: AdminUser;
  onClose: () => void;
}

export function UserPasswordModal({ user, onClose }: UserPasswordModalProps) {
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await adminSetPassword(user.id, newPassword);
      setSuccess(true);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not update the password."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={`Set Password for ${user.first_name} ${user.last_name}`} onClose={onClose}>
      {success ? (
        <SuccessMessage message="Password updated successfully." duration={0} />
      ) : (
        <form onSubmit={handleSubmit} className={styles.form}>
          <label className="field">
            <span className="fieldLabel">
              New Password<span className="requiredMark">*</span>
            </span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="input"
              autoFocus
            />
          </label>

          {error && <ErrorMessage message={error} />}

          <div className={styles.actions}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Set Password"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
