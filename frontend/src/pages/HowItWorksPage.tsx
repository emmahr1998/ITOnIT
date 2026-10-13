import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Boxes,
  ClipboardList,
  Settings2,
  UserCog,
} from "lucide-react";
import { PublicPageShell } from "../components/public/PublicPageShell";
import landingStyles from "./LandingPage.module.css";
import styles from "./HowItWorksPage.module.css";

const STEPS = [
  {
    icon: ClipboardList,
    title: "1. Register your company",
    description:
      "Set up your company's workspace in minutes. ITOnIT automatically generates a unique company code - there's nothing to choose or configure.",
  },
  {
    icon: Settings2,
    title: "2. Set up your workspace",
    description:
      "As Company Administrator, add your team's users, departments, locations, categories, and priorities so tickets reflect how your organization actually works.",
  },
  {
    icon: ClipboardList,
    title: "3. Employees report IT issues",
    description:
      "An employee reports a problem with a title, description, category, priority, and location - everything the support team needs to get started.",
  },
  {
    icon: UserCog,
    title: "4. Technicians manage and resolve tickets",
    description:
      "A technician picks up an assigned ticket, updates its status as work progresses, and adds comments - all recorded automatically in the ticket's history.",
  },
  {
    icon: Boxes,
    title: "5. Track equipment and inventory",
    description:
      "When a ticket needs hardware - a replacement laptop, a spare monitor - the technician can reserve or consume inventory directly on that ticket, with every transaction recorded.",
  },
  {
    icon: BarChart3,
    title: "6. Keep everyone informed",
    description:
      "Status, comments, and history stay visible to everyone involved in a ticket, while administrators see dashboards and analytics across the whole company.",
  },
];

/**
 * Dedicated /how-it-works page - a deeper, narrative version of the
 * landing page's own #how-it-works section (left in place there). Every
 * step describes real, existing ITOnIT behavior.
 */
export function HowItWorksPage() {
  return (
    <PublicPageShell>
      <section className={landingStyles.hero}>
        <h1 className={landingStyles.heroTitle}>From a reported issue to a resolved ticket.</h1>
        <p className={landingStyles.heroSubtitle}>
          Here&rsquo;s the real ITOnIT workflow, from registering your company to tracking the
          equipment behind every ticket.
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

      <section className={landingStyles.workflow} aria-labelledby="how-it-works-heading">
        <h2 id="how-it-works-heading" className={landingStyles.sectionTitle}>
          How It Works
        </h2>
        <ol className={styles.steps}>
          {STEPS.map(({ icon: Icon, title, description }) => (
            <li key={title} className={landingStyles.workflowStep}>
              <span className={landingStyles.workflowIcon} aria-hidden="true">
                <Icon size={20} strokeWidth={2} />
              </span>
              <h3 className={landingStyles.workflowTitle}>{title}</h3>
              <p className={landingStyles.workflowDescription}>{description}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className={landingStyles.finalCta} aria-labelledby="how-it-works-cta-heading">
        <h2 id="how-it-works-cta-heading" className={landingStyles.finalCtaTitle}>
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
