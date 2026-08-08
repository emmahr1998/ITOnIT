import { Link, Navigate } from "react-router-dom";
import { CheckCircle2, ClipboardList, ShieldCheck, Users2 } from "lucide-react";
import { Mascot } from "../components/common/Mascot";
import { useAuth } from "../auth/useAuth";
import styles from "./LandingPage.module.css";

const HIGHLIGHTS = [
  {
    icon: ClipboardList,
    title: "Submit and track tickets",
    description: "Raise an IT request in seconds and follow its status from open to resolved.",
  },
  {
    icon: Users2,
    title: "Role-based access",
    description: "Employees, technicians, and company administrators each see exactly what they need.",
  },
  {
    icon: ShieldCheck,
    title: "A full history on every request",
    description: "Every status change, comment, and assignment is recorded and auditable.",
  },
];

/**
 * The only page reachable without logging in besides /login and /register.
 * Deliberately shows no ticket data or any other internal information -
 * just marketing copy and links into the authenticated app, since ticket
 * content is treated as sensitive internal data everywhere else in ITOnIT.
 * /register is company registration, not personal account creation - see
 * RegisterPage.
 */
export function LandingPage() {
  const { status } = useAuth();

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <Mascot size={36} />
          <span>ITOnIT</span>
        </div>
        <nav className={styles.headerActions}>
          <Link to="/login" className="btn btn-secondary">
            Sign in
          </Link>
          <Link to="/register" className="btn btn-primary">
            Register Company
          </Link>
        </nav>
      </header>

      <main className={styles.hero}>
        <Mascot size={96} className={styles.heroMascot} />
        <h1 className={styles.heroTitle}>Fast, modern IT support for your organization.</h1>
        <p className={styles.heroSubtitle}>
          ITOnIT is a multi-tenant IT ticketing platform - sign in to your company&rsquo;s
          workspace, or register your company to get started.
        </p>
        <div className={styles.heroActions}>
          <Link to="/register" className="btn btn-primary">
            Register Your Company
          </Link>
          <Link to="/login" className="btn btn-secondary">
            Sign in
          </Link>
        </div>
      </main>

      <section className={styles.highlights}>
        {HIGHLIGHTS.map(({ icon: Icon, title, description }) => (
          <div key={title} className={styles.highlightCard}>
            <span className={styles.highlightIcon}>
              <Icon size={22} strokeWidth={2} />
            </span>
            <h2 className={styles.highlightTitle}>{title}</h2>
            <p className={styles.highlightDescription}>{description}</p>
          </div>
        ))}
      </section>

      <footer className={styles.footer}>
        <span>
          <CheckCircle2 size={14} strokeWidth={2} /> Registering creates your company&rsquo;s
          workspace with you as its Company Administrator.
        </span>
      </footer>
    </div>
  );
}
