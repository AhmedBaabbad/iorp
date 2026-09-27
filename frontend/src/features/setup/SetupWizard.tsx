"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { type CSSProperties, type FormEvent, useEffect, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PasswordInput } from "@/components/PasswordInput";
import { ApiClientError } from "@/lib/api-client";
import { TIMEZONES, timezoneLabel } from "@/lib/timezones";
import { sharedStyles } from "@/styles/shared-styles";
import { getBootstrapStatus, initializeSystem, type SetupPayload } from "./setup-api";

const ORG_CODE_PATTERN = /^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/;
const STEP_KEYS = ["platformOwner", "organization", "orgAdmin", "review"] as const;

const empty: SetupPayload = {
  bootstrap_token: "",
  platform_root: { full_name: "", email: "", password: "", password_confirmation: "" },
  organization: { name: "", code: "", industry_type: "", timezone: "Asia/Riyadh", default_locale: "ar" },
  organization_admin: { full_name: "", email: "", phone: "", password: "", password_confirmation: "" },
};

const styles: Record<string, CSSProperties> = {
  page: { minHeight: "100vh", padding: 24, background: "#f6f7f9" },
  card: { background: "#fff", border: "1px solid #d9dee7", borderRadius: 10, padding: 32, maxWidth: 640, margin: "40px auto" },
  stepper: { display: "flex", gap: 8, marginBottom: 24 },
  step: { flex: 1, borderRadius: 6, padding: "8px 4px", textAlign: "center", fontSize: 12, fontWeight: 700, background: "#eef1f4", color: "#7b8794" },
  stepActive: { background: "#1f2933", color: "#ffffff" },
  form: { display: "grid", gap: 16 },
  actions: { display: "flex", gap: 8 },
  logoPreview: { width: 64, height: 64, objectFit: "cover", borderRadius: 8, border: "1px solid #d9dee7", marginTop: 8 },
  reviewRow: { margin: "4px 0" },
};

function isValidTimezone(timezone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: timezone });
    return true;
  } catch {
    return false;
  }
}

