import type { ReactNode } from "react";
import { PublicNavbar } from "./PublicNavbar";
import { PublicFooter } from "./PublicFooter";
import styles from "../../pages/LandingPage.module.css";

/**
 * The shared skeleton every public marketing page (landing, Features, How
 * It Works, Roles, Help Center) renders: header, content, footer - kept in
 * one place so navigation and the footer stay identical across all of
 * them, rather than each page repeating the same three lines of JSX.
 */
export function PublicPageShell({ children }: { children: ReactNode }) {
  return (
    <div className={styles.page}>
      <PublicNavbar />
      <main>{children}</main>
      <PublicFooter />
    </div>
  );
}
