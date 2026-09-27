"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { useTranslations } from "next-intl";

import { sharedStyles } from "@/styles/shared-styles";
import { usePermission } from "./permission-hooks";

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    background: "#f6f7f9",
    padding: "32px",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  card: {
    ...sharedStyles.state,
    background: "#ffffff",
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
    background: "#fff1f2",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "26px",
  },
  message: {
    color: "#1f2933",
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
  },
};

export function PermissionGate({ code, children }: { code: string; children: ReactNode }) {
  const allowed = usePermission(code);
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
