import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Mascot } from "../common/Mascot";
import styles from "./PublicNavbar.module.css";

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Roles", href: "#roles" },
];

/**
 * The public site's header - logo, in-page section links, and Sign In/Get
 * Started. Deliberately separate from AppLayout/Sidebar (tenant nav) and
 * PlatformLayout/PlatformSidebar (platform nav): this component has no
 * dependency on useAuth or any authenticated session at all, since it's
 * rendered only for unauthenticated visitors on LandingPage.
 */
export function PublicNavbar() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  // Escape closes the mobile menu, matching every other dismissible panel
  // in the app (Modal, NotificationBell). Focus returns to the toggle: the
  // focused menu link unmounts on close, which would otherwise drop focus
  // to <body>.
  useEffect(() => {
    if (!open) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  function close() {
    setOpen(false);
  }

  return (
    <header className={styles.header}>
      <div className={styles.bar}>
        <Link to="/" className={styles.brand} onClick={close}>
          <Mascot size={32} />
          <span>ITOnIT</span>
        </Link>

        <nav className={styles.desktopNav} aria-label="Primary">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className={styles.navLink}>
              {link.label}
            </a>
          ))}
        </nav>

        <div className={styles.desktopActions}>
          <Link to="/login" className="btn btn-secondary btn-sm">
            Sign In
          </Link>
          <Link to="/register" className="btn btn-primary btn-sm">
            Get Started
          </Link>
        </div>

        <button
          ref={toggleRef}
          type="button"
          className={styles.menuToggle}
          aria-label="Toggle navigation menu"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <div className={styles.mobileMenu}>
          <nav aria-label="Primary" className={styles.mobileNav}>
            {NAV_LINKS.map((link) => (
              <a key={link.href} href={link.href} className={styles.mobileNavLink} onClick={close}>
                {link.label}
              </a>
            ))}
          </nav>
          <div className={styles.mobileActions}>
            <Link to="/login" className="btn btn-secondary" onClick={close}>
              Sign In
            </Link>
            <Link to="/register" className="btn btn-primary" onClick={close}>
              Get Started
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
