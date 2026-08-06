import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { Mascot } from "../components/common/Mascot";
import { useAuth } from "../auth/useAuth";
import styles from "./LoginPage.module.css";

const FEATURES = [
  "Submit and track support tickets",
  "Role-based access for your whole team",
  "A full history on every request",
];

export function RegisterPage() {
  const { register, status, error } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await register({
        username: username.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        password,
      });
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
            <h2 className={styles.title}>Create your account</h2>
            <p className={styles.subtitle}>
              New accounts are created as Employees, able to submit and track their own tickets.
            </p>
          </div>

          <label className="field">
            <span className="fieldLabel">
              Username<span className="requiredMark">*</span>
            </span>
            <input
              type="text"
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </label>

          <div className={styles.nameRow}>
            <label className="field">
              <span className="fieldLabel">
                First Name<span className="requiredMark">*</span>
              </span>
              <input
                type="text"
                className="input"
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                autoComplete="given-name"
                required
              />
            </label>
            <label className="field">
              <span className="fieldLabel">
                Last Name<span className="requiredMark">*</span>
              </span>
              <input
                type="text"
                className="input"
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                autoComplete="family-name"
                required
              />
            </label>
          </div>

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
              required
            />
          </label>

          <label className="field">
            <span className="fieldLabel">
              Password<span className="requiredMark">*</span>
            </span>
            <input
              type="password"
              className="input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>

          {error && <ErrorMessage message={error} />}

          <button type="submit" className={`btn btn-primary ${styles.submitButton}`} disabled={submitting}>
            {submitting ? "Creating account..." : "Create account"}
          </button>

          <p className={styles.switchRow}>
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
