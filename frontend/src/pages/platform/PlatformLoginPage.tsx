import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { Mascot } from "../../components/common/Mascot";
import { useAuth } from "../../auth/useAuth";
import styles from "../LoginPage.module.css";

const FEATURES = [
  "Provision new tenant companies",
  "Activate or suspend a company's access instantly",
  "See platform-wide usage at a glance",
];

/**
 * The System Administrator's own sign-in screen - deliberately separate
 * from LoginPage (reuses its visual design/CSS module directly, but skips
 * the company-code resolution step entirely: there is no company to
 * resolve for a platform-level account). See AuthProvider.loginPlatform for
 * why this needs no separate token/session infrastructure at all.
 */
export function PlatformLoginPage() {
  const { user, status, loginPlatform, error } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated" && user?.role === "System Administrator") {
    return <Navigate to="/platform" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await loginPlatform(username, password);
      navigate("/platform", { replace: true });
    } catch {
      // Failure message is already surfaced via the auth context's `error`.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.brandPanel}>
        <div className={styles.brandContent}>
          <Mascot size={120} className={styles.mascot} />
          <div className={styles.brandMark}>
            <span>ITOnIT Platform</span>
          </div>
          <h1 className={styles.brandHeadline}>Platform administration console.</h1>
          <ul className={styles.featureList}>
            {FEATURES.map((feature) => (
              <li key={feature}>
                <CheckCircle2 size={18} strokeWidth={2} />
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className={styles.formPanel}>
        <form className={styles.card} onSubmit={handleSubmit}>
          <div className={styles.cardHeader}>
            <div className={styles.companyBadge}>
              <ShieldCheck size={20} strokeWidth={1.75} />
              <span>System Administrator</span>
            </div>
            <h2 className={styles.title}>Platform sign in</h2>
            <p className={styles.subtitle}>Sign in with your platform username or email</p>
          </div>

          <div className="field">
            <label className="fieldLabel" htmlFor="platformUsername">
              Username
            </label>
            <input
              id="platformUsername"
              name="username"
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </div>

          <div className="field">
            <label className="fieldLabel" htmlFor="platformPassword">
              Password
            </label>
            <input
              id="platformPassword"
              name="password"
              type="password"
              className="input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && <ErrorMessage message={error} />}

          <button
            type="submit"
            className={`btn btn-primary ${styles.submitButton}`}
            disabled={submitting}
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
