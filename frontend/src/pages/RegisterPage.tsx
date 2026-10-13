import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Check, CheckCircle2, Copy } from "lucide-react";
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

export function RegisterPage() {
  const { registerCompany, status, error } = useAuth();
  const navigate = useNavigate();

  const [companyName, setCompanyName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Set once registration succeeds - replaces the form with a confirmation
  // panel showing the backend-generated company code, instead of
  // immediately navigating away before the admin has a chance to see it.
  const [generatedCode, setGeneratedCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (status === "authenticated" && !generatedCode) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConfirmPasswordError(null);

    if (password !== confirmPassword) {
      setConfirmPasswordError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const companyCode = await registerCompany({
        company_name: companyName.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        username: username.trim(),
        email: email.trim(),
        password,
      });
      setGeneratedCode(companyCode);
    } catch {
      // Failure message is already surfaced via the auth context's `error`.
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCopyCode() {
    if (!generatedCode) {
      return;
    }
    try {
      await navigator.clipboard.writeText(generatedCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be denied/unavailable - the code is still
      // shown on screen and selectable by hand, so this is a soft failure.
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
        {generatedCode ? (
          <div className={`${loginStyles.card} ${styles.card}`}>
            <div className={loginStyles.cardHeader}>
              <h2 className={loginStyles.title}>
                <CheckCircle2 size={22} strokeWidth={2} className={styles.successIcon} />
                Company created
              </h2>
              <p className={loginStyles.subtitle}>
                Your company code is <strong>{generatedCode}</strong>. Employees will use this
                code to sign in to your company, so make a note of it now.
              </p>
            </div>

            <div className={styles.codePanel}>
              <span className={styles.codeValue}>{generatedCode}</span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleCopyCode}
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>

            <button
              type="button"
              className={`btn btn-primary ${loginStyles.submitButton}`}
              onClick={() => navigate("/dashboard", { replace: true })}
            >
              Continue to Dashboard
            </button>
          </div>
        ) : (
        <form className={`${loginStyles.card} ${styles.card}`} onSubmit={handleSubmit}>
          <div className={loginStyles.cardHeader}>
            <h2 className={loginStyles.title}>Register Your Company</h2>
            <p className={loginStyles.subtitle}>
              Set up your company&rsquo;s workspace and sign in as its first Company
              Administrator. We&rsquo;ll generate a unique company code for you automatically.
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
        )}
      </div>
    </div>
  );
}
