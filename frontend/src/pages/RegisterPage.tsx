import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { Mascot } from "../components/common/Mascot";
import { useAuth } from "../auth/useAuth";
import loginStyles from "./LoginPage.module.css";
import styles from "./RegisterPage.module.css";

const FEATURES = [
  "Submit and track support tickets",
  "Role-based access for your whole team",
  "A full history on every request",
];

// Mirrors the backend's validate_company_code_format
// (backend/app/schemas/validators.py) - kept in sync deliberately, so an
// obviously-invalid code is caught here instead of round-tripping to the
// server first.
const COMPANY_CODE_PATTERN = /^[A-Za-z0-9_-]{3,20}$/;

export function RegisterPage() {
  const { registerCompany, status, error } = useAuth();
  const navigate = useNavigate();

  const [companyName, setCompanyName] = useState("");
  const [companyCode, setCompanyCode] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [companyCodeError, setCompanyCodeError] = useState<string | null>(null);
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCompanyCodeError(null);
    setConfirmPasswordError(null);

    const trimmedCode = companyCode.trim();
    if (!COMPANY_CODE_PATTERN.test(trimmedCode)) {
      setCompanyCodeError(
        "Company code must be 3-20 characters: letters, numbers, hyphens, or underscores only.",
      );
      return;
    }
    if (password !== confirmPassword) {
      setConfirmPasswordError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await registerCompany({
        company_name: companyName.trim(),
        company_code: trimmedCode,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        username: username.trim(),
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
    <div className={loginStyles.page}>
      <div className={loginStyles.brandPanel}>
        <div className={loginStyles.brandContent}>
          <Mascot size={120} className={loginStyles.mascot} />
          <div className={loginStyles.brandMark}>
            <span>ITOnIT</span>
          </div>
          <h1 className={loginStyles.brandHeadline}>
            Fast, modern IT support for your organization.
          </h1>
          <ul className={loginStyles.featureList}>
            {FEATURES.map((feature) => (
              <li key={feature}>
                <CheckCircle2 size={18} strokeWidth={2} />
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className={loginStyles.formPanel}>
        <form className={`${loginStyles.card} ${styles.card}`} onSubmit={handleSubmit}>
          <div className={loginStyles.cardHeader}>
            <h2 className={loginStyles.title}>Register Your Company</h2>
            <p className={loginStyles.subtitle}>
              Set up your company&rsquo;s workspace and sign in as its first Company
              Administrator.
            </p>
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Company Information</h3>

            <label className="field">
              <span className="fieldLabel">
                Company Name<span className="requiredMark">*</span>
              </span>
              <input
                type="text"
                className="input"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                autoComplete="organization"
                autoFocus
                required
              />
            </label>

            <label className="field">
              <span className="fieldLabel">
                Company Code<span className="requiredMark">*</span>
              </span>
              <input
                type="text"
                className="input"
                value={companyCode}
                onChange={(event) => setCompanyCode(event.target.value)}
                minLength={3}
                maxLength={20}
                required
              />
              <span className={styles.hint}>
                A short, unique code your team will type in to sign in (e.g.{" "}
                <strong>ACME01</strong>). Letters, numbers, hyphens, and underscores only.
              </span>
              {companyCodeError && <ErrorMessage message={companyCodeError} />}
            </label>
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Company Administrator</h3>

            <div className={loginStyles.nameRow}>
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
                Username<span className="requiredMark">*</span>
              </span>
              <input
                type="text"
                className="input"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
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
                required
              />
            </label>

            <div className={loginStyles.nameRow}>
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
              <label className="field">
                <span className="fieldLabel">
                  Confirm Password<span className="requiredMark">*</span>
                </span>
                <input
                  type="password"
                  className="input"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
            </div>
            {confirmPasswordError && <ErrorMessage message={confirmPasswordError} />}
          </div>

          {error && <ErrorMessage message={error} />}

          <button
            type="submit"
            className={`btn btn-primary ${loginStyles.submitButton}`}
            disabled={submitting}
          >
            {submitting ? "Creating your company..." : "Register Company"}
          </button>

          <p className={loginStyles.switchRow}>
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
