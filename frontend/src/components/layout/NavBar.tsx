import { Menu } from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import { NotificationBell } from "./NotificationBell";
import styles from "./NavBar.module.css";

interface NavBarProps {
  onMenuClick: () => void;
}

function initials(firstName: string, lastName: string): string {
  return `${firstName[0] ?? ""}${lastName[0] ?? ""}`.toUpperCase();
}

export function NavBar({ onMenuClick }: NavBarProps) {
  const { user } = useAuth();

  return (
    <header className={styles.navbar}>
      <button
        type="button"
        className={styles.menuButton}
        onClick={onMenuClick}
        aria-label="Toggle navigation menu"
      >
        <Menu size={20} />
      </button>

      {user && (
        <div className={styles.userArea}>
          <NotificationBell />
          <span className={styles.divider} aria-hidden="true" />
          <span className={styles.avatar} aria-hidden="true">
            {initials(user.first_name, user.last_name)}
          </span>
          <span className={styles.userInfo}>
            <span className={styles.userName}>
              {user.first_name} {user.last_name}
            </span>
            <span className={styles.roleBadge}>{user.role}</span>
          </span>
        </div>
      )}
    </header>
  );
}
