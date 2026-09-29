"use client";

import { useEffect, type CSSProperties } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useAuth } from "./auth-context";

type OrganizationStatus = "suspended" | "inactive" | "archived";

const statusThemes: Record<OrganizationStatus, { color: string; background: string; border: string }> = {
  suspended: { color: "var(--warning)", background: "var(--warning-soft)", border: "var(--warning)" },
  inactive: { color: "var(--danger)", background: "var(--surface-muted)", border: "var(--danger)" },
  archived: { color: "var(--text-muted)", background: "var(--surface-muted)", border: "var(--border-strong)" },
};

const styles: Record<string, CSSProperties> = {
  page: { alignItems: "center", background: "var(--page-bg)", boxSizing: "border-box", color: "var(--text)", display: "flex", justifyContent: "center", minHeight: "100vh", padding: "24px" },
  panel: { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "12px", boxShadow: "0 18px 50px rgba(31, 41, 51, 0.1)", boxSizing: "border-box", maxWidth: "560px", padding: "32px", textAlign: "center", width: "100%" },
  icon: { alignItems: "center", border: "2px solid", borderRadius: "999px", display: "inline-flex", height: "76px", justifyContent: "center", marginBottom: "20px", width: "76px" },
  eyebrow: { color: "var(--text-muted)", fontSize: "14px", fontWeight: 700, margin: "0 0 8px" },
  title: { fontSize: "28px", lineHeight: 1.25, margin: "0 0 16px" },
  message: { color: "var(--text-muted)", lineHeight: 1.7, margin: "0 auto 22px", maxWidth: "460px" },
  action: { border: "1px solid", borderRadius: "8px", lineHeight: 1.6, margin: "0 0 24px", padding: "16px" },
  button: { background: "var(--text)", border: 0, borderRadius: "7px", color: "var(--surface)", cursor: "pointer", font: "inherit", fontWeight: 700, minHeight: "44px", padding: "10px 18px", width: "100%" },
};

function StatusIcon({ status }: { status: OrganizationStatus }) {
  if (status === "archived") {
    return <svg aria-hidden="true" width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 6h18M5 6v14h14V6M9 10h6"/><path d="M4 3h16v3H4z"/></svg>;
  }
  if (status === "inactive") {
    return <svg aria-hidden="true" width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/></svg>;
  }
  return <svg aria-hidden="true" width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9"/><path d="M10 9v6m4-6v6"/></svg>;
}

export function OrganizationStatusPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("orgStatus");
  const { isAuthenticated, isLoading } = useAuth();
  const requestedStatus = searchParams.get("status");
  const status: OrganizationStatus = requestedStatus === "inactive" || requestedStatus === "archived" ? requestedStatus : "suspended";
  const isKnownStatus = requestedStatus === null || ["suspended", "inactive", "archived"].includes(requestedStatus);
  const theme = statusThemes[status];

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/dashboard");
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || isAuthenticated) return null;

  return (
    <main style={styles.page}>
      <section style={styles.panel} aria-labelledby="organization-status-title">
        <LanguageSwitcher label={t("languageSwitcherLabel")} />
        <div style={{ ...styles.icon, background: theme.background, borderColor: theme.border, color: theme.color }}><StatusIcon status={status} /></div>
        <p style={styles.eyebrow}>{t("pageTitle")}</p>
        <h1 id="organization-status-title" style={styles.title}>{t(`${status}.title`)}</h1>
        <p style={styles.message}>{isKnownStatus ? t(`${status}.message`) : t("statusUnknown")}</p>
        <div style={{ ...styles.action, background: theme.background, borderColor: theme.border, color: theme.color }}>
          <strong>{t("contactAdmin")}</strong>
          <div>{isKnownStatus ? t(`${status}.action`) : t("statusUnknown")}</div>
        </div>
        <button type="button" style={styles.button} onClick={() => router.push("/login")}>{t("tryLoginAgain")}</button>
      </section>
    </main>
  );
}
