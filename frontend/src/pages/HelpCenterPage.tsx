import { useState, type FormEvent } from "react";
import { ChevronDown, Mail, Send } from "lucide-react";
import { submitContactMessage } from "../api/support";
import { getApiErrorMessage } from "../api/client";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { PublicPageShell } from "../components/public/PublicPageShell";
import landingStyles from "./LandingPage.module.css";
import styles from "./HelpCenterPage.module.css";

const FAQS = [
  {
    question: "What is a company code?",
    answer:
      "A company code (for example, IT-7K4M2P) identifies which company's workspace you're signing in to. It's required, along with your username and password, every time you sign in.",
  },
  {
    question: "Where do I get my company code?",
    answer:
      "It's generated automatically the moment your company registers, and is shown right away on the registration success screen. It's also emailed to the Company Administrator who registered the account.",
  },
  {
    question: "I forgot my company code. What should I do?",
    answer:
      "Ask your company's Company Administrator - they received it both on-screen and by email when the company registered. If you are the Company Administrator and can't find it, use the contact form below and our support team will help.",
  },
  {
    question: "How do I sign in?",
    answer:
      "Go to the Sign In page and enter your company code, your username (or email), and your password.",
  },
  {
    question: "How do I report an IT issue?",
    answer:
      "Once signed in, use Create Ticket to report an issue. Include a title, description, category, priority, and location so the support team has everything they need.",
  },
  {
    question: "How can I track my ticket?",
    answer:
      "Open the ticket from your ticket list to see its current status, along with a full history of status changes, comments, and assignments.",
  },
  {
    question: "Who can manage users?",
    answer: "Company Administrators manage users for their company, including adding new users and assigning roles.",
  },
  {
    question: "What is the difference between an Employee and a Technician?",
    answer:
      "An Employee reports issues and follows their own tickets. A Technician works tickets assigned to them, updates their status, and can reserve or use inventory needed for the fix.",
  },
  {
    question: "How does inventory work?",
    answer:
      "ITOnIT tracks both individual assets (like a specific laptop) and bulk stock. When a ticket needs equipment, a Technician or Company Administrator can reserve or consume inventory directly on that ticket, and every transaction is recorded.",
  },
  {
    question: "Who should I contact if I still need help?",
    answer: "Use the contact form below - our support team will get back to you as soon as possible.",
  },
];

/**
 * Dedicated /help page: FAQ accordion (answers describe real, existing
 * ITOnIT behavior only) plus a contact form that posts to
 * POST /support/contact. That endpoint reuses the same SMTP
 * infrastructure as the company-registration welcome email, sending to
 * an environment-configured SUPPORT_EMAIL - see
 * backend/app/services/support_service.py.
 */
export function HelpCenterPage() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  // Honeypot - left blank by every real visitor (see the hidden field
  // below); a non-blank value here means the submission was filled in by
  // a bot, not a human - the backend quietly drops it (see
  // SupportContactRequest's own docstring).
  const [website, setWebsite] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  function toggleFaq(index: number) {
    setOpenIndex((current) => (current === index ? null : index));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      await submitContactMessage({
        name: name.trim(),
        email: email.trim(),
        subject: subject.trim(),
        message: message.trim(),
        website,
      });
      setSent(true);
    } catch (err) {
      setSubmitError(
        getApiErrorMessage(err, "We couldn't send your message right now. Please try again later."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PublicPageShell>
      <section className={landingStyles.hero}>
        <h1 className={landingStyles.heroTitle}>How can we help?</h1>
        <p className={landingStyles.heroSubtitle}>
          Find answers to common ITOnIT questions below, or send our team a message and
          we&rsquo;ll get back to you.
        </p>
      </section>

      <section className={styles.faq} aria-labelledby="faq-heading">
        <h2 id="faq-heading" className={landingStyles.sectionTitle}>
          Frequently asked questions
        </h2>
        <div className={styles.faqList}>
          {FAQS.map((faq, index) => {
            const open = openIndex === index;
            return (
              <div key={faq.question} className={styles.faqItem}>
                <button
                  type="button"
                  className={styles.faqQuestion}
                  aria-expanded={open}
                  onClick={() => toggleFaq(index)}
                >
                  {faq.question}
                  <ChevronDown
                    size={18}
                    strokeWidth={2}
                    className={`${styles.faqIcon} ${open ? styles.faqIconOpen : ""}`}
                    aria-hidden="true"
                  />
                </button>
                {open && <p className={styles.faqAnswer}>{faq.answer}</p>}
              </div>
            );
          })}
        </div>
      </section>

      <section className={styles.contact} aria-labelledby="contact-heading">
        <h2 id="contact-heading" className={landingStyles.sectionTitle}>
          Still need help?
        </h2>
        <p className={styles.contactIntro}>
          Can&rsquo;t find the answer you&rsquo;re looking for? Send us a message and our
          support team will get back to you as soon as possible.
        </p>

        <div className={styles.contactCard}>
          {sent ? (
            <div className={styles.successPanel}>
              <Mail size={32} strokeWidth={2} className={styles.successIcon} />
              <h3 className={styles.successTitle}>Message sent successfully!</h3>
              <p className={styles.successText}>
                Thanks for contacting ITOnIT. We&rsquo;ll get back to you as soon as possible.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className={styles.nameRow}>
                <label className="field">
                  <span className="fieldLabel">
                    Name<span className="requiredMark">*</span>
                  </span>
                  <input
                    type="text"
                    className="input"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    autoComplete="name"
                    maxLength={100}
                    required
                  />
                </label>
                <label className="field">
                  <span className="fieldLabel">
                    Email<span className="requiredMark">*</span>
                  </span>
                  <input
                    type="email"
                    className="input"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    autoComplete="email"
                    maxLength={255}
                    required
                  />
                </label>
              </div>

              <label className="field">
                <span className="fieldLabel">
                  Subject<span className="requiredMark">*</span>
                </span>
                <input
                  type="text"
                  className="input"
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  maxLength={150}
                  required
                />
              </label>

              <label className="field">
                <span className="fieldLabel">
                  Message<span className="requiredMark">*</span>
                </span>
                <textarea
                  className="textarea"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  rows={5}
                  maxLength={5000}
                  required
                />
              </label>

              {/* Honeypot field - see the `website` state's own comment above. */}
              <label className={styles.honeypot} aria-hidden="true">
                Website
                <input
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  value={website}
                  onChange={(event) => setWebsite(event.target.value)}
                />
              </label>

              {submitError && <ErrorMessage message={submitError} />}

              <button
                type="submit"
                className={`btn btn-primary ${styles.submitButton}`}
                disabled={submitting}
              >
                <Send size={16} strokeWidth={2} />
                {submitting ? "Sending..." : "Send Message"}
              </button>
            </form>
          )}
        </div>
      </section>
    </PublicPageShell>
  );
}
