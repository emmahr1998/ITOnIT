import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { Mascot } from "../common/Mascot";
import styles from "../../pages/LandingPage.module.css";

/**
 * The public site's footer - shared by every public page (landing,
 * Features, How It Works, Roles, Help Center), not just LandingPage,
 * which is why this lives as its own component rather than inline JSX
 * repeated on each one. Reuses LandingPage.module.css's existing footer
 * classes rather than a new stylesheet, same convention as RegisterPage
 * reusing LoginPage.module.css.
 */
export function PublicFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerTop}>
        <div className={styles.footerBrand}>
          <div className={styles.footerBrandRow}>
            <Mascot size={28} />
            <span>ITOnIT</span>
          </div>
          <p className={styles.footerTagline}>Fast, modern IT support for your organization.</p>
        </div>

        <div className={styles.footerColumns}>
          <div className={styles.footerColumn}>
            <span className={styles.footerColumnTitle}>Product</span>
            <Link to="/features">Features</Link>
            <Link to="/how-it-works">How It Works</Link>
            <Link to="/roles">Roles</Link>
            <Link to="/help">Help Center</Link>
          </div>
          <div className={styles.footerColumn}>
            <span className={styles.footerColumnTitle}>Account</span>
            <Link to="/login">Sign In</Link>
            <Link to="/register">Register Company</Link>
          </div>
        </div>
      </div>

      <div className={styles.footerBottom}>
        <span className={styles.footerNote}>
          <CheckCircle2 size={14} strokeWidth={2} /> Registering creates your company&rsquo;s
          workspace with you as its Company Administrator.
        </span>
        <Link to="/platform/login" className={styles.platformLink}>
          Platform Administration
        </Link>
      </div>
    </footer>
  );
}
