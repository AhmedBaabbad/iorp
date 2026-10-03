"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { useTranslations } from "next-intl";

import { sharedStyles } from "@/styles/shared-styles";
import { useHasAnyPermission } from "./permission-hooks";

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    background: "var(--page-bg)",
    padding: "32px",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  card: {
    ...sharedStyles.state,
    background: "var(--surface)",
    display: "grid",
    justifyItems: "center",
    gap: "10px",
    padding: "40px 24px",
    textAlign: "center",
    maxWidth: "420px",
  },
  icon: {
    width: "56px",
    height: "56px",
    borderRadius: "50%",
    background: "var(--surface-muted)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "26px",
  },
  message: {
    color: "var(--text)",
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
  },
};

/** Shows the page when the user holds `code`, or any one of `anyOf` (e.g. one of several reports). */
export function PermissionGate({ code, anyOf, children }: { code?: string; anyOf?: string[]; children: ReactNode }) {
  const allowed = useHasAnyPermission(anyOf ?? (code ? [code] : []));
  const t = useTranslations("common");
  const nav = useTranslations("navigation");

  if (!allowed) {
    return (
      <main style={styles.page}>
        <section role="alert" style={styles.card}>
          <div style={styles.icon} aria-hidden="true">🚫</div>
          <p style={styles.message}>{t("states.forbidden")}</p>
          <Link href="/dashboard" style={sharedStyles.secondaryButton}>
            {nav("dashboard")}
          </Link>
        </section>
      </main>
    );
  }

  return <>{children}</>;
}
