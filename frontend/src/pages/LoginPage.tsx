import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { Mascot } from "../components/common/Mascot";
import { useAuth } from "../auth/useAuth";
import styles from "./LoginPage.module.css";

interface LocationState {
  from?: { pathname: string };
}

const FEATURES = [
  "Submit and track support tickets",
  "Role-based access for your whole team",
  "A full history on every request",
];

export function LoginPage() {
  const { login, status, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Already logged in (e.g. navigated here directly) - go straight to
  // wherever they were headed, or the dashboard by default.
  if (status === "authenticated") {
    const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? "/dashboard";
    return <Navigate to={redirectTo} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/dashboard", { replace: true });
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
            <span>ITOnIT</span>
          </div>
          <h1 className={styles.brandHeadline}>Fast, modern IT support for your organization.</h1>
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
            <h2 className={styles.title}>Welcome back</h2>
            <p className={styles.subtitle}>Sign in to your ITOnIT account</p>
          </div>

          <div className="field">
            <label className="fieldLabel" htmlFor="username">
              Username
            </label>
            <input
              id="username"
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
            <label className="fieldLabel" htmlFor="password">
              Password
            </label>
            <input
              id="password"
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

          <button type="submit" className={`btn btn-primary ${styles.submitButton}`} disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </button>

          <p className={styles.switchRow}>
            Don&rsquo;t have an account? <Link to="/register">Create one</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
