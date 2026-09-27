"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PasswordInput } from "@/components/PasswordInput";
import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import { useAuth } from "./auth-context";
import { getBootstrapStatus } from "@/features/setup/setup-api";

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    background: "#f6f7f9",
    color: "#1f2933",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: "24px",
  },
  panel: {
    width: "100%",
    maxWidth: "420px",
    background: "#ffffff",
    border: "1px solid #d9dee7",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.08)",
    padding: "32px",
  },
  header: {
    marginBottom: "28px",
  },
  eyebrow: {
    margin: "0 0 8px",
    color: "#52606d",
    fontSize: "14px",
    fontWeight: 600,
  },
  title: {
    margin: 0,
    fontSize: "28px",
    lineHeight: 1.2,
  },
  form: {
    display: "grid",
    gap: "18px",
  },
};

export function LoginPage() {
  const router = useRouter();
  const t = useTranslations("auth");
  const resetT = useTranslations("passwordReset.forgot");
  const { login, isAuthenticated, isLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [retryAfter, setRetryAfter] = useState(0);
  const [remainingAttempts, setRemainingAttempts] = useState<number | null>(null);

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
    const account = new URLSearchParams(window.location.search).get("account");
    const session = new URLSearchParams(window.location.search).get("session");
    if (account === "locked") setError(t("login.accountLocked"));
    if (account === "inactive") setError(t("login.accountInactive"));
    if (session === "expired") setError(t("login.sessionExpired"));
    if (session === "password_changed") setError(t("login.passwordChanged"));
    void getBootstrapStatus().then((status) => {
      if (!status.initialized) router.replace("/setup");
    });
    if (!isLoading && isAuthenticated) {
      window.location.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, router, t]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setRemainingAttempts(null);
    setIsSubmitting(true);

    try {
      await login({ email: email.trim().toLowerCase(), password });
      // A full navigation guarantees that the authenticated layout is rebuilt
      // with the stored token and the user's effective locale.
      window.location.replace("/dashboard");
    } catch (caughtError) {
      const data = caughtError instanceof ApiClientError && caughtError.details && typeof caughtError.details === "object"
        ? caughtError.details as { code?: string; retry_after_seconds?: number; remaining_attempts?: number } : null;
      const organizationStatuses: Record<string, string> = {
        ORGANIZATION_SUSPENDED: "suspended",
        ORGANIZATION_INACTIVE: "inactive",
        ORGANIZATION_ARCHIVED: "archived",
      };
      if (data?.code && organizationStatuses[data.code]) {
        router.push(`/org-suspended?status=${organizationStatuses[data.code]}`);
        return;
      }
      if (data?.code === "ACCOUNT_LOCKED") {
        setError(t("login.accountLocked"));
        return;
      }
      if (data?.code === "ACCOUNT_INACTIVE") {
        setError(t("login.accountInactive"));
        return;
      }
      if (data?.code === "ACCOUNT_TEMPORARILY_LOCKED") {
        setRetryAfter(data.retry_after_seconds ?? 1);
        setError(t("login.accountTemporarilyLocked"));
        return;
      }
      if (data?.code === "RATE_LIMIT_EXCEEDED") {
        setRetryAfter(data.retry_after_seconds ?? 60);
        setError(t("login.rateLimitExceeded"));
        return;
      }
      if (data?.code === "INVALID_CREDENTIALS" && typeof data.remaining_attempts === "number") {
        setRemainingAttempts(data.remaining_attempts);
        setError(t("login.errorInvalidCredentials"));
        return;
      }
      const message = caughtError instanceof ApiClientError && caughtError.status === 401
        ? t("login.errorInvalidCredentials") : t("login.errorGeneric");
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={styles.page}>
      <section style={styles.panel} aria-labelledby="login-title">
        <LanguageSwitcher label={t("login.languageSwitcherLabel")} />

        <div style={styles.header}>
          <p style={styles.eyebrow}>{t("login.subtitle")}</p>
          <h1 id="login-title" style={styles.title}>
            {t("login.title")}
          </h1>
        </div>

        <form style={styles.form} onSubmit={handleSubmit}>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("login.emailLabel")}</span>
            <input
              style={sharedStyles.input}
              type="email"
              autoComplete="email"
              placeholder={t("login.emailPlaceholder")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>
          <Link href="/forgot-password" style={{ color: "#2563eb", fontWeight: 700, textDecoration: "none" }}>{resetT("forgotLink")}</Link>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("login.passwordLabel")}</span>
            <PasswordInput
              inputStyle={sharedStyles.input}
              autoComplete="current-password"
              placeholder={t("login.passwordPlaceholder")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          {error ? (
            <div style={sharedStyles.error} role="alert">
              <div>{error}{retryAfter > 0 ? ` ${t("login.tryAgainIn", { time: retryTime })}` : ""}</div>
              {remainingAttempts !== null ? <div style={{ marginTop: 6, fontWeight: 700 }}>{remainingAttempts === 1 ? t("login.lastAttemptWarning") : t("login.remainingAttempts", { count: remainingAttempts })}</div> : null}
            </div>
          ) : null}

          <button
            style={{ ...sharedStyles.button, width: "100%" }}
            type="submit"
            disabled={isSubmitting || retryAfter > 0}
          >
            {isSubmitting ? t("login.submitting") : t("login.submitButton")}
          </button>
        </form>
      </section>
    </main>
  );
}
