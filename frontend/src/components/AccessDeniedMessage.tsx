"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { sharedStyles } from "@/styles/shared-styles";

const styles: Record<string, CSSProperties> = {
  card: {
    ...sharedStyles.state,
    background: "var(--surface)",
    display: "grid",
    justifyItems: "center",
    gap: "10px",
    padding: "40px 24px",
    textAlign: "center",
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

export function AccessDeniedMessage({ message }: { message?: string } = {}) {
  const t = useTranslations("administration");
  const nav = useTranslations("navigation");
  const resolvedMessage = message ?? t("accessDenied");

  return (
    <PageFrame title={t("accessDenied")}>
      <section style={styles.card}>
        <div style={styles.icon} aria-hidden="true">🚫</div>
        <p style={styles.message}>{resolvedMessage}</p>
        <Link href="/dashboard" style={sharedStyles.secondaryButton}>
          {nav("dashboard")}
        </Link>
      </section>
    </PageFrame>
  );
}
