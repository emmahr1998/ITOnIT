import { Building2, LayoutDashboard, LogOut } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../auth/useAuth";
import { Mascot } from "../common/Mascot";
import styles from "../layout/Sidebar.module.css";

interface PlatformSidebarProps {
  onNavigate?: () => void;
}

/**
 * Platform-console equivalent of Sidebar (components/layout/Sidebar.tsx).
 * Deliberately a separate, small component rather than extending
 * NAV_BY_ROLE there - that map is tenant-role-shaped and already
 * deliberately empty for "System Administrator" (see its own docstring);
 * folding platform-only nav into it would blur two navigation models this
 * milestone requires stay clearly separated. Reuses Sidebar's own CSS
 * module so both consoles still read as the same product.
 */
export function PlatformSidebar({ onNavigate }: PlatformSidebarProps) {
  const { logout } = useAuth();

  const linkClassName = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.link} ${styles.linkActive}` : styles.link;

  return (
    <nav className={styles.sidebar} aria-label="Platform navigation">
      <div className={styles.brand}>
        <Mascot size={32} className={styles.brandMascot} />
        <span>ITOnIT Platform</span>
      </div>

      <div className={styles.sections}>
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Main</div>
          <NavLink to="/platform" end className={linkClassName} onClick={onNavigate}>
            <LayoutDashboard size={18} strokeWidth={2} />
            Overview
          </NavLink>
          <NavLink to="/platform/companies" className={linkClassName} onClick={onNavigate}>
            <Building2 size={18} strokeWidth={2} />
            Companies
          </NavLink>
        </div>
      </div>

      <div className={styles.footer}>
        <div className={styles.sectionTitle}>Account</div>
        <button type="button" className={styles.logoutButton} onClick={logout}>
          <LogOut size={18} strokeWidth={2} />
          Log out
        </button>
      </div>
    </nav>
  );
}
