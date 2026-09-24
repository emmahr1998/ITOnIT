import { useState } from "react";
import { Outlet } from "react-router-dom";
import { NavBar } from "../layout/NavBar";
import { PlatformSidebar } from "./PlatformSidebar";
import styles from "../layout/AppLayout.module.css";

/**
 * Platform-console equivalent of AppLayout (components/layout/AppLayout.tsx)
 * - identical shell mechanics (sidebar + top bar + routed content, same
 * mobile-drawer breakpoint), reusing that module's CSS directly, with
 * PlatformSidebar's platform-only nav in place of the tenant Sidebar.
 * NavBar is reused completely unmodified: it only reads
 * user.first_name/last_name/role from AuthContext and renders the static
 * NotificationBell (no tenant API calls in either), so it works identically
 * for a System Administrator session.
 */
export function PlatformLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className={styles.shell}>
      <div className={`${styles.sidebarWrap} ${mobileNavOpen ? styles.sidebarOpen : ""}`}>
        <PlatformSidebar onNavigate={() => setMobileNavOpen(false)} />
      </div>

      {mobileNavOpen && (
        <button
          type="button"
          className={styles.backdrop}
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <div className={styles.main}>
        <NavBar onMenuClick={() => setMobileNavOpen((open) => !open)} />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