export function SetupWizard() {
  const t = useTranslations("setup");
  const [data, setData] = useState(empty);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [initialized, setInitialized] = useState<boolean | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    getBootstrapStatus()
      .then((value) => setInitialized(value.initialized))
      .catch(() => setInitialized(false));
  }, []);

  const setSection = (
    section: "platform_root" | "organization" | "organization_admin",
    key: string,
    value: string,
  ) => setData((current) => ({ ...current, [section]: { ...current[section], [key]: value } }));

  function handleLogoSelect(file?: File) {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setError(t("errors.logoTooLarge"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      setSection("organization", "logo_base64", dataUrl);
      setLogoPreview(dataUrl);
    };
    reader.readAsDataURL(file);
  }

  function validateStep(currentStep: number): string {
    if (currentStep === 0) {
      if (!data.bootstrap_token.trim()) return t("errors.bootstrapTokenRequired");
      if (data.platform_root.password.length < 12) return t("errors.passwordTooShort", { min: 12 });
      if (data.platform_root.password !== data.platform_root.password_confirmation) {
        return t("errors.passwordMismatch");
      }
      if (data.platform_root.password.toLowerCase() === data.platform_root.email.toLowerCase()) {
        return t("errors.passwordEqualsEmail");
      }
    }
    if (currentStep === 1) {
      if (!ORG_CODE_PATTERN.test(data.organization.code)) return t("errors.invalidOrgCode");
      if (!isValidTimezone(data.organization.timezone)) return t("errors.invalidTimezone");
    }
    if (currentStep === 2) {
      if (data.organization_admin.password.length < 8) return t("errors.passwordTooShort", { min: 8 });
      if (data.organization_admin.password !== data.organization_admin.password_confirmation) {
        return t("errors.passwordMismatch");
      }
      if (data.organization_admin.password.toLowerCase() === data.organization_admin.email.toLowerCase()) {
        return t("errors.passwordEqualsEmail");
      }
      if (data.organization_admin.email.toLowerCase() === data.platform_root.email.toLowerCase()) {
        return t("errors.emailsMustDiffer");
      }
    }
    return "";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const validationError = validateStep(step);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError("");
    if (step < 3) {
      setStep(step + 1);
      return;
    }
    setSubmitting(true);
    try {
      await initializeSystem(data);
      setData(empty);
      setSuccess(true);
    } catch (caughtError) {
      if (caughtError instanceof ApiClientError && caughtError.status === 403) {
        setError(t("errors.invalidBootstrapToken"));
      } else if (caughtError instanceof ApiClientError && caughtError.status === 409) {
        setError(t("errors.alreadyInitializedDuringSubmit"));
      } else if (caughtError instanceof ApiClientError && caughtError.status === 422) {
        setError(caughtError.message || t("errors.setupFailed"));
      } else {
        setError(t("errors.setupFailed"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (initialized) {
    return (
      <main style={styles.page}>
        <section style={styles.card}>
          <h1>{t("alreadyInitialized.title")}</h1>
          <p>{t("alreadyInitialized.message")}</p>
          <Link href="/login">{t("alreadyInitialized.goToLogin")}</Link>
        </section>
      </main>
    );
  }

  if (success) {
    return (
      <main style={styles.page}>
        <section style={styles.card}>
          <h1>{t("success.title")}</h1>
          <p>{t("success.message")}</p>
          <Link href="/login">{t("success.goToLogin")}</Link>
        </section>
      </main>
    );
  }

  const field = (
    label: string,
    value: string,
    onChange: (value: string) => void,
    type = "text",
    hint?: string,
  ) => (
    <label style={sharedStyles.field}>
      <span style={sharedStyles.label}>{label}</span>
      {type === "password" ? (
        <PasswordInput inputStyle={sharedStyles.input} value={value} onChange={(e) => onChange(e.target.value)} required />
      ) : (
        <input style={sharedStyles.input} type={type} value={value} onChange={(e) => onChange(e.target.value)} required />
      )}
      {hint && <small style={{ color: "#7b8794" }}>{hint}</small>}
    </label>
  );

  return (
    <main style={styles.page}>
      <section style={styles.card}>
        <LanguageSwitcher label={t("languageSwitcher")} />
        <h1>{t("pageTitle")}</h1>
        <p>{t("subtitle")}</p>

        <div style={styles.stepper}>
          {STEP_KEYS.map((key, index) => (
            <div key={key} style={{ ...styles.step, ...(index === step ? styles.stepActive : {}) }}>
              {t(`steps.${key}`)}
            </div>
          ))}
        </div>

        <form onSubmit={submit} style={styles.form}>
          {step === 0 && (
            <>
              {field(t("fields.bootstrapToken"), data.bootstrap_token, (v) => setData({ ...data, bootstrap_token: v }), "password")}
              {field(t("fields.fullName"), data.platform_root.full_name, (v) => setSection("platform_root", "full_name", v))}
              {field(t("fields.email"), data.platform_root.email, (v) => setSection("platform_root", "email", v), "email")}
              {field(t("fields.password"), data.platform_root.password, (v) => setSection("platform_root", "password", v), "password")}
              {field(t("fields.confirmPassword"), data.platform_root.password_confirmation, (v) => setSection("platform_root", "password_confirmation", v), "password")}
            </>
          )}

          {step === 1 && (
            <>
              {field(t("fields.orgName"), data.organization.name, (v) => setSection("organization", "name", v))}
              {field(t("fields.orgCode"), data.organization.code, (v) => setSection("organization", "code", v), "text", t("fields.orgCodeHint"))}
              {field(t("fields.industryType"), data.organization.industry_type || "", (v) => setSection("organization", "industry_type", v))}
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.timezone")}</span>
                <select
                  style={sharedStyles.input}
                  value={data.organization.timezone}
                  onChange={(e) => setSection("organization", "timezone", e.target.value)}
                  required
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>
                      {timezoneLabel(tz)}
                    </option>
                  ))}
                </select>
              </label>
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.orgLogo")}</span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => handleLogoSelect(e.target.files?.[0])}
                />
                <small>{t("fields.acceptedFormats")}</small>
                {logoPreview && <img src={logoPreview} alt="" style={styles.logoPreview} />}
              </label>
            </>
          )}

          {step === 2 && (
            <>
              {field(t("fields.fullName"), data.organization_admin.full_name, (v) => setSection("organization_admin", "full_name", v))}
              {field(t("fields.email"), data.organization_admin.email, (v) => setSection("organization_admin", "email", v), "email")}
              {field(t("fields.phone"), data.organization_admin.phone || "", (v) => setSection("organization_admin", "phone", v), "tel")}
              {field(t("fields.password"), data.organization_admin.password, (v) => setSection("organization_admin", "password", v), "password")}
              {field(t("fields.confirmPassword"), data.organization_admin.password_confirmation, (v) => setSection("organization_admin", "password_confirmation", v), "password")}
            </>
          )}

          {step === 3 && (
            <>
              <h2>{t("steps.review")}</h2>
              {logoPreview && <img src={logoPreview} alt="" style={styles.logoPreview} />}
              <p style={styles.reviewRow}>
                <strong>{t("fields.fullName")}:</strong> {data.platform_root.full_name} — {data.platform_root.email}
              </p>
              <p style={styles.reviewRow}>
                <strong>{t("fields.orgName")}:</strong> {data.organization.name} — {data.organization.code}
              </p>
              <p style={styles.reviewRow}>
                <strong>{t("fields.industryType")}:</strong> {data.organization.industry_type || "—"}
              </p>
              <p style={styles.reviewRow}>
                <strong>{t("fields.timezone")}:</strong> {data.organization.timezone}
              </p>
              <p style={styles.reviewRow}>
                <strong>{t("fields.defaultLocale")}:</strong> {data.organization.default_locale}
              </p>
              <p style={styles.reviewRow}>
                <strong>{t("fields.fullName")}:</strong> {data.organization_admin.full_name} — {data.organization_admin.email}
              </p>
              {data.organization_admin.phone && (
                <p style={styles.reviewRow}>
                  <strong>{t("fields.phone")}:</strong> {data.organization_admin.phone}
                </p>
              )}
            </>
          )}

          {error && <div style={sharedStyles.error}>{error}</div>}

          <div style={styles.actions}>
            {step > 0 && (
              <button type="button" style={sharedStyles.secondaryButton} onClick={() => { setError(""); setStep(step - 1); }}>
                {t("buttons.back")}
              </button>
            )}
            <button type="submit" style={sharedStyles.button} disabled={submitting}>
              {submitting ? t("buttons.submitting") : step === 3 ? t("buttons.completeSetup") : t("buttons.next")}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
