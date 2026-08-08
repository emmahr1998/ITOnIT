import type { ComponentType } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Building2,
  Info,
  LayoutDashboard,
  LogOut,
  MapPin,
  PlusCircle,
  Tags,
  Ticket,
  Users,
} from "lucide-react";
import { useAuth } from "../../auth/useAuth";
import type { Role } from "../../types/auth";
import { Mascot } from "../common/Mascot";
import styles from "./Sidebar.module.css";

interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  end?: boolean;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

/**
 * Per-role nav. Employee sees "My Tickets", Technician "Assigned Tickets",
 * Company Administrator "All Tickets" - all point at the same /tickets
 * route, which the backend already scopes correctly per role (see
 * GET /all-tickets). The Company-Administrator-only admin console is split
 * into a MAIN section (Dashboard/Tickets) and a MANAGEMENT section (the
 * resources an admin configures). Priorities has no management page here -
 * the four levels are fixed values, not admin-editable records - but
 * priority data itself still flows everywhere else (tickets, filters,
 * badges, charts). System Administrator has no real UI yet - it's a
 * platform-level role served by its own console in a future milestone, not
 * this authenticated company app shell.
 */
const NAV_BY_ROLE: Record<Role, NavSection[]> = {
  Employee: [
    {
      items: [
        { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
        { label: "My Tickets", path: "/tickets", icon: Ticket, end: true },
        { label: "Create Ticket", path: "/tickets/new", icon: PlusCircle },
      ],
    },
  ],
  Technician: [
    {
      items: [
        { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
        { label: "Assigned Tickets", path: "/tickets", icon: Ticket, end: true },
      ],
    },
  ],
  "Company Administrator": [
    {
      title: "Main",
      items: [
        { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
        { label: "All Tickets", path: "/tickets", icon: Ticket, end: true },
      ],
    },
    {
      title: "Management",
      items: [
        { label: "Users", path: "/admin/users", icon: Users },
        { label: "Departments", path: "/admin/departments", icon: Building2 },
        { label: "Categories", path: "/admin/categories", icon: Tags },
        { label: "Locations", path: "/admin/locations", icon: MapPin },
      ],
    },
  ],
  "System Administrator": [],
};

const FUTURE_PAGES = [{ label: "Reports", icon: BarChart3 }];

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const { user, logout } = useAuth();

  const linkClassName = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.link} ${styles.linkActive}` : styles.link;

  const sections = user ? NAV_BY_ROLE[user.role] : [];

  return (
    <nav className={styles.sidebar} aria-label="Main navigation">
      <div className={styles.brand}>
        <Mascot size={32} className={styles.brandMascot} />
        <span>ITOnIT</span>
      </div>

      <div className={styles.sections}>
        {sections.map((section, index) => (
          <div className={styles.section} key={section.title ?? index}>
            {section.title && <div className={styles.sectionTitle}>{section.title}</div>}
            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.end}
                  className={linkClassName}
                  onClick={onNavigate}
                >
                  <Icon size={18} strokeWidth={2} />
                  {item.label}
                </NavLink>
              );
            })}
          </div>
        ))}

        <div className={styles.section}>
          {FUTURE_PAGES.map(({ label, icon: Icon }) => (
            <span key={label} className={styles.linkDisabled} aria-disabled="true">
              <span className={styles.linkDisabledLabel}>
                <Icon size={18} strokeWidth={2} />
                {label}
              </span>
              <span className={styles.comingSoon}>Soon</span>
            </span>
          ))}
        </div>
      </div>

      <div className={styles.footer}>
        <NavLink to="/about" className={linkClassName} onClick={onNavigate}>
          <Info size={18} strokeWidth={2} />
          About ITOnIT
        </NavLink>
        <button type="button" className={styles.logoutButton} onClick={logout}>
          <LogOut size={18} strokeWidth={2} />
          Log out
        </button>
      </div>
    </nav>
  );
}
