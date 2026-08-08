import { useEffect, useRef, useState, type FormEvent } from "react";
import { Building2, ImagePlus } from "lucide-react";
import {
  fetchCompanySettings,
  updateCompanySettings,
  uploadCompanyLogo,
} from "../../api/companies";
import { getApiErrorMessage, resolveAssetUrl } from "../../api/client";
import { Skeleton } from "../../components/common/Skeleton";
import { ErrorMessage } from "../../components/common/ErrorMessage";
import { SuccessMessage } from "../../components/common/SuccessMessage";
import type { CompanySettings } from "../../types/company";
import styles from "./CompanySettingsPage.module.css";

// Mirrors the backend's validate_company_code_format
// (backend/app/schemas/validators.py) - kept in sync deliberately, so an
// obviously-invalid code is caught here instead of round-tripping to the
// server first.
const COMPANY_CODE_PATTERN = /^[A-Za-z0-9_-]{3,20}$/;

export function CompanySettingsPage() {
  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [companyCode, setCompanyCode] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [companyCodeError, setCompanyCodeError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function applySettings(next: CompanySettings) {
    setSettings(next);
    setName(next.name);
    setCompanyCode(next.company_code);
    setContactEmail(next.contact_email ?? "");
  }

  useEffect(() => {
    fetchCompanySettings()
      .then(applySettings)
      .catch((err) => setLoadError(getApiErrorMessage(err, "Could not load company settings.")))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCompanyCodeError(null);
    setSaveError(null);

    const trimmedCode = companyCode.trim();
    if (!COMPANY_CODE_PATTERN.test(trimmedCode)) {
      setCompanyCodeError(
        "Company code must be 3-20 characters: letters, numbers, hyphens, or underscores only.",
      );
      return;
    }

    setSaving(true);
    try {
      const updated = await updateCompanySettings({
        name: name.trim(),
        company_code: trimmedCode,
        contact_email: contactEmail.trim(),
      });
      applySettings(updated);
      setSuccessMessage("Company settings saved.");
    } catch (err) {
      setSaveError(getApiErrorMessage(err, "Could not save company settings."));
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoSelected(file: File) {
    setLogoError(null);
    setUploadingLogo(true);
    try {
      const updated = await uploadCompanyLogo(file);
      applySettings(updated);
      setSuccessMessage("Company logo updated.");
    } catch (err) {
      setLogoError(getApiErrorMessage(err, "Could not upload this logo."));
    } finally {
      setUploadingLogo(false);
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <h1 className={styles.heading}>Company Settings</h1>
        <Skeleton rows={6} height={44} />
      </div>
    );
  }

  if (loadError || !settings) {
    return (
      <div className={styles.page}>
        <h1 className={styles.heading}>Company Settings</h1>
        <ErrorMessage message={loadError ?? "Could not load company settings."} />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div>
        <h1 className={styles.heading}>Company Settings</h1>
        <p className={styles.subtitle}>
          Manage your company&rsquo;s profile, branding, and contact information.
        </p>
      </div>

      {successMessage && (
        <SuccessMessage message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <section className={`sectionCard ${styles.section}`}>
        <h2 className={styles.sectionTitle}>Company Logo</h2>
        <div className={styles.logoRow}>
          <div className={styles.logoPreview}>
            {settings.logo_url ? (
              <img
                src={resolveAssetUrl(settings.logo_url)}
                alt="Company logo"
                className={styles.logoImage}
              />
            ) : (
              <Building2 size={32} strokeWidth={1.5} className={styles.logoPlaceholder} />
            )}
          </div>
          <div className={styles.logoActions}>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className={styles.hiddenFileInput}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  handleLogoSelected(file);
                }
                event.target.value = "";
              }}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingLogo}
            >
              <ImagePlus size={16} />
              {uploadingLogo ? "Uploading..." : settings.logo_url ? "Change Logo" : "Upload Logo"}
            </button>
            <p className={styles.hint}>PNG, JPEG, or WebP. Up to 2 MB.</p>
          </div>
        </div>
        {logoError && <ErrorMessage message={logoError} />}
      </section>

      <form onSubmit={handleSave} className={`sectionCard ${styles.section}`}>
        <div className={styles.subsection}>
          <h2 className={styles.sectionTitle}>Company Profile</h2>
          <label className="field">
            <span className="fieldLabel">
              Company Name<span className="requiredMark">*</span>
            </span>
            <input
              type="text"
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
        </div>

        <div className={styles.subsection}>
          <h2 className={styles.sectionTitle}>Company Code</h2>
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
              The code your team types in to sign in. Changing it immediately affects sign-in for
              everyone at your company.
            </span>
            {companyCodeError && <ErrorMessage message={companyCodeError} />}
          </label>
        </div>

        <div className={styles.subsection}>
          <h2 className={styles.sectionTitle}>Contact Information</h2>
          <label className="field">
            <span className="fieldLabel">Contact Email</span>
            <input
              type="email"
              className="input"
              value={contactEmail}
              onChange={(event) => setContactEmail(event.target.value)}
              placeholder="support@yourcompany.com"
            />
          </label>
        </div>

        {saveError && <ErrorMessage message={saveError} />}

        <div className={styles.actions}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>

      <section className={`sectionCard ${styles.section}`}>
        <h2 className={styles.sectionTitle}>Preferences</h2>
        <p className={styles.hint}>
          Stored per-company for future use - not yet customizable.
        </p>
        <dl className={styles.preferencesGrid}>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Theme</dt>
            <dd className={styles.preferenceValue}>{settings.theme}</dd>
          </div>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Timezone</dt>
            <dd className={styles.preferenceValue}>{settings.timezone}</dd>
          </div>
          <div className={styles.preferenceItem}>
            <dt className={styles.preferenceLabel}>Language</dt>
            <dd className={styles.preferenceValue}>{settings.language}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
