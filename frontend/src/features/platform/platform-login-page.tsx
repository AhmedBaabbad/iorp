"use client";

import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PasswordInput } from "@/components/PasswordInput";
import { ApiClientError } from "@/lib/api-client";
import { usePlatformAuth } from "./platform-auth-context";

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    background: "var(--page-bg)",
    color: "var(--text)",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: "24px",
  },
  panel: {
    width: "100%",
    maxWidth: "420px",
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(0, 0, 0, 0.4)",
    padding: "32px",
  },
  header: { marginBottom: "28px" },
  eyebrow: {
    margin: "0 0 8px",
    color: "var(--text-muted)",
    fontSize: "13px",
    fontWeight: 700,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },
  title: { margin: 0, fontSize: "26px", lineHeight: 1.2 },
  form: { display: "grid", gap: "18px" },
  field: { display: "grid", gap: "8px" },
  label: { fontSize: "14px", fontWeight: 600, color: "var(--text)" },
  input: {
    width: "100%",
    boxSizing: "border-box",
    border: "1px solid var(--border)",
    background: "var(--page-bg)",
    color: "var(--text)",
    borderRadius: "6px",
    font: "inherit",
    padding: "11px 12px",
  },
  button: {
    border: 0,
    borderRadius: "6px",
    background: "var(--accent)",
    color: "var(--on-accent)",
    cursor: "pointer",
    font: "inherit",
    fontWeight: 700,
    minHeight: "42px",
    padding: "10px 14px",
    width: "100%",
  },
  error: {
    background: "var(--danger-soft)",
    border: "1px solid color-mix(in srgb, var(--danger) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--danger)",
    fontSize: "14px",
    padding: "12px 14px",
  },
};

export function PlatformLoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("platform");
  const resetT = useTranslations("passwordReset.forgot");
  const { login, isAuthenticated, isLoading } = usePlatformAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [retryAfter, setRetryAfter] = useState(0);
  const sessionMessage = searchParams.get("session");

  useEffect(() => {
    if (retryAfter <= 0) return;
    const timer = window.setInterval(() => setRetryAfter((value) => {
      if (value <= 1) {
        setError(null);
        return 0;
      }
      return value - 1;
    }), 1000);
    return () => window.clearInterval(timer);
  }, [retryAfter]);

  const retryTime = `${Math.floor(retryAfter / 60)}:${String(retryAfter % 60).padStart(2, "0")}`;

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/platform/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email, password, mfa_code: mfaCode });
      router.replace("/platform/dashboard");
    } catch (caughtError) {
      const data = caughtError instanceof ApiClientError && caughtError.details && typeof caughtError.details === "object"
        ? caughtError.details as { code?: string; retry_after_seconds?: number } : null;
      if (data?.code === "MFA_REQUIRED" || data?.code === "VERIFICATION_FAILED" || data?.code === "VERIFICATION_LOCKED") {
        setError(t("security.failed"));
        return;
      }
      if (data?.code === "ACCOUNT_TEMPORARILY_LOCKED" || data?.code === "RATE_LIMIT_EXCEEDED") {
        setRetryAfter(data.retry_after_seconds ?? 60);
        setError(t(data.code === "ACCOUNT_TEMPORARILY_LOCKED" ? "login.accountTemporarilyLocked" : "login.rateLimitExceeded"));
        return;
      }
      if (data?.code === "ACCOUNT_LOCKED") {
        setError(t("login.accountLocked"));
        return;
      }
      const message =
        caughtError instanceof ApiClientError && caughtError.status === 401
          ? t("login.errorInvalidCredentials")
          : t("login.errorGeneric");
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={styles.page}>
      <section style={styles.panel} aria-labelledby="platform-login-title">
        <LanguageSwitcher label={t("login.languageSwitcherLabel")} />

        <div style={styles.header}>
          <p style={styles.eyebrow}>{t("login.eyebrow")}</p>
          <h1 id="platform-login-title" style={styles.title}>
            {t("login.title")}
          </h1>
        </div>

        <form style={styles.form} onSubmit={handleSubmit}>
          <label style={styles.field}>
            <span style={styles.label}>{t("login.emailLabel")}</span>
            <input
              style={styles.input}
              type="email"
              autoComplete="email"
              placeholder={t("login.emailPlaceholder")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>
          <Link href="/platform/forgot-password" style={{ color: "var(--accent)", fontWeight: 700, textDecoration: "none" }}>{resetT("forgotLink")}</Link>

          <label style={styles.field}>
            <span style={styles.label}>{t("login.passwordLabel")}</span>
            <PasswordInput
              inputStyle={styles.input}
              autoComplete="current-password"
              placeholder={t("login.passwordPlaceholder")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          <label style={styles.field}><span>{t("security.code")}</span><input style={styles.input} dir="ltr" autoComplete="one-time-code" value={mfaCode} onChange={e => setMfaCode(e.target.value)} /></label>
          {!error && sessionMessage === "expired" ? (
            <div style={styles.error} role="status">{t("login.sessionExpired")}</div>
          ) : null}
          {!error && sessionMessage === "password_changed" ? (
            <div style={styles.error} role="status">{t("login.passwordChanged")}</div>
          ) : null}
          {error ? (
            <div style={styles.error} role="alert">
              {error}{retryAfter > 0 ? ` ${t("login.tryAgainIn", { time: retryTime })}` : ""}
            </div>
          ) : null}

          <button style={styles.button} type="submit" disabled={isSubmitting || retryAfter > 0}>
            {isSubmitting ? t("login.submitting") : t("login.submitButton")}
          </button>
        </form>
      </section>
    </main>
  );
}
