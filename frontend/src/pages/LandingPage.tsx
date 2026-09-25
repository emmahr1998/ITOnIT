import { Link, Navigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Boxes,
  Building2,
  CheckCircle2,
  ClipboardList,
  History,
  KeyRound,
  Lock,
  PackageCheck,
  Settings,
  ShieldCheck,
  Ticket,
  UserCog,
  Users2,
  Wrench,
} from "lucide-react";
import { Mascot } from "../components/common/Mascot";
import { PublicNavbar } from "../components/public/PublicNavbar";
import { useAuth } from "../auth/useAuth";
import styles from "./LandingPage.module.css";

const FEATURE_GROUPS = [
  {
    icon: Ticket,
    title: "Ticket Management",
    items: [
      "Report and track IT issues from submission to resolution",
      "Assign tickets to technicians with clear ownership",
      "Priorities and categories keep work organized",
      "Comments, attachments, and a full history on every ticket",
    ],
  },
  {
    icon: Boxes,
    title: "Inventory Management",
    items: [
      "Track serialized assets and bulk stock in one place",
      "Reserve or use inventory directly on a ticket",
      "A complete transaction history for every item",
      "Organize equipment by location",
    ],
  },
  {
    icon: BarChart3,
    title: "Analytics",
    items: [
      "Operational ticket metrics at a glance",
      "Breakdowns by status, priority, and category",
      "Low-stock and warranty visibility",
      "Monthly resolution trends",
    ],
  },
  {
    icon: Settings,
    title: "Company Administration",
    items: [
      "Manage users, departments, and locations",
      "Configure categories and priorities",
      "Organize inventory categories",
      "Company profile and branding settings",
    ],
  },
];

const WORKFLOW_STEPS = [
  {
    icon: ClipboardList,
    title: "Report",
    description: "An employee reports an IT issue in seconds.",
  },
  {
    icon: UserCog,
    title: "Manage",
    description: "A technician receives and works the ticket.",
  },
  {
    icon: PackageCheck,
    title: "Equip",
    description: "Inventory can be reserved or used for the ticket, when needed.",
  },
  {
    icon: CheckCircle2,
    title: "Resolve",
    description: "The resolution and full history are recorded automatically.",
  },
  {
    icon: BarChart3,
    title: "Understand",
    description: "Administrators see operational analytics and inventory insights.",
  },
];

const ROLES = [
  {
    icon: Users2,
    title: "Employee",
    items: ["Report issues", "Follow their own tickets", "Communicate through the ticket workflow"],
  },
  {
    icon: Wrench,
    title: "Technician",
    items: ["Work assigned tickets", "Update progress and status", "Access inventory needed for support work"],
  },
  {
    icon: Building2,
    title: "Company Administrator",
    items: ["Manage company resources and users", "Oversee tickets and inventory", "View company-wide analytics"],
  },
];

const TRUST_POINTS = [
  {
    icon: ShieldCheck,
    title: "Role-based access",
    description: "Employees, technicians, and administrators each see only what their role allows.",
  },
  {
    icon: Lock,
    title: "Per-company data separation",
    description: "Every company's tickets, inventory, and users are kept separate from every other company.",
  },
  {
    icon: KeyRound,
    title: "Authenticated sessions",
    description: "Sign-in is protected by an authenticated session with automatic token refresh.",
  },
  {
    icon: History,
    title: "Full ticket history",
    description: "Status changes, comments, and assignments are recorded on every ticket.",
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
  const { user, status } = useAuth();

  if (status === "authenticated") {
    return <Navigate to={user?.role === "System Administrator" ? "/platform" : "/dashboard"} replace />;
  }

  return (
    <div className={styles.page}>
      <PublicNavbar />

      <main>
        <section className={styles.hero}>
          <Mascot size={96} className={styles.heroMascot} />
          <h1 className={styles.heroTitle}>IT support and inventory, finally working together.</h1>
          <p className={styles.heroSubtitle}>
            ITOnIT is a multi-tenant help desk that connects IT ticket management with the
            inventory it depends on - so your team can report issues, resolve them, and track
            the equipment involved, all in one place.
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

        <section className={styles.overview} aria-labelledby="overview-heading">
          <h2 id="overview-heading" className={styles.sectionTitle}>
            Tickets and inventory, connected
          </h2>
          <p className={styles.overviewText}>
            Most help desks stop at the ticket. ITOnIT goes further: when an issue needs a piece
            of equipment - a replacement laptop, a spare monitor - technicians can reserve or use
            inventory directly on the ticket. The full story, from report to resolution, is
            recorded in one place.
          </p>
        </section>

        <section id="features" className={styles.features} aria-labelledby="features-heading">
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

        <section id="how-it-works" className={styles.workflow} aria-labelledby="workflow-heading">
          <h2 id="workflow-heading" className={styles.sectionTitle}>
            How It Works
          </h2>
          <ol className={styles.workflowSteps}>
            {WORKFLOW_STEPS.map(({ icon: Icon, title, description }, index) => (
              <li key={title} className={styles.workflowStep}>
                <span className={styles.stepNumber} aria-hidden="true">
                  {index + 1}
                </span>
                <span className={styles.workflowIcon} aria-hidden="true">
                  <Icon size={20} strokeWidth={2} />
                </span>
                <h3 className={styles.workflowTitle}>{title}</h3>
                <p className={styles.workflowDescription}>{description}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="roles" className={styles.roles} aria-labelledby="roles-heading">
          <h2 id="roles-heading" className={styles.sectionTitle}>
            Built for every role
          </h2>
          <div className={styles.roleGrid}>
            {ROLES.map(({ icon: Icon, title, items }) => (
              <div key={title} className={styles.roleCard}>
                <span className={styles.roleIcon} aria-hidden="true">
                  <Icon size={22} strokeWidth={2} />
                </span>
                <h3 className={styles.roleTitle}>{title}</h3>
                <ul className={styles.roleList}>
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.trust} aria-labelledby="trust-heading">
          <h2 id="trust-heading" className={styles.sectionTitle}>
            Organized and secure by design
          </h2>
          <div className={styles.trustGrid}>
            {TRUST_POINTS.map(({ icon: Icon, title, description }) => (
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

        <section className={styles.finalCta} aria-labelledby="final-cta-heading">
          <h2 id="final-cta-heading" className={styles.finalCtaTitle}>
            Ready to get started?
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
      </main>

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
              <a href="#features">Features</a>
              <a href="#how-it-works">How It Works</a>
              <a href="#roles">Roles</a>
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
    </div>
  );
}
