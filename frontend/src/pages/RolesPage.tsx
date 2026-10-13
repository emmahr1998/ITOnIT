import { Link } from "react-router-dom";
import { ArrowRight, Building2, Server, Users2, Wrench } from "lucide-react";
import { PublicPageShell } from "../components/public/PublicPageShell";
import landingStyles from "./LandingPage.module.css";
import styles from "./RolesPage.module.css";

const ROLES = [
  {
    icon: Users2,
    title: "Employee",
    summary: "Reports issues and follows their own tickets.",
    items: [
      "Report new IT issues as tickets",
      "View and comment on their own tickets",
      "Track the status and history of issues they've reported",
    ],
  },
  {
    icon: Wrench,
    title: "Technician",
    summary: "Works assigned tickets and the equipment behind them.",
    items: [
      "View and update tickets assigned to them",
      "Change ticket status as work progresses",
      "Comment on tickets to communicate progress",
      "Reserve or consume inventory needed for a ticket",
    ],
  },
  {
    icon: Building2,
    title: "Company Administrator",
    summary: "Manages one company's workspace end to end.",
    items: [
      "Manage the company's users and their roles",
      "Configure departments, locations, categories, and priorities",
      "Oversee every ticket in the company, including assigning and deleting tickets",
      "Manage inventory and inventory categories",
      "View company-wide dashboards and analytics",
      "Update company settings, including the company's logo and code",
    ],
  },
  {
    icon: Server,
    title: "System Administrator",
    summary: "Operates the ITOnIT platform itself, not any one company.",
    items: [
      "Provision new company workspaces on request",
      "View a platform-wide overview across every company",
      "Activate or deactivate a company's account",
      "Has no access to any single company's tickets, inventory, or day-to-day data",
    ],
  },
];

/**
 * Dedicated /roles page. Role capabilities here are drawn from the
 * backend's actual route-level permission checks (require_roles(...) in
 * app/api/routes/*.py) rather than guessed - nothing listed here is
 * aspirational. Deliberately stops at what each role can DO, not how
 * permissions are enforced internally (JWTs, route guards, etc.) - see
 * this page's own "don't expose implementation detail" constraint.
 */
export function RolesPage() {
  return (
    <PublicPageShell>
      <section className={landingStyles.hero}>
        <h1 className={landingStyles.heroTitle}>Built for every role on your team.</h1>
        <p className={landingStyles.heroSubtitle}>
          ITOnIT gives each person exactly the access their job needs - nothing more, nothing
          less.
        </p>
        <div className={landingStyles.heroActions}>
          <Link to="/register" className="btn btn-primary">
            Register Your Company
          </Link>
          <Link to="/login" className="btn btn-secondary">
            Sign In
          </Link>
        </div>
      </section>

      <section className={landingStyles.roles} aria-labelledby="roles-heading">
        <h2 id="roles-heading" className={landingStyles.sectionTitle}>
          The four ITOnIT roles
        </h2>
        <div className={styles.grid}>
          {ROLES.map(({ icon: Icon, title, summary, items }) => (
            <div
              key={title}
              className={`${landingStyles.roleCard} ${
                title === "System Administrator" ? styles.platformCard : ""
              }`}
            >
              <span className={landingStyles.roleIcon} aria-hidden="true">
                <Icon size={22} strokeWidth={2} />
              </span>
              <h3 className={landingStyles.roleTitle}>{title}</h3>
              <p className={styles.compareText} style={{ margin: 0 }}>
                {summary}
              </p>
              <ul className={landingStyles.roleList}>
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className={styles.compare}>
          <h3 className={styles.compareTitle}>
            Company Administrator vs. System Administrator
          </h3>
          <p className={styles.compareText}>
            A <strong>Company Administrator</strong> manages one company&rsquo;s own workspace -
            its users, tickets, inventory, and settings. Every company that registers with
            ITOnIT gets its own Company Administrator, created automatically as the first user
            during registration.
          </p>
          <p className={styles.compareText}>
            A <strong>System Administrator</strong> operates the ITOnIT platform itself, across
            every company. They provision new company workspaces and can activate or deactivate
            a company&rsquo;s account, but they have no access to any individual company&rsquo;s
            tickets, inventory, or users - that data stays private to each company and its own
            Company Administrator.
          </p>
        </div>
      </section>

      <section className={landingStyles.finalCta} aria-labelledby="roles-cta-heading">
        <h2 id="roles-cta-heading" className={landingStyles.finalCtaTitle}>
          Ready to get started?
        </h2>
        <p className={landingStyles.finalCtaSubtitle}>
          Set up your company&rsquo;s workspace in minutes.
        </p>
        <div className={landingStyles.heroActions}>
          <Link to="/register" className="btn btn-primary">
            Register Your Company <ArrowRight size={16} />
          </Link>
        </div>
        <p className={landingStyles.finalCtaSignIn}>
          Already using ITOnIT? <Link to="/login">Sign In</Link>
        </p>
      </section>
    </PublicPageShell>
  );
}
