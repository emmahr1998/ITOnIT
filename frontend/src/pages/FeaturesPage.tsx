import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Boxes,
  History,
  KeyRound,
  Lock,
  Settings,
  ShieldCheck,
  Ticket,
} from "lucide-react";
import { PublicPageShell } from "../components/public/PublicPageShell";
import styles from "./LandingPage.module.css";

const FEATURE_GROUPS = [
  {
    icon: Ticket,
    title: "Ticket Management",
    items: [
      "Report and track IT issues from submission through resolution",
      "Organize tickets by status, priority, category, and location",
      "Assign tickets to technicians with clear ownership",
      "Comments on every ticket keep the full conversation in one place",
      "File attachments can be added directly to a ticket",
      "A complete, automatically recorded history of every status change and update",
    ],
  },
  {
    icon: Boxes,
    title: "Inventory & Asset Management",
    items: [
      "Track both serialized assets (e.g. laptops) and bulk stock in one place",
      "Organize inventory into categories and locations",
      "Reserve or consume inventory directly from a ticket, linking equipment to the issue it supports",
      "A full transaction history for every inventory item",
      "Low-stock and warranty-expiration visibility on the dashboard",
    ],
  },
  {
    icon: BarChart3,
    title: "Dashboards & Analytics",
    items: [
      "An at-a-glance dashboard of open, in-progress, and high-priority tickets",
      "Breakdowns of tickets by status, category, and priority",
      "Monthly trends for tickets created vs. resolved",
      "Inventory breakdowns by status and category, including low-stock and warranty alerts",
    ],
  },
  {
    icon: Settings,
    title: "Company Administration",
    items: [
      "Manage your team's users and their roles",
      "Configure departments, locations, categories, and priorities to match how your organization works",
      "Organize inventory categories",
      "Company profile settings, including a custom logo",
    ],
  },
];

const SECURITY_POINTS = [
  {
    icon: ShieldCheck,
    title: "Role-based access",
    description:
      "Employees, Technicians, and Company Administrators each see and can do only what their role allows - see the Roles page for the full breakdown.",
  },
  {
    icon: Lock,
    title: "Per-company data isolation",
    description:
      "ITOnIT is multi-tenant: every company's tickets, inventory, and users are kept completely separate from every other company's.",
  },
  {
    icon: KeyRound,
    title: "Authenticated sessions",
    description:
      "Sign-in is protected by an authenticated session, with your company code required alongside your username and password.",
  },
  {
    icon: History,
    title: "Full audit trail",
    description:
      "Status changes, comments, and assignments are recorded automatically on every ticket, so nothing gets lost.",
  },
];

/**
 * Dedicated /features page - a deeper version of the summary already on
 * the landing page's own #features section (left in place there as an
 * overview for visitors who land on "/"). Every item listed here is real,
 * existing ITOnIT functionality - nothing advertised that the application
 * doesn't actually do (see this page's own investigation in the ITOnIT
 * project history before writing this content).
 */
export function FeaturesPage() {
  return (
    <PublicPageShell>
      <section className={styles.hero}>
        <h1 className={styles.heroTitle}>Everything your IT team needs, in one place.</h1>
        <p className={styles.heroSubtitle}>
          ITOnIT brings ticket management and inventory tracking together, so your team can
          report issues, resolve them, and keep track of the equipment involved - all without
          switching tools.
        </p>
        <div className={styles.heroActions}>
          <Link to="/register" className="btn btn-primary">
            Register Your Company
          </Link>
          <Link to="/login" className="btn btn-secondary">
            Sign In
          </Link>
        </div>
      </section>

      <section className={styles.features} aria-labelledby="features-heading">
        <h2 id="features-heading" className={styles.sectionTitle}>
          Features
        </h2>
        <div className={styles.featureGrid}>
          {FEATURE_GROUPS.map(({ icon: Icon, title, items }) => (
            <div key={title} className={styles.featureCard}>
              <span className={styles.featureIcon} aria-hidden="true">
                <Icon size={22} strokeWidth={2} />
              </span>
              <h3 className={styles.featureTitle}>{title}</h3>
              <ul className={styles.featureList}>
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.trust} aria-labelledby="security-heading">
        <h2 id="security-heading" className={styles.sectionTitle}>
          Organized and secure by design
        </h2>
        <div className={styles.trustGrid}>
          {SECURITY_POINTS.map(({ icon: Icon, title, description }) => (
            <div key={title} className={styles.trustCard}>
              <span className={styles.trustIcon} aria-hidden="true">
                <Icon size={20} strokeWidth={2} />
              </span>
              <h3 className={styles.trustTitle}>{title}</h3>
              <p className={styles.trustDescription}>{description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.finalCta} aria-labelledby="features-cta-heading">
        <h2 id="features-cta-heading" className={styles.finalCtaTitle}>
          Ready to see it in action?
        </h2>
        <p className={styles.finalCtaSubtitle}>Set up your company&rsquo;s workspace in minutes.</p>
        <div className={styles.heroActions}>
          <Link to="/register" className="btn btn-primary">
            Register Your Company <ArrowRight size={16} />
          </Link>
        </div>
        <p className={styles.finalCtaSignIn}>
          Already using ITOnIT? <Link to="/login">Sign In</Link>
        </p>
      </section>
    </PublicPageShell>
  );
}
