import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { createPlatformCompany } from "../../api/platform";
import { getApiErrorMessage } from "../../api/client";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import styles from "../admin/CompanySettingsPage.module.css";
import registerStyles from "../RegisterPage.module.css";
import loginStyles from "../LoginPage.module.css";

// Mirrors the backend's validate_company_code_format
// (backend/app/schemas/validators.py) - same pattern RegisterPage/
// CompanySettingsPage already use, kept in sync deliberately.
const COMPANY_CODE_PATTERN = /^[A-Za-z0-9_-]{3,20}$/;

/**
 * POST /platform/companies. Reuses RegisterPage's exact field set and
 * validation, but is deliberately NOT wired through AuthContext -
 * createPlatformCompany() is a plain data call (the backend returns no
 * tokens at all for this route, see PlatformService.create_company's
 * docstring), so the System Administrator's own session is never touched
 * and never replaced, unlike self-service company registration.
 */
export function PlatformCreateCompanyPage() {
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
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCompanyCodeError(null);
    setConfirmPasswordError(null);
    setSubmitError(null);

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
      const created = await createPlatformCompany({
        company_name: companyName.trim(),
        company_code: trimmedCode,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        username: username.trim(),
        email: email.trim(),
        password,
      });
      navigate(`/platform/companies/${created.id}`, {
        replace: true,
        state: { justCreated: true },
      });
    } catch (err) {
      setSubmitError(getApiErrorMessage(err, "Could not create this company."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate("/platform/companies")}>
        <ArrowLeft size={14} /> Back to Companies
      </button>

      <div>
        <h1 className={styles.heading}>Create Company</h1>
        <p className={styles.subtitle}>
          Provision a new tenant company and its first Company Administrator.
        </p>
      </div>

      <form className={`sectionCard ${registerStyles.card}`} onSubmit={handleSubmit}>
        <div className={registerStyles.section}>
          <h3 className={registerStyles.sectionTitle}>Company Information</h3>

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
            <span className={registerStyles.hint}>
              A short, unique code this company's team will type in to sign in. Letters, numbers,
              hyphens, and underscores only.
            </span>
            {companyCodeError && <ErrorMessage message={companyCodeError} />}
          </label>
        </div>

        <div className={registerStyles.section}>
          <h3 className={registerStyles.sectionTitle}>First Company Administrator</h3>

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

        {submitError && <ErrorMessage message={submitError} />}

        <div className={styles.actions}>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Creating company..." : "Create Company"}
          </button>
        </div>
      </form>
    </div>
  );
}
