import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Building2, CheckCircle2 } from "lucide-react";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { Mascot } from "../components/common/Mascot";
import { useAuth } from "../auth/useAuth";
import { resolveCompanyRequest } from "../api/auth";
import { getApiErrorMessage } from "../api/client";
import { companyStore } from "../api/companyStore";
import styles from "./LoginPage.module.css";

interface LocationState {
  from?: { pathname: string };
}

const FEATURES = [
  "Submit and track support tickets",
  "Role-based access for your whole team",
  "A full history on every request",
];

type Step = "company" | "credentials";

export function LoginPage() {
  const { login, status, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // A remembered company (see companyStore - session-scoped on web,
  // launch-persistent on desktop) skips straight to step 2, pre-filled.
  const remembered = companyStore.get();

  const [step, setStep] = useState<Step>(remembered ? "credentials" : "company");
  const [companyCode, setCompanyCode] = useState(remembered?.companyCode ?? "");
  const [companyName, setCompanyName] = useState(remembered?.companyName ?? "");
  const [companyLogo, setCompanyLogo] = useState<string | null>(remembered?.companyLogo ?? null);
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Already logged in (e.g. navigated here directly) - go straight to
  // wherever they were headed, or the dashboard by default.
  if (status === "authenticated") {
    const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? "/dashboard";
    return <Navigate to={redirectTo} replace />;
  }

  async function handleResolveCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCompanyError(null);
    setResolving(true);
    try {
      const company = await resolveCompanyRequest({ company_code: companyCode });
      setCompanyName(company.company_name);
      setCompanyLogo(company.company_logo);
      companyStore.set({
        companyCode,
        companyName: company.company_name,
        companyLogo: company.company_logo,
      });
      setStep("credentials");
    } catch (err) {
      setCompanyError(
        getApiErrorMessage(err, "Could not find that company. Check the code and try again."),
      );
    } finally {
      setResolving(false);
    }
  }

  function handleChangeCompany() {
    companyStore.clear();
    setCompanyCode("");
    setCompanyName("");
    setCompanyLogo(null);
    setUsername("");
    setPassword("");
    setStep("company");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await login(companyCode, username, password);
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
        {step === "company" ? (
          <form className={styles.card} onSubmit={handleResolveCompany}>
            <div className={styles.cardHeader}>
              <h2 className={styles.title}>Sign in to ITOnIT</h2>
              <p className={styles.subtitle}>Enter your company code to get started</p>
            </div>

            <div className="field">
              <label className="fieldLabel" htmlFor="companyCode">
                Company code
              </label>
              <input
                id="companyCode"
                name="companyCode"
                className="input"
                value={companyCode}
                onChange={(event) => setCompanyCode(event.target.value)}
                autoComplete="organization"
                autoFocus
                required
              />
            </div>

            {companyError && <ErrorMessage message={companyError} />}

            <button
              type="submit"
              className={`btn btn-primary ${styles.submitButton}`}
              disabled={resolving}
            >
              {resolving ? "Checking..." : "Continue"}
            </button>

            <p className={styles.switchRow}>
              New to ITOnIT? <Link to="/register">Register your company</Link>
            </p>
          </form>
        ) : (
          <form className={styles.card} onSubmit={handleSubmit}>
            <div className={styles.cardHeader}>
              <div className={styles.companyBadge}>
                {companyLogo ? (
                  <img src={companyLogo} alt="" className={styles.companyLogo} />
                ) : (
                  <Building2 size={20} strokeWidth={1.75} />
                )}
                <span>{companyName || "Your company"}</span>
              </div>
              <h2 className={styles.title}>Welcome back</h2>
              <p className={styles.subtitle}>Sign in with your username or email</p>
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

            <button
              type="submit"
              className={`btn btn-primary ${styles.submitButton}`}
              disabled={submitting}
            >
              {submitting ? "Signing in..." : "Sign in"}
            </button>

            <p className={styles.switchRow}>
              <button
                type="button"
                className={styles.changeCompanyButton}
                onClick={handleChangeCompany}
              >
                Not your company? Change company
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
